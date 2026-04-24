---
name: mill-setup
description: Initialise mill in a fresh primary-clone directory. Creates the wiki clone, seeds wiki/config.yaml, creates hub junctions and hardlinks, seeds config.local.yaml and Home.md, and sets VS Code window colour. Idempotent — safe to re-run after a partial setup.
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
- `plugins/mill/templates/config.local.yaml`, `plugins/mill/templates/wiki-config.yaml`, and `plugins/mill/templates/Home.md` exist

## Layout assumed

Hub-form (cwd dir is named exactly `hub`):

```
<container>/
  hub/            <- cwd
  wiki/           <- sibling, created or reused in Phase 3
```

Prefix-form (any other name, e.g. `foo`):

```
<container>/
  foo/            <- cwd
  foo.wiki/       <- sibling, created or reused in Phase 3
```

The form is decided by `_sibling.py wiki <HUB_PATH>` in Phase 3 — callers just use `<wiki-dir>` thereafter. Every path below is relative to `cwd` unless noted. Use absolute paths when calling the Python helpers (resolve via `Path(...).resolve()`).

## How to invoke the helpers

The helpers in `plugins/mill/scripts/` are flat modules. Set `PYTHONPATH` once at the top of the session, then call them directly:

```powershell
$env:PYTHONPATH = (Resolve-Path 'plugins/mill/scripts').Path
```

After that you can use `python -c "..."` with plain `import _junction`, `import _wiki`, `import _vscode`, etc. — no `sys.path` gymnastics inside the snippet.

Helpers used by this skill: `_junction` (Phase 4, 4.5), `_wiki` (Phase 3.5, 6, 6a — incl. `read_junctions` and `read_hardlinks`), `_sidebar` (Phase 6a), `_vscode` (Phase 7), `_render` (transitively via `_vscode`).

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

### Phase 3 — Clone or fast-forward the wiki at `<wiki-dir>`

First compute `<wiki-dir>` using the sibling-path helper — this yields `<container>/wiki/` when the hub directory is named exactly `hub`, otherwise `<container>/<repo>.wiki/`. Use the printed path as `<wiki-dir>` for the remainder of mill-setup (Phases 3, 3.5, 4, 6, 6a, 8):

```powershell
python "${env:CLAUDE_PLUGIN_ROOT}/scripts/_sibling.py" wiki "<hub-path>"
```

`<hub-path>` is `<HUB_PATH>` from Phase 3.5 (`git rev-parse --show-toplevel`). Users can override via `.millhouse/config.local.yaml`'s `wiki_path:` key — that value wins over the helper's default.

1. If `<wiki-dir>` does not exist: `git clone <wiki-url> <wiki-dir>`.
2. If `<wiki-dir>` exists and is a git repo (`<wiki-dir>/.git/` present): `git -C <wiki-dir> pull --ff-only`.
3. If `<wiki-dir>` exists but is not a git repo: halt with:
   > `<wiki-dir>` exists but is not a git repository. Move it aside or remove it, then re-run `/mill-setup`. mill-setup never overwrites user data.

### Phase 3.1 — Seed `wiki/config.yaml` from template

1. If `<wiki-dir>/config.yaml` exists: skip.
2. Otherwise: copy `plugins/mill/templates/wiki-config.yaml` → `<wiki-dir>/config.yaml` verbatim (no substitution — tokens are resolved at runtime by scripts, not at seed time).
3. Commit and push via `_wiki.write_commit_push`:

   ```powershell
   python -c "from pathlib import Path; import _wiki; _wiki.write_commit_push(Path(r'<wiki-dir>').resolve(), ['config.yaml'], 'chore: init wiki/config.yaml')"
   ```

**Why verbatim copy:** the token placeholders (`<WIKI_PATH>` etc.) are resolved by `_junction.resolve_target` and `_wiki.read_hardlinks` at runtime. Substituting at seed time would bake in machine-specific paths, breaking the file for other clones.

### Phase 3.5 — Resolve junctions from wiki config

After the wiki is cloned (Phase 3) but before any junction is created, read the `junctions:` block from `<wiki-dir>/config.yaml`:

