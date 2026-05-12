# Batch: resolve-task-path-shim

```yaml
task: 33 (A) -- Working-dir rename + portals redesign + junction cleanup
batch: resolve-task-path-shim
number: 1
cards: 7
verify: python plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

Adds `resolve_task_path(worktree_root, cfg_relative_path) -> Path` to `_paths.py` and wires it into every caller that currently hardcodes `worktree / "task" / ...` paths for the four config-driven working-state paths (status.md, plan_dir, reviews_dir, discussion_file). This batch is purely additive — the config still says `task/` after this batch, so the shim always falls through to the `task/` path on existing worktrees. No existing behavior changes; the shim only fires when `_mill/` paths don't exist and `task/` does.

The shim's signature: `resolve_task_path(worktree_root: Path, cfg_relative_path: str) -> Path`. If `worktree_root / cfg_relative_path` exists, returns it. If `cfg_relative_path` starts with `_mill/` and the `_mill/` target is absent but the `task/` equivalent exists, returns the `task/` path and prints `[compat] falling back to task/ for <cfg_relative_path>` to stderr. Otherwise returns the `_mill/` path (caller handles missing-file).

Batch-02 (task-to-mill-rename) will update config to say `_mill/`; after that the shim provides backward compat for in-flight `task/` worktrees.

## Cards

### Card 1: Add `resolve_task_path` to `_paths.py`

- **Context:**
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/_paths.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add `resolve_task_path(worktree_root: Path, cfg_relative_path: str) -> Path` to `_paths.py`. The function: (1) computes `target = worktree_root / cfg_relative_path`; (2) if `target.exists()` returns `target`; (3) if `cfg_relative_path` contains `_mill/`, computes `fallback_rel = cfg_relative_path.replace("_mill/", "task/", 1)`, checks `fallback = worktree_root / fallback_rel`, if `fallback.exists()` prints `[compat] falling back to task/ for {cfg_relative_path!r}` to stderr and returns `fallback`; (4) returns `target` (no-fallback case). Add `"resolve_task_path"` to `__all__`. Add a one-line docstring: "Resolve config-relative path with _mill/->task/ fallback for in-flight worktrees."
- **Commit:** `feat(paths): add resolve_task_path compat shim for _mill/->/task/ fallback`

### Card 2: Wire `_review_common.resolve_path` through shim

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_review_common.resolve_path`, replace the final return statement `return active_hub / resolved_tmpl` with `return _paths.resolve_task_path(active_hub, resolved_tmpl)`. The import of `_paths` is already present. The `resolved_tmpl` string at this point already has `<SLUG>` substituted. After batch 02 updates config to say `_mill/discussion.md`, the shim will transparently fall back to `task/discussion.md` for in-flight worktrees.
- **Commit:** `fix(review): wire resolve_path through resolve_task_path shim`

### Card 3: Update `millpy-abandon.py` to use shim

