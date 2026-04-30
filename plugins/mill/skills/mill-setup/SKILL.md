---
name: mill-setup
description: Initialise mill in a fresh primary-clone directory. Creates the wiki clone, seeds wiki/config.yaml, creates hub junctions and hardlinks, seeds config.local.yaml and Home.md, and sets VS Code window colour. Idempotent — safe to re-run after a partial setup.
---

# mill-setup

Bootstrap the mill infrastructure from nothing. Produces a working `.millhouse/` + wiki + container layout in the current working clone.

## When to invoke

- First-time setup of a hub clone on a new machine
- After a crash or partial setup
- When `.millhouse/wiki` junction is missing or broken

## Preconditions

- `cwd` is the hub directory inside a container (typically `<container>/wts/<repo>/`)
- `git remote get-url origin` returns a valid URL
- `uv` is installed (`uv --version` exits 0); install via `irm https://astral.sh/uv/install.ps1 | iex`
- `${CLAUDE_PLUGIN_ROOT}/scripts/` contains `_junction.py`, `_wiki.py`, `_subprocess_util.py`, `_render.py`, `_setup.py`
- `${CLAUDE_PLUGIN_ROOT}/templates/config.local.yaml`, `${CLAUDE_PLUGIN_ROOT}/templates/wiki-config.yaml`, and `${CLAUDE_PLUGIN_ROOT}/templates/Home.md` exist

## Layout assumed

Container-form (main worktree lives under `wts/`):

```
<container>/
  wts/
    <repo>/         <- hub (cwd)
    <slug>/         <- task worktrees (created later by mill-spawn)
  portals/          <- junction stubs, one per active task + one for hub
  wiki/             <- wiki clone (created in Phase 3)
```

Prefix-form (any other structure, e.g. `<container>/<repo>/`):

```
<container>/
  <repo>/           <- hub (cwd)
  <repo>.wiki/      <- wiki clone
```

The form is decided by `_sibling.py wiki <HUB_PATH>` in Phase 3 — callers just use `<wiki-dir>` thereafter. Container-form is detected when `cwd.parent.name == "wts"`; prefix-form is everything else. Use absolute paths when calling Python helpers (resolve via `Path(...).resolve()`).

## How to invoke the helpers

mill-setup is the bootstrapper that **creates** the global `PYTHONPATH` Windows user environment variable. That variable does not exist in the current process (or in any child process spawned during this session) until Phase 4.7 completes and a new shell is opened. Therefore, every Python invocation in this skill uses the inline prefix:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c "..."
```

This inline `PYTHONPATH=` prefix is **only** required in mill-setup. All other skills rely on the global Windows user env var set here and need no prefix.

Helpers used by this skill: `_setup` (Phase 4 — `create_hub_links`), `_gitignore` (Phase 4.5b), `_shortcuts` (Phase 4.7), `_sidebar` (Phase 6a), `_vscode` (Phase 7), `_render` (transitively via `_vscode` and `_shortcuts`), `_wiki` (Phase 3, 3.1, 6, 6a), `_junction` (Phase 3.7).

## Phases

Run in order. Stop on the first hard error and report it. Every phase is idempotent — re-checks current state before acting.

### Phase 1 — Derive wiki URL

0. **Check `uv` is installed:**

   ```bash
   uv --version
   ```

   If exit code is non-zero, halt with:

   > uv is not installed. Install via PowerShell: `irm https://astral.sh/uv/install.ps1 | iex` — then re-run /mill-setup.

1. `git remote get-url origin` → `<origin-url>`.
2. Compute `<wiki-url>`: strip trailing `.git` if present, append `.wiki.git`.
   - `https://github.com/org/repo.git` → `https://github.com/org/repo.wiki.git`
3. Store `<wiki-url>` and `<container>` (the parent of `wts/`, or the parent of `cwd` in prefix-form).

### Phase 2 — Verify wiki is reachable and non-empty

Run `git ls-remote <wiki-url>`. If it fails (exit non-zero), halt with:

> The wiki at `<wiki-url>` is unreachable or empty. Open `https://github.com/<owner>/<repo>/wiki` on GitHub, create the Home page with any content, then re-run `/mill-setup`.
>
> (GitHub does not create the wiki git repo until the first page is saved.)

