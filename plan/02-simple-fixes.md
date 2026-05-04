# Batch: Simple script cwd fixes

```yaml
task: 'script-invocation-hygiene — Scripts: cwd not git-root, plugin cache not source repo'
batch: Simple script cwd fixes
cards: 4
verify: python plugins/mill/unit_tests/run-all.py
depends-on: [foundation]
```

## Batch Scope

This batch fixes the four mill scripts where the bug is a straightforward `git_root → resolve_hub_path()` swap for hub-state path construction. It covers `millpy-claim.py` (`.vscode/settings.json` and `.millhouse/`), `millpy-color.py` (same two paths), `millpy-fetch-issues.py` (default output `.scratch/issues.json`), and `millpy-cleanup.py` (the second direct `.millhouse/` read at L102, complementing the discover_active_worktrees fix from Card 4). Each script uses `resolve_hub_path()` from `_paths` (delivered by Card 1) instead of `git_root` for hub-state paths. The `git_root` variable is preserved at every call site for legitimate uses (e.g. `git -C <git_root> ...` subprocess calls, `resolve_main_worktree_root(git_root)` walk-up). This batch has no destination-side complexity — that lives in `spawn-worktree-dst`.

Batch-local decisions:
- `millpy-fetch-issues.py` and `millpy-cleanup.py` have no existing dedicated test files; do not create new test files (YAGNI). The fix is mechanical and the discover_active_worktrees test (Card 4) covers cleanup's primary worktree-walk path.
- The fix in `millpy-cleanup.py` L102 mirrors Card 4's two-step read pattern, not a simple `resolve_hub_path()` swap, because L102 is iterating known worktree roots (already discovered) and needs to find each worktree's hub.

## Cards

### Card 5: Fix millpy-claim.py cwd swaps

- **Reads:**
  - `plugins/mill/scripts/millpy-claim.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/unit_tests/test-millpy-claim.py`
- **Modifies:**
  - `plugins/mill/scripts/millpy-claim.py`
  - `plugins/mill/unit_tests/test-millpy-claim.py`
- **Creates:** none
- **Requirements:** Add `resolve_hub_path` to the `from _paths import ...` line. At line 127 (inside `_update_hub_vscode_title`), change `settings_path = git_root / ".vscode" / "settings.json"` to `settings_path = resolve_hub_path() / ".vscode" / "settings.json"`. At line 168 (inside `main`), change `mill_dir = git_root / ".millhouse"` to `mill_dir = resolve_hub_path() / ".millhouse"`. Leave the `git_root = resolve_git_root()` call and every `git_root`-based subprocess invocation untouched. The `_load_config(wiki_path, git_root)` call at line 169 stays as `git_root` for now — claim is already running at the hub when invoked, so passing `git_root` (subfolder-install: bigrepo root) and `resolve_hub_path()` (subfolder-install: bigrepo/src/Models) would yield different config reads after Card 2's two-step read; the correct call is `_load_config(wiki_path, resolve_hub_path())` so update L169 too. In `test-millpy-claim.py`: add a test asserting that when the test fixture sets up `cwd != git_root` (subfolder-install simulation via `os.chdir` to a subdir of the fake git root), the script reads/writes the settings file and mill dir at the cwd-rooted paths, not at the git-root-rooted paths. Mock `_subprocess_util.run` so `resolve_git_root()` returns the parent fake git root while `Path.cwd()` returns the subdir.
- **Commit:** `fix(millpy-claim): use resolve_hub_path() for .vscode and .millhouse paths`

### Card 6: Fix millpy-color.py cwd swaps

- **Reads:**
  - `plugins/mill/scripts/millpy-color.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/unit_tests/test-millpy-color.py`
- **Modifies:**
  - `plugins/mill/scripts/millpy-color.py`
  - `plugins/mill/unit_tests/test-millpy-color.py`