- **Context:**
  - `plugins/mill/scripts/millpy-abandon.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-abandon.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Replace the hardcoded `status_path = active_hub / "task" / "status.md"` (line 58) with `status_path = _paths.resolve_task_path(active_hub, "_mill/status.md")`. Replace the literal `"task/status.md"` string in the `git add` subprocess call (line 101) with `str(status_path.relative_to(active_hub))`. The import of `_paths` is already present. After batch 02 sets config to `_mill/`, new tasks will use `_mill/status.md`; old in-flight tasks get `task/status.md` via the shim.
- **Commit:** `fix(abandon): use resolve_task_path shim for status.md path`

### Card 4: Update `millpy-implement.py` to use shim

- **Context:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `millpy-implement.py`:
  (1) Add `import _paths` (if not already present — check current imports).
  (2) Replace `status_path = project_root / "task" / "status.md"` (line 93) with `status_path = _paths.resolve_task_path(project_root, "_mill/status.md")`.
  (3) Replace the `plan_dir`-based `project_root / plan_dir / "00-overview.md"` construction (line 100): instead of `overview_path = project_root / plan_dir / "00-overview.md"` write `plan_base = _paths.resolve_task_path(project_root, plan_dir); overview_path = plan_base / "00-overview.md"`. Similarly `batch_file = plan_base / batch_entry["file"]` instead of `project_root / plan_dir / batch_entry["file"]`.
  (4) Replace the literal `"task/status.md"` in git add calls at lines 138 and 217 with `str(status_path.relative_to(project_root))`.
  Note: the cleanliness snapshot path (`project_root / "task" / f".cleanliness-snapshot-..."`) is an internal mill state file — do NOT add shim for it here. It will be renamed directly in batch 02.
- **Commit:** `fix(implement): use resolve_task_path shim for status and plan paths`

### Card 5: Update `millpy-implement-holistic.py` to use shim

- **Context:**
  - `plugins/mill/scripts/millpy-implement-holistic.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement-holistic.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `millpy-implement-holistic.py`:
  (1) Add `import _paths` (if not already present).
  (2) Replace `status_path = project_root / "task" / "status.md"` (line 77) with `status_path = _paths.resolve_task_path(project_root, "_mill/status.md")`.
  (3) Replace `overview_path = project_root / "task" / "plan" / "00-overview.md"` (line 91): first compute `plan_base = _paths.resolve_task_path(project_root, "_mill/plan/")`, then `overview_path = plan_base / "00-overview.md"`.
  (4) Replace `str(project_root / "task" / "plan" / b["file"])` (line 103 list-comp) with `str(plan_base / b["file"])` — use the `plan_base` computed above (move it before the `try` block that calls `extract_batch_index`).
  (5) Replace the literal `"task/status.md"` in the git add call (line 123) with `str(status_path.relative_to(project_root))`.
- **Commit:** `fix(implement-holistic): use resolve_task_path shim for status and plan paths`

### Card 6: Update `millpy-cleanup.py` `_read_phase` callers to use shim

- **Context:**
  - `plugins/mill/scripts/millpy-cleanup.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-cleanup.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `millpy-cleanup.py`, there are three sites that use the `_task_status` / `_legacy_status` two-candidate pattern. Replace all three with a single `_paths.resolve_task_path` call:
  (1) In `build_plan` (lines ~120-122): replace `_task_status = wt_path / "task" / "status.md"` and `_legacy_status = wt_path / "status.md"` and `_read_phase(_task_status if _task_status.exists() else _legacy_status)` with `_read_phase(_paths.resolve_task_path(wt_path, "_mill/status.md"))`.
  (2) In `_apply_inplace_record` first occurrence (lines ~307-309): replace the same two-candidate pattern for `read_parent_branch` with `_status.read_parent_branch(_paths.resolve_task_path(record.worktree_path, "_mill/status.md"))`.
  (3) In `_apply_inplace_record` second occurrence (lines ~337-339): replace the two-candidate pattern for `_read_phase` with `_read_phase(_paths.resolve_task_path(record.worktree_path, "_mill/status.md"))`.
  The import `import _paths` is already present at the top of millpy-cleanup.py.
- **Commit:** `fix(cleanup): use resolve_task_path shim in _read_phase calls`

### Card 7: Add `resolve_task_path` unit tests to `test-paths.py`

- **Context:**
  - `plugins/mill/unit_tests/test-paths.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-paths.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a `test_resolve_task_path()` function to `test-paths.py` that covers these six cases using `tempfile.TemporaryDirectory()`:
  (1) `_mill/discussion.md` exists -> returns `_mill/` path, no stderr output.
  (2) `_mill/discussion.md` absent, `task/discussion.md` present -> returns `task/` path, stderr contains `[compat]`.
  (3) Neither exists -> returns `_mill/` path, no stderr output.
  (4) `_mill/plan/` directory exists -> returns `_mill/plan/` path.
  (5) `_mill/plan/` absent, `task/plan/` present -> returns `task/plan/` path, stderr contains `[compat]`.
  (6) `cfg_relative_path` does not start with `_mill/` (e.g. `task/status.md`) -> returns `worktree_root / "task/status.md"` directly (no fallback attempted, no error).
  Call `test_resolve_task_path()` from the `main()` function alongside existing tests.
- **Commit:** `test(paths): add resolve_task_path unit tests`

## Batch Tests

Verifies the compat shim logic and that all wired callers compile and pass existing tests. Run `python plugins/mill/unit_tests/run-all.py`. All existing tests must pass unchanged; the new `test_resolve_task_path` tests must pass as well.