### Phase 3 — Clone or fast-forward the wiki at `<wiki-dir>`

First compute `<wiki-dir>` using the sibling-path helper — this yields `<container>/wiki/` in container-form, otherwise `<container>/<repo>.wiki/`. Use the printed path as `<wiki-dir>` for the remainder of mill-setup:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/_sibling.py" wiki "<hub-path>"
```

`<hub-path>` is derived via `git rev-parse --show-toplevel`. Users can override via `.millhouse/config.local.yaml`'s `wiki_path:` key.

1. If `<wiki-dir>` does not exist: `git clone <wiki-url> <wiki-dir>`.
2. If `<wiki-dir>` exists and is a git repo (`<wiki-dir>/.git/` present): `git -C <wiki-dir> pull --ff-only`.
3. If `<wiki-dir>` exists but is not a git repo: halt with:
   > `<wiki-dir>` exists but is not a git repository. Move it aside or remove it, then re-run `/mill-setup`. mill-setup never overwrites user data.

### Phase 3.1 — Seed `wiki/config.yaml` from template

1. If `<wiki-dir>/config.yaml` exists: skip.
2. Otherwise: copy `${CLAUDE_PLUGIN_ROOT}/templates/wiki-config.yaml` → `<wiki-dir>/config.yaml` verbatim (no substitution — tokens are resolved at runtime by scripts, not at seed time).
3. Commit and push via `_wiki.write_commit_push`:

   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c "from pathlib import Path; import _wiki; _wiki.write_commit_push(Path(r'<wiki-dir>').resolve(), ['config.yaml'], 'chore: init wiki/config.yaml')"
   ```

**Why verbatim copy:** the token placeholders (`<WIKI_PATH>` etc.) are resolved by `_junction.resolve_target` and `_wiki.read_hardlinks` at runtime. Substituting at seed time would bake in machine-specific paths.

### Phase 3.7 — Create container scaffolding

Create the `<container>/portals/` directory (if missing) and the main-worktree portal entry pointing at the hub:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c "
from pathlib import Path
import _junction
container = Path(r'<container>').resolve()
portals = container / 'portals'
portals.mkdir(parents=True, exist_ok=True)
hub = Path(r'<hub-path>').resolve()
portal_entry = portals / hub.name
if not portal_entry.exists():
    _junction.create(hub, portal_entry)
    print(f'created portal entry: {portal_entry} -> {hub}')
else:
    print('portal entry already exists, skipping')
"
```

`<hub.name>` is the repository directory name (last component of `<hub-path>`). This portal entry is the canonical "hub in portals" that `.others/<repo>` resolves through.

**Idempotency:** `portals.mkdir(exist_ok=True)` is a no-op if the directory already exists. The portal junction check prevents double-creation.

### Phase 4 — Create hub links (junctions + hardlinks)

Call `_setup.create_hub_links` with the hub token set (no `<SLUG>` — that is mill-spawn's concern). The helper reads both the `junctions:` and `hardlinks:` blocks from `<wiki-dir>/config.yaml`, applies the token-scope filter (silently skipping entries whose templates reference `<SLUG>`), creates all hub-scope junctions, and creates all hardlinks idempotently:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c "
from pathlib import Path
import json, _setup
result = _setup.create_hub_links(
    target_root=Path(r'<hub-path>').resolve(),
    wiki_path=Path(r'<wiki-dir>').resolve(),
    tokens={
        'HUB_PATH':       r'<hub-path>',
        'CWD_PATH':       r'<cwd>',
        'CONTAINER_PATH': r'<container>',
        'WIKI_PATH':      r'<wiki-dir>',
        'REPO':           '<repo>',
    },
)
print(json.dumps({k: [str(p) for p in v] for k, v in result.items()}, indent=2))
"
```

Token reference:
- `<hub-path>` — absolute path to the hub (`git rev-parse --show-toplevel`)
- `<cwd>` — current working directory absolute path
- `<container>` — parent of `wts/` (container-form) or parent of hub (prefix-form)
- `<wiki-dir>` — wiki clone path from Phase 3
- `<repo>` — repository directory name (e.g. `millhouse`)

