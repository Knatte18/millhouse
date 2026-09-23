# Batch: cleanup-orphan-removal

```yaml
task: 'compute_baseline: use the task worktree''s own pre-edit state, not a parent-branch checkout'
batch: cleanup-orphan-removal
number: 6
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-cleanup.py
depends-on: []
```

## Batch Scope

This batch deletes `millpy-cleanup.py`'s `.scratch/verify-baseline-*` orphan-reaping surface, per Decision `delete-outright`: since no batch in this plan can produce a new orphaned transient-worktree checkout once `_verify_baseline.py` no longer creates one (batch 2), the reaper is dead weight, not a needed safety net — any leftover directory from before this task merges is removable by hand. This batch has no dependency on any other batch: it does not call into `_verify_baseline.py` or read/write any status.md baseline field, it only removes a scan that happened to be named after the mechanism batch 2 deletes.

## Cards

### Card 31: Delete _scan_orphan_baseline_dirs

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-cleanup.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Delete `_scan_orphan_baseline_dirs` in full (docstring and body). Its only caller is `build_plan`'s per-worktree loop, updated in Card 32 of this same batch.
- **Commit:** `refactor(millpy-cleanup): delete _scan_orphan_baseline_dirs`

### Card 32: Remove orphan_baseline_dirs from CleanupPlan and build_plan

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-cleanup.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Delete the `orphan_baseline_dirs: list[Path] = field(default_factory=list)` field from the `CleanupPlan` dataclass. In `build_plan`: delete the `orphan_baseline_dirs: list[Path] = []` local-variable initialization and the `orphan_baseline_dirs.extend(_scan_orphan_baseline_dirs(wt_path))` call inside the per-active-worktree loop. Drop the `orphan_baseline_dirs=orphan_baseline_dirs,` keyword argument from `build_plan`'s final `CleanupPlan(...)` construction.
- **Commit:** `refactor(millpy-cleanup): drop orphan_baseline_dirs from CleanupPlan and build_plan`

### Card 33: Delete _apply_orphan_baseline_dir and its print/apply-loop sites

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-cleanup.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Delete `_apply_orphan_baseline_dir` in full (docstring and body). In `_print_plan`: drop `plan.orphan_baseline_dirs` from the leading `if not any([...])` "Nothing to do" guard's list, and delete the `for p in plan.orphan_baseline_dirs: print(f"ORPHAN-BASELINE-DIR: ...")` loop. In `apply_plan`: delete the `for dir_path in plan.orphan_baseline_dirs: try: _apply_orphan_baseline_dir(...) except _worktree.WorktreeError as exc: ...` block in full (including its `REPORT: orphan baseline dir removal failed` stderr print and `continue`).
- **Commit:** `refactor(millpy-cleanup): delete _apply_orphan_baseline_dir and its call sites`

### Card 34: Update test-cleanup.py for the removed orphan-dir surface

- **Context:**
  - `plugins/mill/scripts/millpy-cleanup.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-cleanup.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Delete `test_scan_orphan_baseline_dirs` and `test_apply_orphan_baseline_dir` in full, and their two invocations inside `main()` (the `test_scan_orphan_baseline_dirs()` / `test_apply_orphan_baseline_dir()` calls). Add an assertion that `CleanupPlan` no longer carries an `orphan_baseline_dirs` field — e.g. construct one via its remaining fields and confirm `hasattr(plan, "orphan_baseline_dirs")` is `False`, or that passing `orphan_baseline_dirs=[...]` as a keyword argument to the `CleanupPlan` constructor raises `TypeError` — so a stray `.scratch/verify-baseline-*` directory is now simply ignored by cleanup rather than reaped.
- **Commit:** `test(millpy-cleanup): drop orphan-baseline-dir coverage, assert field removed`

## Batch Tests

`verify:` runs `test-cleanup.py` alone via `run-all.py --only` — the only test file this batch's cards edit, and it directly exercises every function this batch deletes from `millpy-cleanup.py`.
