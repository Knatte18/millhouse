# Batch: Tests

```yaml
task: Write active-slug indicator file in hub
batch: Tests
number: 3
cards: 3
verify: uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
depends-on: [1, 2]
```

## Batch Scope

Adds unit tests for all new behaviour introduced in Batches 1 and 2. Tests for the `write_hub_active_indicator` helper go into the existing `test-spawn-core.py`; tests for indicator deletion in cleanup go into `test-cleanup.py`; the glob fallback in `find_active_slug` gets a new dedicated file `test-review-common.py`. All three test files are run by the shared `run-all.py` runner.

## Cards

### Card 7: Add `write_hub_active_indicator` tests to `test-spawn-core.py`

- **Context:**
  - `plugins/mill/unit_tests/_test_helpers.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-spawn-core.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. Import `write_hub_active_indicator` from `_spawn_core` by adding it to the existing `from _spawn_core import (...)` block at the top of the file.
  2. After the `recreate_active_junction` test section (around line 523), add a new section `# write_hub_active_indicator` with three tests:

     `test_write_hub_active_indicator_happy_path`: use `safe_temp_dir()` to create a temp hub_root with `_mill/` already present; call `write_hub_active_indicator(hub_root, "my-task")`; assert `hub_root / "_mill" / "my-task.active"` exists and `Path.is_file()` returns True.

     `test_write_hub_active_indicator_idempotent`: call `write_hub_active_indicator` twice with the same arguments; assert no exception and the indicator file exists after both calls.

     `test_write_hub_active_indicator_creates_mill_dir`: use `safe_temp_dir()` to create a temp hub_root but do NOT pre-create `_mill/`; call `write_hub_active_indicator(hub_root, "my-task")`; assert both `hub_root / "_mill"` and `hub_root / "_mill" / "my-task.active"` exist.

  3. Add calls to all three tests in the `if __name__ == "__main__":` block (or create one if absent).
- **Commit:** `test(spawn-core): add write_hub_active_indicator unit tests`

### Card 8: Add indicator deletion tests to `test-cleanup.py`

- **Context:**
  - `plugins/mill/unit_tests/test-cleanup.py`
  - `plugins/mill/scripts/millpy-cleanup.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-cleanup.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. At the end of `test-cleanup.py`, add a new section `# Hub active indicator deletion` with three tests. Study the existing test for `_apply_inplace_record` (around line 565) and `apply_plan` for the mocking pattern used for git/junction calls.

     `test_apply_inplace_deletes_hub_indicator`: create a temp `hub_root` with `hub_root/_mill/<slug>.active` present; mock all subprocess and junction calls so `_apply_inplace_record` does not need a real git repo (mock `_subprocess_util.run` to succeed for `checkout` and `branch -D`, mock `_junction.remove` to no-op); call `_apply_inplace_record(record, hub_root, task_branch, cfg={})`; assert `hub_root / "_mill" / f"{record.slug}.active"` no longer exists.

     `test_apply_worktree_deletes_hub_indicator`: same structure for `_apply_worktree_record`; mock `_worktree.remove_safe` and `_junction.remove` to no-op (worktree_path may be None or nonexistent); assert indicator gone after the call.

     `test_apply_inplace_indicator_missing_ok`: do NOT create the indicator file; call `_apply_inplace_record` with the same mocks; assert no `FileNotFoundError` is raised.

  2. Import `tempfile` if not already imported (it is already imported in the file).
  3. Add calls to all three tests in the `if __name__ == "__main__":` block.
- **Commit:** `test(cleanup): add hub active indicator deletion tests`

### Card 9: New `test-review-common.py` for glob fallback

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_marker.py`
  - `plugins/mill/unit_tests/test-marker.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-review-common.py`
- **Deletes:** none
- **Requirements:**
  1. File header: follow the pattern of other test files — `HUB = Path(__file__).resolve().parent.parent.parent.parent`, `sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))`.
  2. Import `find_active_slug` and `ReviewError` from `_review_common`; import `_marker` for `MarkerError`; use `unittest.mock.patch` and `tempfile.TemporaryDirectory`.
  3. Add five tests:

     `test_find_active_slug_branch_success`: patch `_marker.slug_from_branch` to return `"my-task"`; call `find_active_slug(Path("/fake"), Path("/wiki"), {})`; assert returns `"my-task"`.

     `test_find_active_slug_one_active_file`: use `TemporaryDirectory` for `hub_root`; create `hub_root/_mill/my-task.active`; patch `_marker.slug_from_branch` to raise `_marker.MarkerError("detached HEAD")`; call `find_active_slug(Path(hub_root), Path("/wiki"), {})`; assert returns `"my-task"`.

     `test_find_active_slug_zero_active_files`: `hub_root/_mill/` exists but is empty; patch raises `MarkerError`; assert `ReviewError` is raised and its message contains `"no active task"`.

     `test_find_active_slug_multiple_active_files`: create `_mill/task-a.active` and `_mill/task-b.active`; patch raises `MarkerError`; assert `ReviewError` is raised and its message contains `"use --slug"`.

     `test_find_active_slug_no_mill_dir`: `hub_root/_mill/` does not exist; patch raises `MarkerError`; assert `ReviewError` is raised (OSError handled gracefully, treated as zero matches).

  4. `if __name__ == "__main__":` block calls all five tests.
- **Commit:** `test(review-common): add find_active_slug glob fallback tests`

## Batch Tests

Verify with `uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py`. The runner auto-discovers `test-review-common.py` via glob, so no registration step is needed. A green run confirms all new and existing tests pass.