**Do NOT add `<SLUG>`** — the token-scope filter skips junction entries that need `<SLUG>` (`.active`, per-task `.others` entries). Those are created by mill-spawn.

Log the created junctions and hardlinks from the returned dict so the user can verify.

### Phase 4.5b — Manage `.gitignore` marker block

Maintains the `# === mill-managed ... # === end mill-managed ===` block across the repo-root `.gitignore` and (when hub is a subdirectory of the repo) a hub-local `.gitignore`.

Compute `<repo-root-gitignore>` and `<hub-gitignore>`:
- In container-form (`hub-path == git-toplevel`): both paths are the same (`<git-toplevel>/.gitignore`).
- In prefix-form (hub is a subfolder of the repo): `<repo-root-gitignore>` is `<git-toplevel>/.gitignore`; `<hub-gitignore>` is `<hub-path>/.gitignore`.

Read the hardlink entry names (available from Phase 4 output), then call `_gitignore.upsert_split`:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c "
from pathlib import Path
import _wiki, _gitignore, json
wiki = Path(r'<wiki-dir>').resolve()
hardlinks = _wiki.read_hardlinks(wiki)
hardlink_names = list(hardlinks.keys())
repo_gi = Path(r'<repo-root-gitignore>').resolve()
hub_gi = Path(r'<hub-gitignore>').resolve()
glob_entries = _gitignore.GLOB_ENTRIES
anchored_entries = _gitignore.ANCHORED_ENTRIES + hardlink_names
repo_changed, hub_changed = _gitignore.upsert_split(repo_gi, hub_gi, glob_entries, anchored_entries)
print('repo .gitignore:', 'updated' if repo_changed else 'already up to date')
print('hub .gitignore: ', 'updated' if hub_changed else 'already up to date')
"
```

Log the result per file. When both paths are the same a single combined block is written; when different, glob entries go to `repo_root_gitignore` and anchored entries go to `hub_gitignore`.

### Phase 4.7 — PS1 shortcut wrappers

Creates `.millhouse/<script>.ps1` forwarders for every user-callable mill script. Each wrapper locates the latest installed millhouse plugin cache and delegates to the real script via `uv run`.

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c "
from pathlib import Path
import _shortcuts
written = _shortcuts.write_all(Path('.millhouse'))
print(f'wrote {len(written)} wrappers' if written else 'wrappers up to date')
"
```

Log `wrote N wrappers` or `wrappers up to date` based on the returned list.

Then set the `PYTHONPATH` Windows user environment variable to the scripts directory of the latest installed plugin version. Use `powershell` (PS5 — guaranteed on Windows 11; `pwsh` is not):

```bash
powershell -Command "
\$cache = \"\$env:USERPROFILE\\.claude\\plugins\\cache\\millhouse\\mill\";
\$latest = (Get-ChildItem \$cache -Directory | Sort-Object Name -Descending | Select-Object -First 1).FullName;
\$scripts = Join-Path \$latest 'scripts';
[System.Environment]::SetEnvironmentVariable('PYTHONPATH', \$scripts, 'User');
Write-Host \"Set PYTHONPATH (User) = \$scripts\"
"
```

Log: `Set PYTHONPATH (User) = <scripts>. Note: takes effect in NEW shell sessions; current mill-setup session must keep using the inline PYTHONPATH prefix above.`

**Note:** After running `update-plugins.ps1` to install a new plugin version, re-run `/mill-setup` to refresh PYTHONPATH and the PS1 wrappers to the new version.

### Phase 4.9 — Seed `hub_relative_path` in `config.local.yaml`

The `hub_relative_path` key tells mill-terminal and mill-vscode where the effective hub directory is within the worktree. Write it before seeding `config.local.yaml` (Phase 5) so it appears in the seeded file if the file doesn't exist yet, and update it if the file already exists.

Compute the value:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c "
from pathlib import Path
cwd = Path.cwd().resolve()
git_toplevel = Path(r'<git-toplevel>').resolve()
try:
    rel = cwd.relative_to(git_toplevel).as_posix()
except ValueError:
    rel = '.'
