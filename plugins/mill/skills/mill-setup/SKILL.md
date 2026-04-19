---
name: mill-setup
description: Initialise mill in a fresh primary-clone directory. Creates the wiki clone at the sibling path, the .millhouse/wiki junction, a local config.local.yaml, and an initial Home.md. Idempotent — safe to re-run after a partial setup.
---

# mill-setup

Bootstrap the mill infrastructure from nothing. Produces a working `.millhouse/` + wiki junction in the current working clone.

## When to invoke

- First-time setup of a hub clone on a new machine
- After a crash or partial setup
- When `.millhouse/wiki` junction is missing or broken

## Preconditions

- `cwd` is the primary clone directory (typically `C:\Code\<project>\hub\`)
- `git remote get-url origin` returns a valid URL
- `plugins/mill/scripts/` contains `_junction.py`, `_wiki.py`, `_subprocess_util.py`, `_render.py` (lifted in M1.1)
- `plugins/mill/templates/config.local.yaml` and `plugins/mill/templates/Home.md` exist (shipped with M1.2)

## Layout assumed

```
<container>/
  hub/            <- cwd
  wiki/           <- sibling, created or reused in Phase 3
```

Every path below is relative to `cwd` unless noted. Use absolute paths when calling the Python helpers (resolve via `Path(...).resolve()`).

## How to invoke the M1.1 helpers

The helpers in `plugins/mill/scripts/` are flat modules. Set `PYTHONPATH` once at the top of the session, then call them directly:

```powershell
$env:PYTHONPATH = (Resolve-Path 'plugins/mill/scripts').Path
```

After that you can use `python -c "..."` with plain `import _junction` / `import _wiki` etc., no `sys.path` gymnastics inside the snippet.

## Phases

Run in order. Stop on the first hard error and report it. Every phase is idempotent — re-checks current state before acting.

### Phase 1 — Derive wiki URL

1. `git remote get-url origin` → `<origin-url>`.
2. Compute `<wiki-url>`: strip trailing `.git` if present, append `.wiki.git`.
   - `https://github.com/org/repo.git` → `https://github.com/org/repo.wiki.git`
3. Store `<wiki-url>` and `<container>` (the parent of `cwd`).

### Phase 2 — Verify wiki is reachable and non-empty

Run `git ls-remote <wiki-url>`. If it fails (exit non-zero), halt with:

> The wiki at `<wiki-url>` is unreachable or empty. Open `https://github.com/<owner>/<repo>/wiki` on GitHub, create the Home page with any content, then re-run `/mill-setup`.
>
> (GitHub does not create the wiki git repo until the first page is saved.)

### Phase 3 — Clone or fast-forward the wiki at `<container>/wiki`

1. If `<container>/wiki/` does not exist: `git clone <wiki-url> <container>/wiki`.
2. If `<container>/wiki/` exists and is a git repo (`<container>/wiki/.git/` present): `git -C <container>/wiki pull --ff-only`.
3. If `<container>/wiki/` exists but is not a git repo: halt with:
   > `<container>/wiki/` exists but is not a git repository. Move it aside or remove it, then re-run `/mill-setup`. mill-setup never overwrites user data.

### Phase 4 — Create the `.millhouse/wiki` junction

Call `_junction.create` from M1.1:

```powershell
python -c "from pathlib import Path; import _junction; _junction.create(Path(r'<container>/wiki').resolve(), Path('.millhouse/wiki').resolve())"
```

Before calling, check state:

1. If `.millhouse/wiki` does not exist: create it via the call above.
2. If it exists and already resolves to `<container>/wiki`: skip.
3. If it exists but resolves elsewhere: halt with:
   > `.millhouse/wiki` junction points at `<current-target>`. Expected `<container>/wiki`. Remove `.millhouse/wiki`, then re-run `/mill-setup`.

### Phase 5 — Seed `.millhouse/config.local.yaml`

1. If `.millhouse/config.local.yaml` exists: skip.
2. Otherwise: copy `plugins/mill/templates/config.local.yaml` → `.millhouse/config.local.yaml` verbatim (no substitution).

### Phase 6 — Initialise or normalise `Home.md`

Decide what to do based on the current content of `<container>/wiki/Home.md`:

| Current state | Action |
|---|---|
| File missing | Write template, commit & push (`chore: init Home.md`) |
| Matches GitHub default — content is literally `Welcome to the <repo> wiki!` (optionally followed by whitespace) | Overwrite from template, commit & push (`chore: replace GitHub-default Home.md with v2 tasks template`). Safe because GitHub authored it, not the user. |
| First non-blank line is `# Tasks` | Already in v2 shape — skip. |
| Anything else | User content present — skip and emit a warning: "Home.md does not start with `# Tasks`; mill-add may behave unexpectedly. Edit Home.md manually if you want it normalised." Do not overwrite. |

For "missing" and "GitHub default" cases:

1. Copy `plugins/mill/templates/Home.md` → `<container>/wiki/Home.md` verbatim.
2. Commit and push via `_wiki.write_commit_push`:

   ```powershell
   python -c "from pathlib import Path; import _wiki; _wiki.write_commit_push(Path(r'<container>/wiki').resolve(), ['Home.md'], '<commit-msg>')"
   ```

   (Use the commit message from the table above.)

**GitHub-default detection:** read the file, strip outer whitespace, match the pattern `^Welcome to the .+ wiki!$` (single line). The `<repo>` name varies per project; the surrounding text is fixed. This pattern is what GitHub writes when the user clicks "Create the first page" without editing.

### Phase 7 — VS Code window colour (hub = green)

The hub is the canonical "main" workspace, always coloured `#2d7d46` so the operator can spot it instantly when several VS Code windows are open. mill-spawn picks non-green colours per worktree (M3.1).

Derive `<short-name>` from the origin URL: take the last path segment, strip any trailing `.git`. For `https://github.com/Knatte18/millhouse.git` that gives `millhouse`.

Behaviour:

| Current state of `.vscode/settings.json` | Action |
|---|---|
| Missing | Render template, write file. |
| Present and contains `"titleBar.activeBackground": "#2d7d46"` (regex match — VS Code's settings.json allows trailing commas and comments, so do **not** parse it as strict JSON) | Skip (idempotent). |
| Present with a different `titleBar.activeBackground` colour | Back up to `.vscode/settings.json.bak`, then overwrite from template. |
| Present but no `titleBar.activeBackground` key at all | Back up to `.vscode/settings.json.bak`, then overwrite from template. |

Render via `_render.py`:

```powershell
python -c "from pathlib import Path; import _render; out = _render.render(Path('plugins/mill/templates/vscode-settings.json'), {'COLOR_HEX': '#2d7d46', 'WINDOW_TITLE': '<short-name>: `${activeEditorShort}'}); Path('.vscode').mkdir(exist_ok=True); Path('.vscode/settings.json').write_text(out, encoding='utf-8')"
```

Note: `${activeEditorShort}` is a literal VS Code variable that must reach the rendered file unchanged. Inside a PowerShell double-quoted string, `$` triggers variable expansion — escape it with a backtick: write `` `${activeEditorShort} `` (backtick + `$` + braces). The backtick is consumed by PowerShell; the rendered JSON contains the literal `${activeEditorShort}`.

### Phase 8 — Verify + report

Check every invariant; halt with a specific error if any fails:

- `<container>/wiki/` is a git repo
- `.millhouse/wiki` junction exists and resolves to `<container>/wiki`
- `.millhouse/config.local.yaml` exists
- `<container>/wiki/Home.md` exists and starts with `# Tasks`
- `.vscode/settings.json` exists with `titleBar.activeBackground == "#2d7d46"`

On success, print:

```
mill-setup complete.

  Container:     <container>
  Hub:           <cwd>
  Wiki clone:    <container>/wiki
  Wiki junction: .millhouse/wiki -> <container>/wiki
  Tasks (Home):  <container>/wiki/Home.md
  Local config:  .millhouse/config.local.yaml
  VS Code:       .vscode/settings.json (titleBar = #2d7d46 green)

Next: /mill-add <slug> --description "..." to add tasks, /mill-list to list them.
```

## Error conditions

| Condition | Action |
|---|---|
| `git ls-remote <wiki-url>` fails | Halt with GitHub URL + instruction to create Home page |
| `<container>/wiki/` exists but not a git repo | Halt — never overwrite user data |
| `.millhouse/wiki` junction points elsewhere | Halt with remove-and-rerun instruction |
| Push of `Home.md` fails (network / auth) | Halt; user fixes network and re-runs |
| A Python helper raises | Show the traceback from the Python invocation and halt |

## Idempotency

Every phase checks current state before acting. Re-running after a partial or complete setup is always safe:

- Wiki already cloned → pulls latest.
- Junction correct → skipped.
- `config.local.yaml` present → skipped.
- `Home.md` non-empty (and v2-shape or user-custom) → skipped; only GitHub-default content is overwritten.
- `.vscode/settings.json` already green → skipped.

A second `/mill-setup` run on a fully-set-up clone makes no changes and prints the same summary block.
