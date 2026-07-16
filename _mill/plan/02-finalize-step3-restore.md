# Batch: finalize-step3-restore

```yaml
task: "mill-finalize/mill-merge corrupt or mishandle _mill/status.md and task_dir on stacked branches"
batch: finalize-step3-restore
number: 2
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-finalize-cleanup.py
depends-on: [1]
```

## Batch Scope

Fix #653 (mill-finalize's Step 3 restore-path leaves orphaned child-only files behind
because a bare `git checkout <ref> -- <path>` only adds/updates, never deletes) by making
the restore delete-then-checkout, and add `expected_slug` defense-in-depth to
mill-finalize's own `_parent_branch.resolve()` call in the Dispatch step. Both edits land
in `mill-finalize/SKILL.md`, so they are one batch to avoid two parallel batches touching
the same file. Depends on Batch 1 for the `expected_slug` kwarg's existence (Card 4 below
references it).

## Cards

### Card 3: Fix Step 3 restore path to delete-then-checkout

- **Context:**
  - `plugins/mill/scripts/_finalize_cleanup.py`
- **Edits:**
  - `plugins/mill/skills/mill-finalize/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In `### Step 3: Cleanup commit (issue #268)`, the restore-path bash block currently
    reads:
    ```
    git -C <worktree> checkout <parent_branch> -- <task_dir>
    git commit -m "chore: pre-merge cleanup"
    ```
    Change it to:
    ```
    git -C <worktree> rm -r --ignore-unmatch <task_dir>
    git -C <worktree> checkout <parent_branch> -- <task_dir>
    git commit -m "chore: pre-merge cleanup"
    ```
  - Update the paragraph immediately above the bash block (the one describing "If True
    (base tracks task_dir): restore it from the base") to explain the two-command
    sequence: `git rm -r --ignore-unmatch <task_dir>` first empties `task_dir` of
    everything on the current (child) branch tip -- a no-op, not an error, when nothing
    matches -- then `git checkout <parent_branch> -- <task_dir>` repopulates `task_dir`
    with exactly `<parent_branch>`'s tree at that path. Any file present in the child's
    `task_dir` but absent from `<parent_branch>`'s tree there is now removed rather than
    left behind -- this closes the #653 orphaned-files gap a bare checkout left (it can
    only add/update paths present in the target ref, never delete paths that are
    exclusive to the current branch).
  - Update the "Idempotency" paragraph below the bash block to describe the new
    two-command sequence's idempotency: re-running after a partial failure is still safe
    -- `git rm -r --ignore-unmatch` is a no-op when `task_dir` is already empty/absent,
    and the subsequent checkout still succeeds (or is itself a no-op if `<parent_branch>`
    has nothing at that path). The existing "if checkout fails (rare; base has no
    `<task_dir>`), skip the commit" guidance still applies.
  - Do not modify `_finalize_cleanup.base_tracks_task_dir()` itself -- the restore-vs-rm
    branch decision is unchanged; only the restore path's own git commands change.
- **Commit:** `fix(mill): make mill-finalize Step 3 restore delete orphaned task_dir files`

### Card 4: Add expected_slug to mill-finalize's Dispatch-step resolve() call

- **Context:**
  - `plugins/mill/scripts/_parent_branch.py`
- **Edits:**
  - `plugins/mill/skills/mill-finalize/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In `## Dispatch`, the line `- parent_branch = _parent_branch.resolve(status_path,
    interactive=False)` becomes `- parent_branch = _parent_branch.resolve(status_path,
    interactive=False, expected_slug=slug)` (`slug` is already bound in Entry step 4:
    `slug = active_data['slug']`).
  - Add a one-sentence note that this is a defense-in-depth check: this particular read
    always runs before Step 3's own restore-path corruption within a single mill-finalize
    invocation, so it costs nothing to protect and only matters on an unusual re-run
    after a prior partial failure.
- **Commit:** `fix(mill): thread expected_slug through mill-finalize's parent-branch resolve`

### Card 5: Add orphan-removal regression test to test-finalize-cleanup.py

- **Context:**
  - `plugins/mill/scripts/_finalize_cleanup.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-finalize-cleanup.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Add a third case to `main()`, alongside the existing (a)/(b) `base_tracks_task_dir`
    cases, exercising the actual delete-then-restore git-command mechanic from Card 3
    (not just the detection function). Reuse the existing `clone`/`bare` tempfile fixture
    already set up in this file.
  - On the existing `main` branch (base), `_mill/` tracks only `status.md`. On a new
    branch checked out from `main` (representing the child), add `_mill/discussion.md`
    and `_mill/plan/00-overview.md` (both with trivial placeholder content) alongside
    `_mill/status.md`, and commit -- this is the "child has a superset `_mill/` tree"
    setup.
  - Run `git -C <clone> rm -r --ignore-unmatch _mill` followed by `git -C <clone>
    checkout main -- _mill`, matching Card 3's exact two-command sequence.
  - Assert: `_mill/discussion.md` and `_mill/plan/` no longer exist on disk after the
    sequence, and `_mill/status.md`'s content on disk now exactly matches `main`'s
    version (not the child branch's superset version). This is the regression guard for
    #653 -- a bare `git checkout main -- _mill` (the pre-fix behavior) would have left
    `discussion.md`/`plan/` in place; only the `rm -r --ignore-unmatch` step removes
    them.
  - Update the module docstring's "Covers:" line to mention the new orphan-removal case.
- **Commit:** `test(mill): cover Step 3 delete-then-restore orphan removal`

## Batch Tests

`test-finalize-cleanup.py` covers `base_tracks_task_dir`'s existing detection behavior
(unchanged) plus the new delete-then-restore mechanic's orphan-removal guarantee, all
against real tempfile git repos (no mocks). Card 4's SKILL.md-only change has no
executable surface of its own; its correctness is a plain string-substitution read
against the updated `_parent_branch.py` signature from Batch 1, verified visually in
review, not by this batch's `verify:`.