print(rel)
"
```

- When `cwd == git_toplevel` (typical mill setup where the hub is the repo root): value is `"."`.
- When `cwd` is a subdirectory of `git_toplevel` (downstream consumer pattern): value is the relative subpath (e.g. `"src/csharp/Models"`).

Write the value into `.millhouse/config.local.yaml`. If the file already exists and already contains `hub_relative_path:`, update it in-place; if missing or absent from the file, append/insert it before the first non-comment key:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c "
from pathlib import Path
import yaml, re
cfg_path = Path('.millhouse/config.local.yaml')
hub_subpath = r'<hub_subpath>'  # computed above
if cfg_path.exists():
    text = cfg_path.read_text(encoding='utf-8')
    if 'hub_relative_path:' in text:
        text = re.sub(r'^hub_relative_path:.*$', f'hub_relative_path: {hub_subpath}', text, flags=re.MULTILINE)
    else:
        text = f'hub_relative_path: {hub_subpath}\n' + text
    cfg_path.write_text(text, encoding='utf-8')
    print(f'updated hub_relative_path: {hub_subpath}')
else:
    # Phase 5 will seed the full file; just record it for Phase 5.
    print(f'hub_relative_path: {hub_subpath} (will be written in Phase 5)')
"
```

### Phase 5 — Seed `.millhouse/config.local.yaml`

1. If `.millhouse/config.local.yaml` exists: skip.
2. Otherwise: copy `${CLAUDE_PLUGIN_ROOT}/templates/config.local.yaml` → `.millhouse/config.local.yaml` verbatim, then set `hub_relative_path:` to the value computed in Phase 4.9 (uncomment and fill in the line).

### Phase 6 — Initialise or normalise `Home.md`

Decide what to do based on the current content of `<wiki-dir>/Home.md`:

| Current state | Action |
|---|---|
| File missing | Write template, commit & push (`chore: init Home.md`) |
| Matches GitHub default — content is literally `Welcome to the <repo> wiki!` (optionally followed by whitespace) | Overwrite from template, commit & push (`chore: replace GitHub-default Home.md with v2 tasks template`). Safe because GitHub authored it, not the user. |
| First non-blank line is `# Tasks` | Already in v2 shape — skip. |
| Anything else | User content present — skip and emit a warning: "Home.md does not start with `# Tasks`; mill-add may behave unexpectedly. Edit Home.md manually if you want it normalised." Do not overwrite. |

For "missing" and "GitHub default" cases:

1. Copy `${CLAUDE_PLUGIN_ROOT}/templates/Home.md` → `<wiki-dir>/Home.md` verbatim.
2. Commit and push via `_wiki.write_commit_push`:

   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c "from pathlib import Path; import _wiki; _wiki.write_commit_push(Path(r'<wiki-dir>').resolve(), ['Home.md'], '<commit-msg>')"
   ```

**GitHub-default detection:** read the file, strip outer whitespace, match the pattern `^Welcome to the .+ wiki!$` (single line).

### Phase 6a — Initialise `_Sidebar.md` via `_sidebar.regenerate()`

Regenerate the wiki sidebar every time mill-setup runs:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c "from pathlib import Path; import _sidebar; _sidebar.regenerate(Path(r'<wiki-dir>').resolve())"
```

Then commit + push if the file changed:

1. Check `git -C <wiki-dir> status --porcelain _Sidebar.md`.
2. If nothing printed: already correct — skip the commit.
3. Otherwise commit:

   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c "from pathlib import Path; import _wiki; _wiki.write_commit_push(Path(r'<wiki-dir>').resolve(), ['_Sidebar.md'], 'chore: regenerate _Sidebar.md')"
   ```

### Phase 7 — VS Code window colour (hub = green)

The hub is always coloured `#2d7d46` so the operator can spot it instantly. mill-spawn picks non-green colours per worktree.

| Current state of `.vscode/settings.json` | Action |
|---|---|
| Missing | Render template, write file. |
| Present and `"titleBar.activeBackground": "#2d7d46"` | Skip (idempotent). |
| Present with different colour | Back up to `.vscode/settings.json.bak`, then overwrite. |
| Present but no `titleBar.activeBackground` key | Back up to `.vscode/settings.json.bak`, then overwrite. |

