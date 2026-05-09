# Batch: integration-tests

```yaml
task: Drop active.slug.md marker
batch: integration-tests
number: 3
cards: 3
verify: null
depends-on: [2]
```

## Batch Scope

Update the three integration tests under `plugins/mill/integration_tests/` that reference the marker file. These tests are not run by `run-all.py` (which only discovers `unit_tests/test-*.py`), so they are not blocked by Batch 2's verify — but they import / write the marker today and would fail when invoked manually. This batch keeps them runnable.

`verify: null` because the integration tests require a real `git` and the dev workflow runs them ad hoc, not in the standard suite. Each card commits the affected file independently. The implementer should run each updated integration test after editing it (`uv run --project plugins/mill python plugins/mill/integration_tests/test-<x>.py`) to confirm it still passes the scenarios it covers — but that's manual, not gated.

## Cards

### Card 27: drop marker assertions from `integration_tests/test-spawn.py`

- **Context:**
  - `plugins/mill/scripts/millpy-spawn.py`
  - `plugins/mill/scripts/_spawn_core.py`
  - `plugins/mill/scripts/_marker.py`
- **Edits:**
  - `plugins/mill/integration_tests/test-spawn.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Drop the marker-existence assertion block at lines 200-205: `marker_path = worktree / ".millhouse" / "active.slug.md"; _assert(marker_path.exists(), ...)` plus the `marker_text` content check that follows. Replace with: assert `discover_active_worktrees` returns the new worktree (build `home_tasks` via the same Home.md the test sets up; pass `branch_prefix` from cfg). Drop `import _active` if unused. The surrounding spawn-flow assertions (the worktree dir exists, branch is checked out, Home.md is `[active]`, status.md is committed) stay intact.
- **Commit:** `test(int-spawn): drop marker assertions; assert discover finds the new worktree`

### Card 28: drop marker writes from `integration_tests/test-merge.py`

- **Context:**
  - `plugins/mill/scripts/millpy-cleanup.py`
  - `plugins/mill/scripts/_marker.py`
  - `plugins/mill/scripts/_inplace.py`
- **Edits:**
  - `plugins/mill/integration_tests/test-merge.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Drop the marker-write blocks at lines 187 (comment about `.millhouse on hub with wiki junction + active.slug.md`), 212 (comment), and 222 (`(wt_mill / "active.slug.md").write_text(...)`). Replace the manual marker write with branch+Home.md state setup: ensure the worktree's git checkout is on `<branch_prefix><slug>` and the Home.md the test wrote contains the slug at `[active]`. Drop `import _active` if unused. Verify the rest of the merge-integration scenario still flows (the test sets up a worktree, runs mill-merge, asserts squash-merge + cleanup).
- **Commit:** `test(int-merge): replace marker writes with branch+Home.md state`

### Card 29: drop `_active.write` from `integration_tests/test-abandon.py`

- **Context:**
  - `plugins/mill/scripts/millpy-abandon.py`
  - `plugins/mill/scripts/_marker.py`
- **Edits:**
  - `plugins/mill/integration_tests/test-abandon.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Drop the `_active.write(mill_dir, slug=slug, task_title="Test abandon task", ...)` call at line 103. Ensure the test's worktree has the right branch checked out and the test's Home.md contains the slug at `[active]` so `mill-abandon`'s `_marker.slug_from_branch` succeeds. Drop `import _active` if unused.
- **Commit:** `test(int-abandon): replace _active.write with branch+Home.md state`

## Batch Tests

`verify: null`. Manual run-through expected:

```bash
uv run --project plugins/mill python plugins/mill/integration_tests/test-spawn.py
uv run --project plugins/mill python plugins/mill/integration_tests/test-merge.py
uv run --project plugins/mill python plugins/mill/integration_tests/test-abandon.py
```

Each must exit 0. The integration tests use real `git` and a `.scratch/` working directory; they are slow and not part of the standard CI sweep.
