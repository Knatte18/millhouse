# Batch: foundation

```yaml
task: "46 (A) — Home.md state machine + split mill-merge teardown into mill-cleanup"
batch: foundation
number: 1
cards: 6
verify: "python plugins/mill/unit_tests/test-tasks-md.py && python plugins/mill/unit_tests/test-marker.py && python plugins/mill/unit_tests/test-worktree.py"
depends-on: []
```

## Batch Scope

This batch installs the low-level invariants every other batch builds on: the Home.md parser learns two new phases (`ready-to-merge`, `pr-pending`); `_marker.slug_from_branch` stops gating on `[active]`-only Home.md state; and `_worktree.remove_safe` classifies the Windows NTFS `Invalid argument` error as a lock condition. Each change ships with its unit-test extension. After this batch, batches 2 and 3 can run in parallel: batch 2 emits SKILL.md text that references the new phases; batch 3 reads/writes them in `millpy-cleanup.py`. Cards are split per file (one production card + one test card) so the implementer can apply TDD ordering — write the failing test first, then the production change, then watch the test pass. Card numbering is 1–6 and continues at 7 in batch 2.

## Cards

### Card 1: Extend `_tasks_md.py` phase vocabulary

- **Context:**
  - `plugins/mill/unit_tests/test-tasks-md.py`
- **Edits:**
  - `plugins/mill/scripts/_tasks_md.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plugins/mill/scripts/_tasks_md.py`, extend two module-level constants to recognise the new Home.md phase markers introduced by this task. (a) In the `_HEADING_RE` compiled regex, change the alternation `(?: \[(?P<phase>s|active|done|abandoned)\])?` so it accepts `s|active|ready-to-merge|pr-pending|done|abandoned`. (b) In the `_VALID_PHASES` tuple, add `"ready-to-merge"` and `"pr-pending"` between `"active"` and `"done"`. Update the module docstring's bullet list of accepted phases ("Phases: ``None`` (unmarked backlog), …") to include the two new values; keep the docstring's heading-syntax examples unchanged. Do NOT modify the `Task` dataclass `phase` field's type annotation — `str | None` already covers the new values.
- **Commit:** `feat(tasks-md): add [ready-to-merge] and [pr-pending] to Home.md phase vocabulary`

### Card 2: Test new phases in `_tasks_md`

- **Context:**
  - `plugins/mill/scripts/_tasks_md.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-tasks-md.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Extend `plugins/mill/unit_tests/test-tasks-md.py` `main()` with new assertions covering the phases added in card 1. After the existing `claim(sample, "task-one")` block, add a block that calls `set_phase(sample, "task-one", "ready-to-merge")` and asserts that `parse()` of the result yields `phase == "ready-to-merge"` for `task-one`. Mirror the same for `"pr-pending"`. Add a parse-only fixture: a Home.md string containing both `[ready-to-merge]` and `[pr-pending]` markers on different slugs and assert `parse()` returns the expected phases. Add a failing-validation block: `set_phase(sample, "task-one", "invalid-phase")` must raise `ValueError`; this case may already exist for an unrelated invalid phase — leave existing assertions intact. Use the existing PASS/print pattern; do not introduce new test infrastructure.
- **Commit:** `test(tasks-md): cover [ready-to-merge] and [pr-pending] parse/set_phase`

### Card 3: Relax `_marker.slug_from_branch` phase check

- **Context:**
  - `plugins/mill/unit_tests/test-marker.py`
  - `plugins/mill/scripts/_tasks_md.py`
- **Edits:**
  - `plugins/mill/scripts/_marker.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plugins/mill/scripts/_marker.py`, modify `slug_from_branch` (currently lines 28–67) so it no longer raises `MarkerError` when `task.phase != "active"`. Delete the entire `if task.phase != "active": raise MarkerError(f"task {slug!r} is not [active] in Home.md (phase={task.phase!r})")` block (currently lines 63–66). Keep the preceding existence check `if task is None: raise MarkerError(f"branch slug {slug!r} not present in Home.md")` unchanged. Update the module docstring's "Raises" line in `slug_from_branch`: replace "On detached HEAD, prefix mismatch, missing slug, or slug not in [active] phase." with "On detached HEAD, prefix mismatch, or missing slug." Do NOT modify `task_data` — it calls `slug_from_branch` and inherits the relaxed behaviour automatically.
- **Commit:** `refactor(marker): drop [active]-only phase check from slug_from_branch`

### Card 4: Test relaxed marker phase acceptance

- **Context:**
  - `plugins/mill/scripts/_marker.py`
  - `plugins/mill/unit_tests/_test_helpers.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-marker.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Extend `plugins/mill/unit_tests/test-marker.py` so every non-`active` phase has a success-case test (the relaxation now accepts them all). Final post-card state: five tests named `test_slug_from_branch_ready_to_merge`, `test_slug_from_branch_pr_pending`, `test_slug_from_branch_done`, `test_slug_from_branch_phase_abandoned`, `test_slug_from_branch_phase_none` — each follows the existing `test_slug_from_branch_happy_path` pattern but passes `phase="ready-to-merge"`, `phase="pr-pending"`, `phase="done"`, `phase="abandoned"`, and `phase=None` respectively to `_test_helpers._make_task_worktree`, and each asserts the returned slug equals `"foo"`. Procedure: search the file for any existing test that asserts `MarkerError` for a non-active phase (likely named `test_slug_from_branch_phase_abandoned`, `test_slug_from_branch_phase_none`, `test_slug_from_branch_phase_done`) and either delete it or rewrite its body to assert success; if multiple tests now cover the same phase (e.g. a rewritten `test_slug_from_branch_phase_done` PLUS a new `test_slug_from_branch_done`), keep only ONE per phase — prefer the names listed in the final-state set above (`test_slug_from_branch_done`, not `test_slug_from_branch_phase_done`). Retain the detached-HEAD and unknown-slug failure tests unchanged. Register the final five tests in `main()` (if present) or in whatever runner pattern the file uses.