Render and write via `_vscode.write_settings`:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c "from pathlib import Path; import yaml; import _vscode; from _paths import resolve_short_name; cfg = yaml.safe_load(Path('<wiki-dir>/config.yaml').read_text(encoding='utf-8')); _vscode.write_settings(color_hex='#2d7d46', target=Path('.vscode/settings.json'), short_name=resolve_short_name(cfg, '<repo-name>'))"
```

### Phase 8 — Verify + report

Check every invariant; halt with a specific error if any fails:

- `<WIKI_PATH>` is a git repo (the cloned wiki)
- `<WIKI_PATH>/config.yaml` exists
- `<container>/wts/` exists (container-form) or `<container>/` exists (prefix-form)
- `<container>/portals/` exists (container-form)
- `<container>/portals/<repo>/` portal entry exists and points at `<hub-path>` (container-form)
- Every hub junction (entries without `<SLUG>` from `wiki/config.yaml`) exists and resolves to its expected target
- Every hardlink (from `wiki/config.yaml`) exists and shares an inode with its target
- `.gitignore` contains the mill-managed marker block with glob and anchored entries
- `hub_relative_path:` is set in `.millhouse/config.local.yaml`
- Every script in `_shortcuts.SHORTCUT_SCRIPTS` has a wrapper at `.millhouse/<script>.ps1` (and no legacy `.millhouse/<script>.py` exists)
- `PYTHONPATH` user env var contains `<CLAUDE_PLUGIN_ROOT>/scripts` (verify via `[System.Environment]::GetEnvironmentVariable('PYTHONPATH', 'User')`)
- `.millhouse/config.local.yaml` exists
- `<WIKI_PATH>/Home.md` exists and starts with `# Tasks`
- `<WIKI_PATH>/_Sidebar.md` exists and begins with `### Navigation`
- `.vscode/settings.json` exists with `titleBar.activeBackground == "#2d7d46"`

On success, print a summary:

```
mill-setup complete.

  Hub:               <HUB_PATH>
  Container:         <container>
  Portals:           <container>/portals/
  Wiki clone:        <WIKI_PATH>
  Local config:      .millhouse/config.local.yaml
  hub_relative_path: <hub_subpath>
  Tasks (Home):      <WIKI_PATH>/Home.md  (hardlinked as tasks.md)
  Sidebar:           <WIKI_PATH>/_Sidebar.md
  VS Code:           .vscode/settings.json (titleBar = #2d7d46 green)
  Shortcut wrappers: N PS1 scripts under .millhouse/
  PYTHONPATH (User): <scripts>

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
| `uv --version` fails | Halt with install instruction: `irm https://astral.sh/uv/install.ps1 | iex` |
| `git ls-remote <wiki-url>` fails | Halt with GitHub URL + instruction to create Home page |
| `<wiki-dir>` exists but not a git repo | Halt — never overwrite user data |
| Junction points elsewhere | Halt with remove-and-rerun instruction |
| Push of `Home.md` fails (network / auth) | Halt; user fixes network and re-runs |
| A Python helper raises | Show the traceback from the Python invocation and halt |

## Idempotency

Every phase checks current state before acting. Re-running after a partial or complete setup is always safe:

- Wiki already cloned → pulls latest.
- `wiki/config.yaml` present → skipped (Phase 3.1).
- `portals/` and main-worktree portal entry present → skipped (Phase 3.7).
- `create_hub_links` re-checks each junction and hardlink — skips already-correct ones (Phase 4).
- `.gitignore` marker block already up-to-date → not rewritten (Phase 4.5b).
- `hub_relative_path` already set → updated to current value (Phase 4.9).
- `config.local.yaml` present → skipped (Phase 5).
- `Home.md` non-empty (and v2-shape or user-custom) → skipped; only GitHub-default content is overwritten.
- `_Sidebar.md` regenerated unconditionally; commit only if bytes changed.
- `.vscode/settings.json` already green → skipped.
- PYTHONPATH user env var re-set to the current latest plugin version on every run.

A second `/mill-setup` run on a fully-set-up clone makes no changes and prints the same summary block.
