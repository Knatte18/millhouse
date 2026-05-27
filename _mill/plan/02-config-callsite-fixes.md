# Batch: config-callsite-fixes

```yaml
task: "Sub-project repo (hub_relative_path) support"
batch: "config-callsite-fixes"
number: 2
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
depends-on: [1]
```

## Batch Scope

This batch repairs every wrong callsite of `_config.load_config` (11 sites) and `_review_common.load_config` (3 sites; the 4th in `millpy-review-discussion.py` is already correct), and deletes the strict-wrapper precheck functions in `millpy-claim.py` and `millpy-spawn.py`. Every fix follows the same shape: first positional arg becomes `_paths.resolve_hub_path()` (not `_paths.resolve_git_root()`). The wrapper deletions also import the loader directly (`from _config import load_config`), removing the `_strict_load_config` / `_load_config` aliases and their associated `_strict_load_config` / `_load_config` functions. The unit-test suite must remain green after this batch; no new tests are added — the changes are no-op refactors in the typical (hub == git_root) layout, and the sub-project layout is covered by batch 5's integration test.

Batch-local decisions:
- Cards are grouped by helper (one card for `_config.load_config` fixes including the two wrapper deletions; one card for `_review_common.load_config` fixes). This keeps each card to a single reviewer-tractable scope.
- Where a script already imports `_paths` (e.g., `from _paths import resolve_hub_path`), reuse that import. Where it does not, add a minimal `from _paths import resolve_hub_path` line in the existing imports block alongside `resolve_git_root` etc.

## Cards

### Card 7: fix all `_config.load_config` callsites and delete strict-wrappers

- **Context:**
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/_llm_claude.py`
  - `plugins/mill/scripts/millpy-bg.py`
  - `plugins/mill/scripts/millpy-claim.py`
  - `plugins/mill/scripts/millpy-claude-sub.py`
  - `plugins/mill/scripts/millpy-cleanup.py`
  - `plugins/mill/scripts/millpy-color.py`
  - `plugins/mill/scripts/millpy-inspect.py`
  - `plugins/mill/scripts/millpy-spawn.py`
  - `plugins/mill/scripts/millpy-status.py`
  - `plugins/mill/scripts/millpy-terminal.py`
  - `plugins/mill/scripts/millpy-vscode.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** For each script in Edits, locate the `_config.load_config` (or aliased `_load_config` / `_load_config_lenient`) call and replace its first positional argument with `_paths.resolve_hub_path()`. The replacement table from discussion.md `### _config.load_config callsites to fix`:
  - `millpy-bg.py:142` — `_config.load_config(Path(git_root), Path(git_root))` becomes `_config.load_config(_paths.resolve_hub_path(), Path(git_root))`. Second arg stays `Path(git_root)` (launcher's view of the worktree being driven).
  - `millpy-claude-sub.py:159` — `_config.load_config(git_root, git_root)` becomes `_config.load_config(_paths.resolve_hub_path(), _paths.resolve_hub_path())`.
  - `millpy-cleanup.py:600` — `_load_config(git_root, git_root)` becomes `_load_config(_paths.resolve_hub_path(), git_root)`. Second arg stays `git_root` because cleanup operates on a possibly-different worktree.
  - `millpy-color.py:90` — `_load_config(git_root, resolve_hub_path())` becomes `_load_config(resolve_hub_path(), resolve_hub_path())`.
  - `millpy-inspect.py:47` — `_config.load_config(git_root, git_root)` becomes `_config.load_config(_paths.resolve_hub_path(), _paths.resolve_hub_path())`.
  - `millpy-status.py:26` — same as inspect.
  - `millpy-terminal.py:56` — `_load_config(git_root, git_root)` becomes `_load_config(_paths.resolve_hub_path(), _paths.resolve_hub_path())`.
  - `millpy-vscode.py:183` — same as terminal.
  - `_llm_claude.py:99` — `_config.load_config(git_root, git_root)` becomes `_config.load_config(_paths.resolve_hub_path(), _paths.resolve_hub_path())`.
  Special cases:
  - `millpy-claim.py`: delete the `_strict_load_config` function (the wrapper definition around the existing aliased import). Update the import on line 47 — keep `from _config import load_config as _load_config`. Replace the call at line 168 from `_strict_load_config(git_root, resolve_hub_path())` to `_load_config(resolve_hub_path(), resolve_hub_path())`.
  - `millpy-spawn.py`: delete the `_load_config` wrapper function. Change the import on line 46 from `from _config import load_config as _load_config_lenient` to `from _config import load_config as _load_config`. Replace the call at line 111 from `_load_config(git_root, resolve_hub_path())` to `_load_config(resolve_hub_path(), resolve_hub_path())`. Remove the now-unused `_load_config_lenient` alias and any stale references in the surrounding code or docstrings.
  Re-grep each script after the edit and assert there are zero remaining `_config.load_config(` or aliased calls with `git_root` as the first positional. Verification cue: `grep -nE '(_load_config|_config\.load_config|_load_config_lenient)\s*\(\s*git_root' plugins/mill/scripts/ | head` should return no hits (only the cleanup callsite's second arg uses `git_root`, which is correct — the regex above checks position 1 only).
- **Commit:** `fix(mill-scripts): pass hub_root to _config.load_config in all callers; drop strict-load wrappers`

### Card 8: fix all `_review_common.load_config` callsites

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/millpy-review-discussion.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-review-code.py`
  - `plugins/mill/scripts/millpy-review-plan.py`
  - `plugins/mill/scripts/millpy-validate-plan.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** For each script in Edits, replace the first positional argument of the `_review_common.load_config` call with `_paths.resolve_hub_path()`. The replacement table from discussion.md `### _review_common.load_config callsites to fix`:
  - `millpy-review-code.py:76` — `load_config(project_root, mill_dir)` (where `project_root = Path.cwd()`) becomes `load_config(_paths.resolve_hub_path(), mill_dir)`. Keep `project_root = Path.cwd()` if other code paths use the variable later — only the `load_config` call's first arg changes.
  - `millpy-review-plan.py:86` — same pattern as review-code.
  - `millpy-validate-plan.py:44` — `load_config(repo_root, mill_dir)` (where `repo_root = resolve_git_root()`) becomes `load_config(_paths.resolve_hub_path(), mill_dir)`. The local `repo_root` variable may be left in place if other lines use it.
  `millpy-review-discussion.py:50` is NOT in Edits because it already calls `load_config(hub_dir, mill_dir)` with `hub_dir = resolve_hub_path()` — read it as Context to confirm the pattern matches. Re-grep after the edit: `grep -nE 'load_config\(.*(project_root|repo_root)[,\)]' plugins/mill/scripts/millpy-review-*.py plugins/mill/scripts/millpy-validate-plan.py` should return zero hits.
- **Commit:** `fix(mill-review): pass hub_root to _review_common.load_config in all callers`

## Batch Tests

The batch's `verify:` runs the full unit-test suite. No new tests are added in this batch — the callsite changes are no-op refactors in the typical (hub == git_root) layout. Coverage in the unit-test suite includes:
- `test-spawn-units.py` — exercises `millpy-spawn.py`'s top-level flow; will catch any breakage in the deleted `_load_config` wrapper.
- `test-config.py` — exercises `_config.load_config` via cards 1-3 of batch 1.
- `test-claim.py` / `test-cleanup.py` / `test-inspect.py` / similar — exercise the affected scripts where present.
- Any test that imports `_paths` and calls `resolve_hub_path` will continue to work — the helper is untouched.
The sub-project layout is covered by batch 5's integration test; this batch does not add unit-level sub-project coverage.