```powershell
python -c "from pathlib import Path; import _wiki; import json; print(json.dumps(_wiki.read_junctions(Path(r'<wiki-dir>').resolve())))"
```

`read_junctions` returns a dict of `{junction-path: target-template}`. Defaults when the config file or `junctions:` block is absent:

- `.millhouse/wiki` → `<WIKI_PATH>`
- `.active` → `<WIKI_PATH>/active/<SLUG>/`

**Compute the token map** for this run. All tokens are UPPERCASE; paths carry the `_PATH` suffix.

- `<HUB_PATH>` — the primary clone. Derive via `git rev-parse --show-toplevel` (and, in future, worktree-detect to fall back to the primary from a worktree subfolder).
- `<CWD_PATH>` — current working directory (absolute).
- `<CONTAINER_PATH>` — parent of `<HUB_PATH>` (holds hub/, wiki/, worktrees/).
- `<WIKI_PATH>` — the wiki clone (`<wiki-dir>` from Phase 3). Default: computed by `python ${CLAUDE_PLUGIN_ROOT}/scripts/_sibling.py wiki <HUB_PATH>` — hub-form yields `<CONTAINER_PATH>/wiki/`, prefix-form yields `<CONTAINER_PATH>/<REPO>.wiki/`. Override if `.millhouse/config.local.yaml` has a `wiki_path:` key.
- `<REPO>` — short repo name from origin URL (last path segment, stripped of `.git`).

Do **NOT** add `<SLUG>` — mill-setup only handles hub-scope junctions. Entries whose template contains `<SLUG>` belong to mill-spawn.

Partition the junction entries:

- **Hub junctions**: template does not contain `<SLUG>`. These are created now (Phase 4).
- **Per-worktree junctions**: template contains `<SLUG>`. Skipped by mill-setup; reported in Phase 8 summary so the user can confirm they exist in config.

For each hub junction, substitute tokens via `_junction.resolve_target`:

```powershell
python -c "import _junction; print(_junction.resolve_target('<WIKI_PATH>/active/<SLUG>/', {'HUB_PATH': 'C:/path', 'CWD_PATH': '.', 'CONTAINER_PATH': 'C:/', 'REPO': 'millhouse', 'WIKI_PATH': 'C:/path/../millhouse.wiki'}))"
```

Unknown tokens raise `ValueError` — halt and tell the user to correct the `junctions:` block.

**Invariant:** Junctions are IDE/terminal convenience. Scripts MUST resolve to the real wiki repo (`<WIKI_PATH>`-token value) and never treat the junction path as authoritative.

### Phase 4 — Create the hub junctions

For each hub-scope entry resolved in Phase 3.5 (the ones without `<SLUG>`), call `_junction.create`:

```powershell
python -c "from pathlib import Path; import _junction; _junction.create(Path(r'<resolved-target>').resolve(), Path(r'<junction-path>').resolve())"
```

Before creating, check state per junction:

1. If `<junction-path>` does not exist: create it. Parent dir (e.g. `.millhouse/`) is auto-created by `_junction.create`.
2. If it exists and already resolves to `<resolved-target>`: skip.
3. If it exists but resolves elsewhere: halt with:
   > `<junction-path>` points at `<current-target>`. Expected `<resolved-target>`. Remove `<junction-path>`, then re-run `/mill-setup`.

Iterate until all hub junctions are present. Entries with `<SLUG>` are left to mill-spawn per worktree.

### Phase 4.5 — Create hardlinks and add to `.gitignore`

Read the `hardlinks:` block from `<wiki-dir>/config.yaml`:

```powershell
python -c "from pathlib import Path; import _wiki; import json; print(json.dumps(_wiki.read_hardlinks(Path(r'<wiki-dir>').resolve())))"
```

`read_hardlinks` returns a dict of `{link-path: target-template}`. If the block is absent, return an empty dict (no hardlinks configured).

Resolve each target template using the same token map as Phase 3.5 (no `<SLUG>` — hardlinks are always hub-scope). For each entry:

