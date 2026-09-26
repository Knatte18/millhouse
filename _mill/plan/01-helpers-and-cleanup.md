# Batch: helpers-and-cleanup

```yaml
task: 'Post-merge teardown: keep PR notes, remove checkpoint branches'
batch: 'helpers-and-cleanup'
number: 1
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-finalize-cleanup.py test-cleanup.py
depends-on: []
```

## Batch Scope

Adds the script-side helpers (checkpoint naming/deletion, pr-notes stashing) to `_finalize_cleanup.py`, wires checkpoint deletion into the two teardown functions of `millpy-cleanup.py`, and covers both with unit tests.
`_apply_pr_reap_record` delegates to those two functions, so it needs no edit.
Batch 2 consumes `stash_pr_notes` from the finalize skill text.

## Cards

### Card 1: Add checkpoint and pr-notes helpers

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/scripts/_finalize_cleanup.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_finalize_cleanup.py` add three functions, keeping the existing `base_tracks_task_dir` untouched and ASCII-only log output.
  `checkpoint_branch_name(branch: str) -> str` returns `"mill-checkpoint-" + branch.replace("/", "-")`.
  `delete_checkpoint_branch(repo: Path, branch: str) -> bool` runs `git -C <repo> branch -D <checkpoint_branch_name(branch)>` via `_subprocess_util.run`; returns True when the branch was removed or did not exist (detect absence by first running `git -C <repo> rev-parse --verify --quiet refs/heads/<name>` and returning True without deleting when it exits non-zero); on any other failure print a one-line message to stderr and return False; never raise.
  `stash_pr_notes(worktree: Path, task_dir: Path, slug: str) -> bool` with destination `worktree / ".scratch" / f"pr-notes-{slug}.md"` and source `task_dir / "pr-notes.md"`: when the source exists and its text is non-empty after strip, create `.scratch` if needed, copy the source over the destination (always overwriting), and return True; otherwise leave any existing destination untouched and return whether the destination exists.
  Read and write with `encoding="utf-8"`.
- **Commit:** `feat(finalize-cleanup): add checkpoint and pr-notes helpers`

### Card 2: Delete checkpoint in cleanup teardown

- **Context:**
  - `plugins/mill/scripts/_finalize_cleanup.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-cleanup.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `millpy-cleanup.py` add `import _finalize_cleanup` beside the other module imports.
  In `_apply_worktree_record`, immediately after the local `branch -D` handling and before `_delete_remote_branch`, call `_finalize_cleanup.delete_checkpoint_branch(hub_root, record.branch)` inside the existing `if record.branch is not None:` block.
  In `_apply_inplace_record`, inside the `if task_branch:` block immediately after the local branch deletion result handling and before `_delete_remote_branch`, call `_finalize_cleanup.delete_checkpoint_branch(hub_root, task_branch)`.
  Do not edit `_apply_pr_reap_record`: it delegates to the two functions above.
  The early-return paths of `_apply_inplace_record` and the empty-`task_branch` path stay as they are, so no checkpoint deletion happens there.
- **Commit:** `fix(cleanup): delete mill-checkpoint branch with the task branch`

### Card 3: Unit tests for helpers and cleanup wiring

- **Context:**
  - `plugins/mill/scripts/_finalize_cleanup.py`
  - `plugins/mill/scripts/millpy-cleanup.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-finalize-cleanup.py`
  - `plugins/mill/unit_tests/test-cleanup.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `test-finalize-cleanup.py`, following its existing ok/fail counter pattern and real temp git repo, add cases: `checkpoint_branch_name` with and without a slash; `delete_checkpoint_branch` removes an existing `mill-checkpoint-` branch, returns True for a missing branch, and does not touch an unrelated branch; `stash_pr_notes` returns True and writes `.scratch/pr-notes-<slug>.md` when the source is present, returns False for an absent source, returns False for a whitespace-only source, overwrites an existing scratch copy when the source is present, and keeps the scratch copy and returns True when the source is gone.
  Import the new names from `_finalize_cleanup`.
  In `test-cleanup.py`, following the existing `_apply_worktree_record` and `_apply_inplace_record` test pattern that patches `mill_cleanup._subprocess_util.run`, add one worktree-record case and one in-place case asserting the recorded git calls include a `branch -D mill-checkpoint-...` call with the slash-to-dash name derived from the record's branch, and one case asserting a non-zero return from that call does not raise.
- **Commit:** `test(cleanup): cover checkpoint deletion and pr-notes stash`

## Batch Tests

`verify:` runs `test-finalize-cleanup.py` (helpers, real temp git repo) and `test-cleanup.py` (wiring via patched subprocess), which are exactly the two test files this batch edits.