- **Creates:** none
- **Requirements:** Add `resolve_hub_path` to the `from _paths import ...` line. At line 80 (inside `main`), change `settings_path = git_root / ".vscode" / "settings.json"` to `settings_path = resolve_hub_path() / ".vscode" / "settings.json"`. At line 89, update the `_load_config(wiki_path, git_root)` call to `_load_config(wiki_path, resolve_hub_path())` so the loaded config matches the hub layout (same reasoning as Card 5). At line 94, change `mill_dir = git_root / ".millhouse"` to `mill_dir = resolve_hub_path() / ".millhouse"`. In `test-millpy-color.py`: add a test that, with the same `cwd != git_root` fixture pattern, asserts the settings file write and active-marker read both target cwd-relative paths.
- **Commit:** `fix(millpy-color): use resolve_hub_path() for .vscode and .millhouse paths`

### Card 7: Fix millpy-fetch-issues.py cwd swap

- **Reads:**
  - `plugins/mill/scripts/millpy-fetch-issues.py`
  - `plugins/mill/scripts/_paths.py`
- **Modifies:**
  - `plugins/mill/scripts/millpy-fetch-issues.py`
- **Creates:** none
- **Requirements:** Add `resolve_hub_path` to the `from _paths import ...` line. At line 62, change `out = git_root / ".scratch" / "issues.json"` to `out = resolve_hub_path() / ".scratch" / "issues.json"`. The `if args.out` branch (which uses an explicit override) is untouched. The `git_root = resolve_git_root()` call at line 57 stays — it remains a legitimate hint for "is this a git repo at all" even though no other path is constructed from it after the fix. (If `resolve_git_root()` becomes dead code after this change, leave it; removing it is out of scope.) Do not create a new test file for this script — the fix is a one-line swap and the discussion's testing list does not include `test-millpy-fetch-issues.py`.
- **Commit:** `fix(millpy-fetch-issues): use resolve_hub_path() for default .scratch/issues.json output`

### Card 8: Fix millpy-cleanup.py L102 direct read

- **Reads:**
  - `plugins/mill/scripts/millpy-cleanup.py`
  - `plugins/mill/scripts/_active.py`
- **Modifies:**
  - `plugins/mill/scripts/millpy-cleanup.py`
- **Creates:** none
- **Requirements:** At line 102 (inside the `for wt_path in active_worktrees` loop in `build_plan`), replace the direct `_active.read_all(wt_path / ".millhouse")` with a two-step stub-aware read: (1) read stub at `wt_path / ".millhouse" / "config.local.yaml"` for `hub_relative_path` (default `"."`; missing file or parse error → `"."`); (2) compute `hub_mill_dir = wt_path / hub_subpath / ".millhouse"` (or `wt_path / ".millhouse"` when `"."`); (3) call `_active.read_all(hub_mill_dir)` and keep the existing `except _active.ActiveError: continue` flow. Use `yaml.safe_load` for the stub read and wrap parse errors as a fall-through to `hub_subpath = "."`. Do not extract this into a private helper — duplicating the 4-line pattern across cleanup, _spawn_core, and _config is acceptable per CLAUDE.md's "three similar lines is better than premature abstraction" guidance. The L73 use of `discover_active_worktrees` is already fixed by Card 4; do not re-fix it. No new test file (per Batch Scope).
- **Commit:** `fix(millpy-cleanup): use two-step stub-aware read at direct .millhouse read`

## Batch Tests

Verify command: `python plugins/mill/unit_tests/run-all.py`

Covers: `test-millpy-claim.py` (Card 5), `test-millpy-color.py` (Card 6). Cards 7 and 8 have no dedicated test surface and are verified by the absence of regressions in run-all.py — particularly the `discover_active_worktrees` test from Card 4, which exercises the same two-step pattern that Card 8 applies inline. After this batch, manual smoke verification: run mill-claim and mill-color from a hub directory; observe `.vscode/settings.json` and `.millhouse/` are read/written at the hub, not at any parent git toplevel.