1. If `<link-path>` already exists and its inode matches `<resolved-target>`'s inode: skip (already a hardlink to the correct file).
2. If `<link-path>` exists but points to a different inode: back up to `<link-path>.bak` and remove the original.
3. Create the hardlink:

   ```powershell
   python -c "from pathlib import Path; Path(r'<link-path>').hardlink_to(Path(r'<resolved-target>'))"
   ```

   On failure (cross-volume): halt with:
   > Cannot create hardlink `<link-path>` → `<resolved-target>`: source and target must be on the same volume. Move the wiki clone to the same drive as the hub, or remove this entry from `hardlinks:` in `wiki/config.yaml`.

4. Add `/<link-path>` to the repo's `.gitignore` if not already present. Check via `grep`:

   ```powershell
   python -c "
   from pathlib import Path
   gi = Path('.gitignore')
   entry = '/<link-path>'
   if entry not in gi.read_text(encoding='utf-8').splitlines():
       with gi.open('a', encoding='utf-8') as f:
           f.write(f'\n{entry}\n')
   "
   ```

5. If the file was already tracked by git, untrack it:

   ```powershell
   git ls-files --error-unmatch <link-path> 2>/dev/null && git rm --cached <link-path>
   ```

**Idempotency:** inode comparison in step 1 ensures re-runs skip already-correct hardlinks. The `.gitignore` check in step 4 avoids duplicate entries.

### Phase 5 — Seed `.millhouse/config.local.yaml`

1. If `.millhouse/config.local.yaml` exists: skip.
2. Otherwise: copy `plugins/mill/templates/config.local.yaml` → `.millhouse/config.local.yaml` verbatim (no substitution).

### Phase 6 — Initialise or normalise `Home.md`

Decide what to do based on the current content of `<wiki-dir>/Home.md`:

| Current state | Action |
|---|---|
| File missing | Write template, commit & push (`chore: init Home.md`) |
| Matches GitHub default — content is literally `Welcome to the <repo> wiki!` (optionally followed by whitespace) | Overwrite from template, commit & push (`chore: replace GitHub-default Home.md with v2 tasks template`). Safe because GitHub authored it, not the user. |
| First non-blank line is `# Tasks` | Already in v2 shape — skip. |
| Anything else | User content present — skip and emit a warning: "Home.md does not start with `# Tasks`; mill-add may behave unexpectedly. Edit Home.md manually if you want it normalised." Do not overwrite. |

For "missing" and "GitHub default" cases:

1. Copy `plugins/mill/templates/Home.md` → `<wiki-dir>/Home.md` verbatim.
2. Commit and push via `_wiki.write_commit_push`:

   ```powershell
   python -c "from pathlib import Path; import _wiki; _wiki.write_commit_push(Path(r'<wiki-dir>').resolve(), ['Home.md'], '<commit-msg>')"
   ```

   (Use the commit message from the table above.)

**GitHub-default detection:** read the file, strip outer whitespace, match the pattern `^Welcome to the .+ wiki!$` (single line). The `<repo>` name varies per project; the surrounding text is fixed. This pattern is what GitHub writes when the user clicks "Create the first page" without editing.

### Phase 6a — Initialise `_Sidebar.md` via `_sidebar.regenerate()`

The wiki sidebar is auto-generated from `Home.md` and the set of `proposal-*.md` files at wiki root. Regenerate it every time `mill-setup` runs so a fresh clone gets a Navigation-only sidebar, and any hand-edited sidebar drift is healed.

Run:

```powershell
python -c "from pathlib import Path; import _sidebar; _sidebar.regenerate(Path(r'<wiki-dir>').resolve())"
```

Then commit + push if the file changed:

1. Check `git -C <wiki-dir> status --porcelain _Sidebar.md`.
2. If the command prints nothing, the sidebar is already correct — skip the commit. (Idempotency: second and later runs land here.)
3. Otherwise, commit via `_wiki.write_commit_push`:

   ```powershell
   python -c "from pathlib import Path; import _wiki; _wiki.write_commit_push(Path(r'<wiki-dir>').resolve(), ['_Sidebar.md'], 'chore: regenerate _Sidebar.md')"
   ```