- **Commit:** `test(marker): cover slug_from_branch for ready-to-merge, pr-pending, done`

### Card 5: Classify Windows `Invalid argument` as worktree lock

- **Context:**
  - `plugins/mill/unit_tests/test-worktree.py`
- **Edits:**
  - `plugins/mill/scripts/_worktree.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plugins/mill/scripts/_worktree.py`, modify the `_lock_patterns` tuple inside `remove_safe` (currently line 254) to include `"Invalid argument"`. Change `_lock_patterns = ("Permission denied", "is in use", "Access is denied")` to `_lock_patterns = ("Permission denied", "is in use", "Access is denied", "Invalid argument")`. Update the docstring of `WorktreeLockedError` (line 41) so it reads: `"""Raised when a worktree directory cannot be removed because it is in use (NTFS CWD lock, PermissionError, or Windows 'Invalid argument' on locked handles)."""`. Do not touch any other code in this file.
- **Commit:** `fix(worktree): classify Windows 'Invalid argument' as WorktreeLockedError`

### Card 6: Test `Invalid argument` lock classification

- **Context:**
  - `plugins/mill/scripts/_worktree.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-worktree.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Extend `plugins/mill/unit_tests/test-worktree.py` with a new test `test_remove_safe_invalid_argument_is_locked` that asserts `remove_safe` raises `WorktreeLockedError` (not bare `WorktreeError`) when the underlying `git worktree remove` command's stderr contains the substring `"Invalid argument"`. Follow whichever mocking pattern the file already uses for the other lock-pattern tests (`"Permission denied"`, `"is in use"`, `"Access is denied"`); if the file has none, mock `_subprocess_util.run` via `unittest.mock.patch` so it returns a `MagicMock` with `returncode=1` and `stderr="error: Invalid argument"`. The test must verify (a) `WorktreeLockedError` is raised, (b) the error message contains the offending stderr text. Register the new test alongside the existing ones (in `main()` or the runner block). Do not modify `_worktree.py`.
- **Commit:** `test(worktree): cover 'Invalid argument' → WorktreeLockedError classification`

## Batch Tests

The batch's `verify:` chains the three relevant unit-test runners: `test-tasks-md.py`, `test-marker.py`, `test-worktree.py`. Cards 1–2 are covered by `test-tasks-md.py`; cards 3–4 by `test-marker.py`; cards 5–6 by `test-worktree.py`. Each script prints PASS/FAIL lines and exits non-zero on failure. There are no integration tests for this batch — every change is observable through pure-Python unit tests with in-memory fixtures.
