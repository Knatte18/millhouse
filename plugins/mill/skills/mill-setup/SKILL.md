---
name: mill-setup
description: Initialise mill in a fresh primary-clone directory. Creates the wiki clone, seeds wiki/config.yaml, creates hub junctions and hardlinks, seeds config.local.yaml and Home.md, and sets VS Code window colour. Idempotent — safe to re-run after a partial setup.
argument-hint: "[--from-url <url>] [--branch <name>]"
---

# mill-setup

> Wiki access: never `cd .wiki/`. Use the documented helpers — see CLAUDE.md `## Wiki access`.

Bootstrap the mill infrastructure from nothing. Produces a working `.millhouse/` + wiki + container layout in the current working clone.

## Usage

- `/mill-setup` — default GitHub-wiki path (derives `<origin>.wiki.git` from the primary clone's origin URL and clones the remote default branch). Behaviour unchanged from pre-flags state.
- `/mill-setup --from-url https://github.com/Org/shared.git --branch wiki/millhouse` — clones the named branch from a separate repo (one-repo-many-branches pattern). If the branch does not yet exist on remote, mill-setup initialises a local orphan branch and the first commit (Phase 3.1) pushes it.
- `/mill-setup --from-url https://github.com/Org/shared.git` — clones from a separate repo at its remote HEAD branch (no `-b` passed to `git clone`).
- `/mill-setup --branch wiki/millhouse` — applies a branch override to the default `<origin>.wiki.git` URL. Edge case but supported; branch is persisted to `config.local.yaml` for re-runs.

## When to invoke

- First-time setup of a hub clone on a new machine
- After a crash or partial setup
- When `.wiki` junction is missing or broken

## Preconditions

- `cwd` is the hub directory inside a container (typically `<container>/wts/<repo>/`)
- `git remote get-url origin` returns a valid URL
- `uv` is installed (`uv --version` exits 0); install via `irm https://astral.sh/uv/install.ps1 | iex`
- `${CLAUDE_PLUGIN_ROOT}/scripts/` contains `_junction.py`, `_wiki.py`, `_subprocess_util.py`, `_render.py`, `_setup.py`
- `${CLAUDE_PLUGIN_ROOT}/templates/config.local.yaml`, `${CLAUDE_PLUGIN_ROOT}/templates/mill-config.yaml`, `${CLAUDE_PLUGIN_ROOT}/templates/mill-agents.yaml`, and `${CLAUDE_PLUGIN_ROOT}/templates/Home.md` exist

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

mill-setup is the bootstrapper that **creates** the global `PYTHONPATH` Windows user environment variable. That variable does not exist in the current process (or in any child process spawned during this session) until Phase 4.7 completes and a new shell is opened. The mill convention is to invoke the venv Python binary directly with an explicit `PYTHONPATH=` shell prefix on every call — this works whether the global env var is set or not:

```bash
# WRONG — invokes from source tree
PYTHONPATH="plugins/mill/scripts" uv run --project plugins/mill python -c "..."

# RIGHT — invokes from cache (the canonical mill-script form, shared with every other mill SKILL.md)
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" -c "..."
```

This direct-binary form is used by every mill SKILL.md (mill-go uses an equivalent form with `$MILL_PYTHON`, an alias defined in its Step 0 block). The source-tree form (`uv run --project plugins/mill ...`) remains the documented exception for cases where the cache path is unavailable — for example, running unit tests from the millhouse repo itself.

Helpers used by this skill: `_setup` (Phase 4 — `create_hub_links`), `_gitignore` (Phase 4.5b), `_shortcuts` (Phase 4.7), `_sidebar` (Phase 6a), `_vscode` (Phase 7), `_render` (transitively via `_vscode` and `_shortcuts`), `_wiki` (Phase 3, 3.1, 6, 6a).

## Phases

Run in order. Stop on the first hard error and report it. Every phase is idempotent — re-checks current state before acting.

### Phase 0 — Parse arguments

Read `$ARGUMENTS`. Token-walk left-to-right:

- `--from-url <url>` — the next token is the wiki URL. Store as `<cli-from-url>`. May appear at most once.
- `--branch <name>` — the next token is the branch name. Store as `<cli-branch>`. May appear at most once.
- Any other token: halt with usage hint:

  > Unknown argument: `<token>` in `$ARGUMENTS`
  >
  > usage: `/mill-setup [--from-url <url>] [--branch <name>]`

Store `<cli-from-url>` and `<cli-branch>` (each may be empty / unset).

Optionally pre-load `.millhouse/config.local.yaml` now (if it exists) and read `wiki.repo_url:` / `wiki.branch:` into `<config-repo-url>` and `<config-branch>`, so Phase 1 can apply precedence without re-reading the file.

### Phase 1 — Derive wiki URL

0. **Check `uv` is installed:**

   ```bash
   uv --version
   ```

   If exit code is non-zero, halt with:

   > uv is not installed. Install via PowerShell: `irm https://astral.sh/uv/install.ps1 | iex` — then re-run /mill-setup.

1. `git remote get-url origin` → `<origin-url>` (still computed; needed for the derived fallback and for Phase 7's `<repo-name>` resolution).
2. Compute effective URL and branch via precedence:
   - **Effective URL (`<wiki-url>`):** `<cli-from-url>` if set; else `wiki.repo_url:` from `.millhouse/config.local.yaml` if present; else strip trailing `.git` from `<origin-url>` and append `.wiki.git` (e.g. `https://github.com/org/repo.git` → `https://github.com/org/repo.wiki.git`).
   - **Effective branch (`<wiki-branch>`):** `<cli-branch>` if set; else `wiki.branch:` from config if present; else `None` (use remote HEAD).
   - **Source flag (`<effective-from-url-source>`):** `'cli'` when `<cli-from-url>` or `<cli-branch>` was supplied on the CLI; `'config'` when the effective URL came from `.millhouse/config.local.yaml`; `'derived'` when the `<origin>.wiki.git` fallback was used.
3. Store `<wiki-url>`, `<wiki-branch>`, `<effective-from-url-source>`, and `<container>` (the parent of `wts/`, or the parent of `cwd` in prefix-form).

### Phase 2 — Verify wiki is reachable and non-empty

Run `git ls-remote <wiki-url>`. If it fails (exit non-zero), halt with a conditional message based on `<effective-from-url-source>`:

- When `<effective-from-url-source> == 'derived'` (no CLI flag, no config override — the default GitHub-wiki path):

  > The wiki at `<wiki-url>` is unreachable or empty. Open `https://github.com/<owner>/<repo>/wiki` on GitHub, create the Home page with any content, then re-run `/mill-setup`.
  >
  > (GitHub does not create the wiki git repo until the first page is saved.)

- When `<effective-from-url-source>` is `'cli'` or `'config'`:

  > The wiki URL `<wiki-url>` is unreachable. Check the URL, your network, and your credentials, then re-run `/mill-setup`.

### Phase 3 — Clone or fast-forward the wiki at `<wiki-dir>`

First compute `<wiki-dir>` using the sibling-path helper — this yields `<container>/wiki/` in container-form, otherwise `<container>/<repo>.wiki/`. Use the printed path as `<wiki-dir>` for the remainder of mill-setup:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" "${CLAUDE_PLUGIN_ROOT}/scripts/_sibling.py" wiki "<hub-path>"
```

`<hub-path>` is derived via `git rev-parse --show-toplevel`. Users can override via `.millhouse/config.local.yaml`'s `wiki_path:` key.

After `<wiki-dir>` is computed, call `_wiki.clone_or_init`:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" -c "
from pathlib import Path
import _wiki, json
result = _wiki.clone_or_init(
    url=r'<wiki-url>',
    branch=r'<wiki-branch>' if r'<wiki-branch>' else None,
    dest=Path(r'<wiki-dir>').resolve(),
)
print(json.dumps(result))
"
```

When rendering the command, substitute `<wiki-url>` and `<wiki-dir>` with their computed values. For `<wiki-branch>`: when it is set (e.g. `wiki/millhouse`), the ternary evaluates to the string; when `<wiki-branch>` is unset, write `branch=None` directly instead. Log the returned JSON (`"action"`: `"cloned"` | `"pulled"` | `"initialized"`; `"branch_existed_on_remote"`: `true` | `false` | `null`).

If the helper raises `WikiSetupError` (dest is not a git repo, URL mismatch, branch mismatch, clone or init failure): halt and surface the exception message verbatim. The message names the offending paths so the user can fix manually.

If the helper raises `WikiPushError` (from the pull path — `git pull --ff-only` failed due to network failure, credentials, or non-fast-forward / local divergence): halt and instruct the user to inspect and fix the wiki dir manually.

### Phase 3.0b — Migrate wiki config and agents to hub/plugin

This phase invokes `millpy-migrate-config.py` to migrate existing wiki-based config to the hub worktree and plugin templates. The script handles three concerns: (a) copy `wiki/config.yaml` to the hub root if not yet present, (b) delete the wiki copy and push the change, (c) diff `wiki/agents.yaml` against the plugin template and either delete (identical) or warn-and-skip (different).

**Ordering constraint:** Phase 3.0b MUST execute before Phase 3.1. If Phase 3.1 ran first against a hub with an existing `wiki/config.yaml`, the operator's custom config would be overwritten by the plugin template's defaults and then silently deleted from the wiki. Do NOT reorder these phases.

Run the migration script:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-migrate-config.py"
```

The operator should expect to see in the output:
- One of: `[migrate] mill-config.yaml staged` (copy happened), `[migrate] mill-config.yaml already exists` (skipped), or `[migrate] no wiki/config.yaml` (nothing to migrate).
- Wiki-side cleanup: `[migrate] wiki/config.yaml deleted and pushed` (after copying) or `[migrate] no wiki/config.yaml` (nothing to delete).
- One of: `[migrate] wiki/agents.yaml identical to plugin template -- deleted and pushed`, `[migrate] wiki/agents.yaml NOT deleted` (warn case with diffs listed), or `[migrate] no wiki/agents.yaml` (nothing to migrate).
- A notice about the removed machine-config layer.

Idempotency: re-running mill-setup after a successful migration is a no-op for this phase. If the agents migration warned with diffs, copy the unique entries from the printed list into `.millhouse/agents.local.yaml` and re-run mill-setup to retry the agents step.

### Phase 3.1 — Seed mill-config.yaml at hub directory from template

1. If `<cwd>/mill-config.yaml` does not exist: copy `${CLAUDE_PLUGIN_ROOT}/templates/mill-config.yaml` → `<cwd>/mill-config.yaml` verbatim (no substitution — tokens are resolved at runtime by scripts, not at seed time). Then stage via `git add`:

   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" -c "from pathlib import Path; import shutil, _subprocess_util; shutil.copyfile(Path(r'${CLAUDE_PLUGIN_ROOT}/templates/mill-config.yaml').resolve(), Path(r'<cwd>/mill-config.yaml').resolve()); _subprocess_util.run(['git', '-C', r'<cwd>', 'add', 'mill-config.yaml']); print('mill-config.yaml staged at <cwd>/mill-config.yaml -- commit it on the main branch to land the migration')"
   ```

2. If `<cwd>/mill-config.yaml` exists: run a block-level upsert:

   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" -c "
   from pathlib import Path
   import yaml

   config_path = Path(r'<cwd>/mill-config.yaml').resolve()
   template_path = Path(r'${CLAUDE_PLUGIN_ROOT}/templates/mill-config.yaml').resolve()

   existing = yaml.safe_load(config_path.read_text(encoding='utf-8')) or {}
   template  = yaml.safe_load(template_path.read_text(encoding='utf-8')) or {}

   required_keys = ['junctions', 'paths', 'llm', 'pipeline', 'roles', 'notify', 'spawn', 'groom', 'merge']
   missing = [k for k in required_keys if k not in existing]
   if missing:
       for k in missing:
           existing[k] = template[k]
       config_path.write_text(yaml.dump(existing, allow_unicode=True, sort_keys=False), encoding='utf-8')
       print('upserted blocks:', missing)
   else:
       print('mill-config.yaml validation OK -- all required blocks present')
   "
   ```

   After running: if any blocks were upserted (i.e., `missing` was non-empty), stage and commit:

   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" -c "
   from pathlib import Path
   import _subprocess_util
   hub_root = Path(r'<cwd>').resolve()
   _subprocess_util.run(['git', '-C', str(hub_root), 'add', 'mill-config.yaml'])
   _subprocess_util.run(['git', '-C', str(hub_root), 'commit', '-m', 'chore: upsert missing mill-config.yaml blocks from template'])
   "
   ```

   Log which blocks were added (from the `print('upserted blocks:', ...)` output) so the operator can see the diff.

**Why verbatim copy:** the token placeholders (`<WIKI_PATH>` etc.) are resolved by `_junction.resolve_target` and `_wiki.read_hardlinks` at runtime. Substituting at seed time would bake in machine-specific paths. If `mill-config.yaml` already exists, the upsert step validates and fills any required top-level blocks that are missing (`paths`, `llm`, `pipeline`, `roles`, `notify`, `spawn`, `groom`, `merge`). This prevents downstream `KeyError` in mill-spawn when an older mill-config.yaml predates a required schema block.

### Phase 3.2 — Persist wiki overrides to `config.local.yaml`

Runs only when `<cli-from-url>` or `<cli-branch>` was explicitly supplied on the CLI in this run. When both came from config or derived defaults, this phase is a no-op.

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" -c "
from pathlib import Path
import _config
changed = _config.set_local_wiki_overrides(
    cfg_path=Path('.millhouse/config.local.yaml'),
    repo_url=<repo-url-or-None>,
    branch=<branch-or-None>,
)
print('config.local.yaml updated' if changed else 'config.local.yaml already correct')
"
```

When rendering the command: fill `<repo-url-or-None>` with `r'<value>'` when `--from-url` was given, `None` when only `--branch` was given. Fill `<branch-or-None>` with `r'<value>'` when `--branch` was given, `None` when only `--from-url` was given. Passing `None` for an omitted argument preserves whatever value the file already has (partial-update semantics).

Note: `.millhouse/` does not exist on a fresh install at the time this phase fires (it is created in Phase 4 by `create_hub_links`). No separate `mkdir` is needed — `_config.set_local_wiki_overrides` calls `cfg_path.parent.mkdir(parents=True, exist_ok=True)` before writing.

Note: comments in `.millhouse/config.local.yaml` are lost when this phase rewrites the file. The file is gitignored and per-machine, so the trade-off is acceptable.

Idempotency: re-running mill-setup with the same flags (or no flags after a prior persisted run) leaves the file untouched — the helper returns `False` when the on-disk content already matches the desired content.

### Phase 3.7 — Create container scaffolding

Create the `<container>/portals/` directory (if missing). Task portals are added per-task by `mill-spawn`/`mill-claim`; main worktree gets NO portal entry — adding one creates a deletion-cycle through `<container>/portals/<repo>` back to the hub when any task worktree is removed.

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" -c "
from pathlib import Path
container = Path(r'<container>').resolve()
portals = container / 'portals'
portals.mkdir(parents=True, exist_ok=True)
print(f'ensured portals dir: {portals}')
"
```

**Idempotency:** `portals.mkdir(exist_ok=True)` is a no-op if the directory already exists. The portal junction check prevents double-creation.

### Phase 4 — Create hub links (junctions + hardlinks)

Call `_setup.create_hub_links` with the hub token set (no `<SLUG>` — that is mill-spawn's concern). The helper reads both the `junctions:` and `hardlinks:` blocks from `<wiki-dir>/config.yaml`, applies the token-scope filter (silently skipping entries whose templates reference `<SLUG>`), creates all hub-scope junctions, and creates all hardlinks idempotently:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" -c "
from pathlib import Path
import json, _setup
result = _setup.create_hub_links(
    target_root=Path(r'<cwd>').resolve(),
    wiki_path=Path(r'<wiki-dir>').resolve(),
    tokens={
        'HUB_PATH':       r'<cwd>',
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
- `<cwd>` — the hub directory. mill-setup is invoked from the hub; `cwd` is the hub by construction. In subdirectory-hub mode, this differs from `git rev-parse --show-toplevel` (the repo root). Use `cwd`, not `git rev-parse --show-toplevel`, for `target_root`.
- `<container>` — parent of `wts/` (container-form) or parent of hub (prefix-form)
- `<wiki-dir>` — wiki clone path from Phase 3
- `<repo>` — repository directory name (e.g. `millhouse`)

**Do NOT add `<SLUG>`** — the token-scope filter skips junction entries that need `<SLUG>` (per-task `.active` and `.wiki` entries). Those are created by mill-spawn.

Log the created junctions and hardlinks from the returned dict so the user can verify.

### Phase 4.5b — Manage `.gitignore` marker block

Maintains the `# === mill-managed ... # === end mill-managed ===` block in the hub's `.gitignore`.

Compute `<hub-gitignore>` as `<hub-path>/.gitignore` (same path in both container-form and prefix-form).

Call `_gitignore.upsert`:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" -c "
from pathlib import Path
import _gitignore
hub_gi = Path(r'<hub-gitignore>').resolve()
changed = _gitignore.upsert(hub_gi, _gitignore.GLOB_ENTRIES)
print('hub .gitignore:', 'updated' if changed else 'already up to date')
"
```

Log the result.

### Phase 4.7 — PS1 shortcut wrappers

Creates `.millhouse/<script>.ps1` forwarders for every user-callable mill script. Each wrapper hardcodes the path of the currently-latest plugin cache entry and delegates to the real script via `uv run --active`.

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" -c "
import os
import _shortcuts
from pathlib import Path
cache = Path(os.environ['USERPROFILE']) / '.claude' / 'plugins' / 'cache' / 'millhouse' / 'mill'
latest_path = max((p for p in cache.iterdir() if p.is_dir()), key=lambda p: p.name)
written = _shortcuts.write_all(Path('.millhouse'), latest_path)
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

**Note:** After running `update-plugins.ps1` to install a new plugin version, re-run `/mill-setup` to refresh PYTHONPATH and the PS1 wrappers to the new version. If upgrading from a pre-PS1 hub (one where `.millhouse/` still contains `.py` wrappers), re-run `/mill-setup` — Phase 4.7 is idempotent and will replace the `.py` wrappers with `.ps1` wrappers in a single pass, and Phase 8 will verify their absence.

### Phase 4.8 — Venv activation in $PROFILE

Writes a marker-delimited venv activation block to PowerShell `$PROFILE` so that
`uv run --active` works in every new shell session without manual activation.
Idempotent: re-run replaces the existing block (if any). Creates `$PROFILE` if
it does not exist.

```powershell
$profilePath = $PROFILE
$latest = (Get-ChildItem "$HOME\.claude\plugins\cache\millhouse\mill" -Directory | Sort-Object Name -Descending | Select-Object -First 1).FullName
$activateLine = ". `"$latest\.venv\Scripts\Activate.ps1`""
$startMarker = "# mill-venv-start — managed by mill-setup, do not edit manually"
$endMarker = "# mill-venv-end"
$block = "$startMarker`n$activateLine`n$endMarker"

if (-not (Test-Path $profilePath)) {
    New-Item -ItemType File -Path $profilePath -Force | Out-Null
    Write-Host "[mill-setup] Created $profilePath"
}
$content = Get-Content $profilePath -Raw -ErrorAction SilentlyContinue
if ($content -match [regex]::Escape($startMarker)) {
    $content = $content -replace "(?s)$([regex]::Escape($startMarker)).*?$([regex]::Escape($endMarker))", $block
    Set-Content $profilePath $content -NoNewline
    Write-Host "[mill-setup] Updated mill-venv block in $profilePath"
} else {
    Add-Content $profilePath "`n$block"
    Write-Host "[mill-setup] Added mill-venv block to $profilePath"
}
```

Log `Updated mill-venv block in <path>` or `Added mill-venv block to <path>` per the script output.

**Note:** This phase hardcodes the path of the currently-latest cache entry into `$PROFILE`. After running `update-plugins.ps1` to install a new plugin version, re-run `/mill-setup` — Phase 4.8 is idempotent and will update the activation path to the new version.

### Phase 4.9 — Seed `hub_relative_path` in `config.local.yaml`

The `hub_relative_path` key tells mill-terminal and mill-vscode where the effective hub directory is within the worktree. Write it before seeding `config.local.yaml` (Phase 5) so it appears in the seeded file if the file doesn't exist yet, and update it if the file already exists.

Compute the value:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" -c "
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
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" -c "
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
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" -c "from pathlib import Path; import _wiki; _wiki.write_commit_push(Path(r'<wiki-dir>').resolve(), ['Home.md'], '<commit-msg>')"
   ```

**GitHub-default detection:** read the file, strip outer whitespace, match the pattern `^Welcome to the .+ wiki!$` (single line).

### Phase 6a — Initialise `_Sidebar.md` via `_sidebar.regenerate()`

Regenerate the wiki sidebar every time mill-setup runs:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" -c "from pathlib import Path; import _sidebar; _sidebar.regenerate(Path(r'<wiki-dir>').resolve())"
```

Then commit + push if the file changed:

1. Check `git -C <wiki-dir> status --porcelain _Sidebar.md`.
2. If nothing printed: already correct — skip the commit.
3. Otherwise commit:

   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" -c "from pathlib import Path; import _wiki; _wiki.write_commit_push(Path(r'<wiki-dir>').resolve(), ['_Sidebar.md'], 'chore: regenerate _Sidebar.md')"
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
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" -c "from pathlib import Path; import yaml; import _vscode; from _paths import resolve_short_name; cfg = yaml.safe_load(Path(r'<cwd>/mill-config.yaml').read_text(encoding='utf-8')); _vscode.write_settings(color_hex='#2d7d46', target=Path('.vscode/settings.json'), short_name=resolve_short_name(cfg, '<repo-name>'))"
```

### Phase 8 — Verify + report

Check every invariant; halt with a specific error if any fails:

- `<WIKI_PATH>` is a git repo (the cloned wiki)
- `<cwd>/mill-config.yaml` exists
- `<container>/wts/` exists (container-form) or `<container>/` exists (prefix-form)
- `<container>/portals/` exists (container-form)
- `hub/.portals` exists and resolves to `<container>/portals/`
- Every hub junction (entries without `<SLUG>` from `wiki/config.yaml`) exists and resolves to its expected target
- `.gitignore` contains the mill-managed marker block with glob entries
- `hub_relative_path:` is set in `.millhouse/config.local.yaml`
- Every script in `_shortcuts.SHORTCUT_SCRIPTS` has a wrapper at `.millhouse/<script>.ps1` (and no legacy `.millhouse/<script>.py` exists)
- `PYTHONPATH` user env var contains `<CLAUDE_PLUGIN_ROOT>/scripts` (verify via `[System.Environment]::GetEnvironmentVariable('PYTHONPATH', 'User')`)
- `$PROFILE` contains the `# mill-venv-start` / `# mill-venv-end` block (verify via `Select-String -Path $PROFILE -Pattern "mill-venv-start" -Quiet`)
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
  Profile activation: $PROFILE — mill-venv-start block present

Junctions (from mill-config.yaml):
  Hub-scope (created now):
    <path-a> -> <resolved-target-a>
  Per-worktree (created by mill-spawn):
    <path-c> -> <template-c>    (contains <SLUG>)

Next: /mill-add <slug> --title "..." [--summary "..."] [--proposal-body "..."] to add tasks, /mill-status to list them.
```

## Error conditions

| Condition | Action |
|---|---|
| `uv --version` fails | Halt with install instruction: `irm https://astral.sh/uv/install.ps1 | iex` |
| `git ls-remote <wiki-url>` fails | Halt with GitHub URL + instruction to create Home page |
| `<wiki-dir>` exists but not a git repo | Halt — never overwrite user data |
| `clone_or_init` raises `WikiSetupError` (dest is not a git repo / URL mismatch / branch mismatch / clone or init failure) | Halt with the exception message verbatim. The helper's message names the offending paths; instruct the user to fix manually. |
| Junction points elsewhere | Halt with remove-and-rerun instruction |
| Push of `Home.md` fails (network / auth) | Halt; user fixes network and re-runs |
| A Python helper raises | Show the traceback from the Python invocation and halt |
| Unknown CLI argument | Halt with usage hint (Phase 0). |

## Idempotency

Every phase checks current state before acting. Re-running after a partial or complete setup is always safe:

- Wiki already cloned → pulls latest.
- `wiki/config.yaml` present → block-level upsert run; commit only if missing blocks were added (Phase 3.1).
- `portals/` dir present → created by Phase 4 via `_setup.create_hub_links` (idempotent via `exist_ok=True` on the junction target).
- `create_hub_links` re-checks each junction and hardlink — skips already-correct ones (Phase 4).
- `.gitignore` marker block already up-to-date → not rewritten (Phase 4.5b).
- `hub_relative_path` already set → updated to current value (Phase 4.9).
- `config.local.yaml` present → skipped (Phase 5).
- Phase 3.2's persisted `wiki.repo_url` / `wiki.branch` block is rewritten only when the on-disk values differ from the effective CLI values. Re-runs with matching flags (or no flags after a prior persisted run) make no change.
- `Home.md` non-empty (and v2-shape or user-custom) → skipped; only GitHub-default content is overwritten.
- `_Sidebar.md` regenerated unconditionally; commit only if bytes changed.
- `.vscode/settings.json` already green → skipped.
- PYTHONPATH user env var re-set to the current latest plugin version on every run.

A second `/mill-setup` run on a fully-set-up clone makes no changes and prints the same summary block.