**Why separate from Phase 6:** Phase 6 only writes `Home.md` on the missing / GitHub-default branches. When Phase 6 skips (Home.md already in v2 shape), the sidebar still needs to be regenerated the first time `mill-setup` runs against a clone that was bootstrapped before this phase existed. Running it unconditionally is cheap and keeps the two commits separate in history: one says "init Home.md", the other says "regenerate _Sidebar.md".

**On `_sidebar.regenerate` semantics:** the function is pure on wiki state — it reads `Home.md` and the on-disk `proposal-*.md` set, writes `_Sidebar.md`, performs no git operations. Calling it when the sidebar is already correct produces a byte-identical file; `git status` in step 1 above will report no changes and the commit is skipped.

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

Render and write via `_vscode.write_settings` (which wraps `_render` and the file write):

```powershell
python -c "from pathlib import Path; import _vscode; _vscode.write_settings('#2d7d46', '<short-name>', Path('.vscode/settings.json'))"
```

Title format for the hub: **just the repo short-name** (e.g. `millhouse`). No `${activeEditorShort}`, no slug — this is the main workspace and the title must read clearly in the Windows 11 taskbar at small sizes. Worktrees use `<short-name>: <slug>` (mill-spawn, M3.1).

`_vscode.write_settings` overwrites unconditionally; the *decision* to write (skip vs back-up vs render) is this skill's job above. mill-spawn (M3.1) calls the same helper for worktree colours.

### Phase 8 — Verify + report

Check every invariant; halt with a specific error if any fails:

- `<WIKI_PATH>` is a git repo (the cloned wiki)
- `<WIKI_PATH>/config.yaml` exists
- Every hub junction (Phase 4 entry) exists and resolves to its expected target
- Every hardlink (Phase 4.5 entry) exists and shares an inode with its target
- `.millhouse/config.local.yaml` exists
- `<WIKI_PATH>/Home.md` exists and starts with `# Tasks`
- `<WIKI_PATH>/_Sidebar.md` exists and begins with `### Navigation`
- `.vscode/settings.json` exists with `titleBar.activeBackground == "#2d7d46"`

On success, print a summary:

```
mill-setup complete.

  Hub:           <HUB_PATH>
  Wiki clone:    <WIKI_PATH>
  Local config:  .millhouse/config.local.yaml
  Tasks (Home):  <WIKI_PATH>/Home.md  (hardlinked as tasks.md)
  Sidebar:       <WIKI_PATH>/_Sidebar.md
  VS Code:       .vscode/settings.json (titleBar = #2d7d46 green)

Junctions (from wiki config.yaml):
  Hub-scope (created now):
    <path-a> -> <resolved-target-a>
  Per-worktree (created by mill-spawn):
    <path-c> -> <template-c>    (contains <SLUG>)

Hardlinks (from wiki config.yaml):
  <link-a> -> <resolved-target-a>

Next: /mill-add <slug> --title "..." [--summary "..."] [--proposal-body "..."] to add tasks, /mill-list to list them.
```

## Error conditions

| Condition | Action |
|---|---|
| `git ls-remote <wiki-url>` fails | Halt with GitHub URL + instruction to create Home page |
| `<wiki-dir>` exists but not a git repo | Halt — never overwrite user data |
| `.millhouse/wiki` junction points elsewhere | Halt with remove-and-rerun instruction |
| Push of `Home.md` fails (network / auth) | Halt; user fixes network and re-runs |
| A Python helper raises | Show the traceback from the Python invocation and halt |

## Idempotency

Every phase checks current state before acting. Re-running after a partial or complete setup is always safe:

- Wiki already cloned → pulls latest.
- `wiki/config.yaml` present → skipped (Phase 3.1).
- Junction-prefs re-read from wiki config each run → picks up changes to `junctions:` block after a wiki pull.
- Wiki junction correct (at the configured path) → skipped.
- Hardlink inode-matches target → skipped; `.gitignore` entry already present → not duplicated (Phase 4.5).
- `config.local.yaml` present → skipped.
- `Home.md` non-empty (and v2-shape or user-custom) → skipped; only GitHub-default content is overwritten.
- `_Sidebar.md` regenerated unconditionally; commit only if bytes changed.
- `.vscode/settings.json` already green → skipped.

A second `/mill-setup` run on a fully-set-up clone makes no changes and prints the same summary block.
