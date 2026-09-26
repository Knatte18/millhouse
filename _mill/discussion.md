# Discussion: Post-merge teardown: keep PR notes, remove checkpoint branches

```yaml
task: 'Post-merge teardown: keep PR notes, remove checkpoint branches'
slug: merge-teardown-hygiene
status: discussing
parent_branch: main
```

## Problem

Two teardown bugs, sources GitHub issues #1156 and #1152.

**#1156.**
A plan card can write reviewer-facing PR notes (docs-to-update list, left-in-place comments, test results) to `_mill/pr-notes.md`.
`mill-finalize` Step 3 then removes the whole task dir (`git rm -r <task_dir>`) and `git-pr` Step 9 builds the PR body only from `git log origin/<base>..HEAD --oneline`.
The notes therefore never reach the PR unless the builder recovers them from history by hand.

**#1152.**
`mill-merge-in` Step 2 creates a local branch `mill-checkpoint-<branch with / -> ->` (`git branch -f "$CHK"`) and nothing ever deletes it.
One branch accumulates per finished task (25 seen in one hub), cluttering `git branch`.
`mill-cleanup` (`millpy-cleanup.py`) deletes the task branch and worktree but not the checkpoint.

## Scope

**In:**

- `mill-finalize` / `git-pr`: carry `_mill/pr-notes.md` (if present) into the PR body.
- `mill-merge-in`: delete its own checkpoint after merge and verify succeed.
- `millpy-cleanup.py`: delete `mill-checkpoint-<branch>` in the same teardown that removes the task branch, for both worktree and in-place records (and the pr-reap record path, which also removes the branch).
- Shared helpers in `_finalize_cleanup.py` (checkpoint naming/deletion and pr-notes stashing), with unit tests.

**Out:**

- Changing where plan cards write PR notes (mill-plan is untouched; `_mill/pr-notes.md` stays the convention).
- The direct-merge path (`mill-merge`) for pr-notes: no PR exists there, so no PR body to fold notes into.
  Exception, wording only: `mill-merge` Step 2's "Capture the checkpoint branch name it prints; you may need it on rollback" is removed (merge-in no longer prints a checkpoint name, and mill-merge's rollback already targets `origin/<parent_branch>`, per its own "Why `origin/<parent_branch>`, not the checkpoint" note), and its rollback line "Preserve the checkpoint branch." is dropped as moot once merge-in succeeded.
  No behaviour change in mill-merge.
- Remote checkpoint branches: checkpoints are local-only (`git branch -f`, never pushed).
- Any change to rollback semantics (`mill-merge` already rolls back to `origin/<parent_branch>`, not the checkpoint).

## Decisions

### Fold pr-notes via a scratch stash (fixes #1156)

- Decision: in `mill-finalize` Step 3, before either cleanup branch runs, if `<task_dir>/pr-notes.md` exists and is non-empty, copy it to `<worktree>/.scratch/pr-notes-<slug>.md` (gitignored, so it survives `git rm -r` and is never committed).
  In Step 5, `git-pr` is invoked with the extra flag; `git-pr` Step 9 gains: when `--pr-notes <path>` is given and the file exists, append its contents to the generated body under a `## Reviewer notes` heading, then delete the scratch file after `gh pr create` succeeds (also after the REST fallback).
  Argument parsing: `git-pr`'s Usage/argument handling (which treats the first remaining non-flag token as the base branch, and already strips `--skip-task-branch-guard`) must strip `--pr-notes` and its following value before base-branch selection, so the path is never read as the base branch.
  The Usage section documents the new flag.
  `git-pr` reads notes only when `--pr-notes` is passed, so non-task and non-finalize uses are unaffected.
- Helper: the stash is a script helper, not inline SKILL prose: `_finalize_cleanup.stash_pr_notes(worktree: Path, task_dir: Path) -> bool` (returns True when a scratch copy exists after the call).
  Scratch file name is task-specific to avoid collisions in the shared `.scratch/`: `.scratch/pr-notes-<slug>.md`, so the helper takes `slug` too: `stash_pr_notes(worktree, task_dir, slug)`.
  `git-pr` receives the path explicitly rather than guessing: mill-finalize passes `--pr-notes <path>` when `stash_pr_notes` returned True; `git-pr` appends only when that flag is given.
  Overwrite rule: if `<task_dir>/pr-notes.md` exists and is non-empty, it always overwrites the scratch copy (source of truth wins).
  If the source is absent or empty, any existing scratch copy for this slug is kept (re-run after a partial failure), never deleted at stash time.
  Stale-file protection: the file is slug-specific and only ever passed via the explicit flag, so a leftover from another task can never attach to a PR; a leftover for the same slug is either a legitimate re-run or overwritten by the fresh source.
  `git-pr` deletes the scratch file after PR creation succeeds; on failure it is left in place for the operator's retry.
- Rationale: the cleanup must keep removing `_mill/` (PR diff hygiene), so the notes need a location that survives the removal without landing in the diff; `.scratch/` is the repo's designated gitignored scratch.
  Copy-before-cleanup is idempotent on a re-run: if `_mill/pr-notes.md` is already gone but the scratch copy exists, keep the scratch copy.
- Rejected: (a) reading the notes from `git show <cleanup>^:_mill/pr-notes.md` inside git-pr -- couples git-pr to finalize's commit layout; (b) steering mill-plan cards to write outside `_mill/` -- notes would then be committed into the PR diff; (c) skipping cleanup for `pr-notes.md` -- pollutes the PR diff and breaks the restore-from-base path.
- Assumption (autonomous): PR body uses the notes verbatim, appended after the generated summary, with no size cap (GitHub's own limit applies; on a `gh pr create` failure the existing error path handles it).

### Delete the checkpoint at the end of a successful merge-in (fixes #1152, part 1)

- Decision: `mill-merge-in` deletes `$CHK` (`git branch -D "$CHK"`) as the last action after Step 4 verify passes and Step 5 dispatch-brief commit, on the success path only.
  Every failure path (conflict-stuck, verify-fix stuck) already says "preserve the checkpoint" and stays unchanged.
  Deletion failure is non-fatal (log and continue).
  Placement: the delete block sits between Step 5 (brief commit) and Step 6 (Report).
  Step 6's `Checkpoint: <CHK> (delete manually ...)` report line is removed, as is the trailing paragraph "Leave the checkpoint branch in place on success. The user decides when to delete it ..." (replaced by one sentence stating the checkpoint is deleted on success and preserved only on the Rollback path).
  The "Substituted parent branch" append instruction that says "after the `Checkpoint:` line" is reworded to "after the `Verify:` line".
  The Rollback section's "Do **not** delete the checkpoint" stays as is (failure path).
  The no-op fast path (Step 1 exits before creating a checkpoint) is unchanged.
- Rationale: a checkpoint is only needed while a rollback is possible; once merge and verify pass it is dead weight.
- Rejected: leaving it for cleanup only -- a task that is never cleaned still accumulates, and long-lived tasks re-running merge-in would keep it around.

### mill-cleanup deletes the checkpoint with the task branch (fixes #1152, part 2)

- Decision: add `checkpoint_branch_name(branch: str) -> str` to `_finalize_cleanup.py` (`"mill-checkpoint-" + branch.replace("/", "-")`, matching the merge-in skill's `tr '/' '-'`) and `delete_checkpoint_branch(hub_root, branch)` (runs `git -C <hub_root> branch -D <name>`; a missing branch is success, other failures are logged non-fatally like the existing `branch -D` handling).
  Call it from `_apply_worktree_record`, `_apply_inplace_record`, right after each one's task-branch deletion.
  `_apply_pr_reap_record` needs no separate call: it delegates its teardown to `_apply_inplace_record` / `_apply_worktree_record` (the final dispatch in that function), so those two call sites cover it and nothing is deleted twice.
  Checkpoint deletion is tied to task-branch deletion: on `_apply_inplace_record`'s early-return paths (no parent branch, checkout failed) and when `task_branch` is empty, no branch is deleted and the checkpoint is likewise left alone.
  This covers leftovers from failed/stuck merge-ins and pre-fix accumulation for tasks that get cleaned from now on.
- Rationale: both fixes together are what the issue asked for ("either or both"); the cleanup half catches the halted-checkpoint case, which is the only time one survives after the merge-in fix.
- Rejected: a one-off sweep of all existing `mill-checkpoint-*` branches -- not requested, and would risk deleting a checkpoint of a live task.
  Existing stale branches are left for manual `git branch -D`.
- The shared helper lives in `_finalize_cleanup.py` (already the home of finalize cleanup helpers); `millpy-cleanup.py` imports it.

## Technical context

- `plugins/mill/skills/mill-finalize/SKILL.md`: Step 3 "Cleanup commit" (both restore-from-base and `git rm -r` branches) and Step 5 "Create PR" (invokes `/git-pr <parent_branch> --skip-task-branch-guard`).
- `plugins/mill/skills/git-pr/SKILL.md`: Step 9 "Generate PR content" (`git log origin/<base>..HEAD --oneline`), Step 10 (`gh pr create`), Step 10.5 (REST fallback).
- `plugins/mill/skills/mill-merge-in/SKILL.md`: Step 2 creates `$CHK`; Steps 3-4 roll back via `git reset --hard "$CHK"` on stuck; Step 5 commits dispatch briefs.
  Each fenced bash block runs as a separate tool call, so recompute `CHK` in the deletion block rather than relying on a shell variable.
- `plugins/mill/scripts/millpy-cleanup.py`: `_apply_worktree_record` (`branch -D <record.branch>` then `_delete_remote_branch`), `_apply_inplace_record` (checkout parent, `branch -d/-D`), `_apply_pr_reap_record`.
- `plugins/mill/scripts/_finalize_cleanup.py`: existing `base_tracks_task_dir`; uses `_subprocess_util.run`.
- Checkpoint branches are refs in the shared repo, so a worktree's checkpoint is visible and deletable from the hub via `git -C <hub_root>`.
- Source-code verification and edits target this task worktree, not the plugin cache.

## Constraints

- Never use `sed`; use Edit/Write.
- `print()` / log output ASCII only.
- Never `cd` into the parent/hub worktree; use `git -C`.
- Working state stays under `_mill/` on the task branch; scratch goes to `.scratch/`, never `/tmp`.
- Unit tests use in-memory/tempfile fixtures, no real LLM (real git in tempdirs is acceptable where `test-finalize-cleanup.py` already does so).
- Verify commands in plan files must start with `PYTHONPATH=` (empty value).

## Testing

- `test-finalize-cleanup.py`: TDD candidates for `checkpoint_branch_name` (slash replacement, no slash) and `delete_checkpoint_branch` (existing branch removed, missing branch is success, git failure non-fatal), against a temp git repo.
- `stash_pr_notes`: present file copied to `.scratch/pr-notes-<slug>.md`, absent file no-op (returns False), empty file no-op, source present overwrites an existing scratch copy, source gone with scratch copy present keeps it and returns True.
- `test-cleanup.py`: worktree record, in-place record, and pr-reap record each delete `mill-checkpoint-<branch>`; absence of the checkpoint does not fail.
- SKILL.md changes (mill-finalize, git-pr, mill-merge-in) are prose edits; verify by grep for the new steps and, if existing unit tests lock skill text (e.g. `test-mill-finalize-dispatch.py`), keep them passing.

## Q&A log

- **Q:** Fix #1156 in finalize/git-pr, or steer mill-plan elsewhere? **A:** [auto-pick] Fold into PR body via scratch stash in finalize + git-pr. **Why:** keeps `_mill/` cleanup and PR diff hygiene intact; notes reach the PR.
- **Q:** Fix #1152 in mill-merge-in, mill-cleanup, or both? **A:** [auto-pick] Both. **Why:** merge-in deletion handles the success path; cleanup catches checkpoints preserved after halts.
- **Q:** Sweep pre-existing stale checkpoints? **A:** [auto-pick] No. **Why:** out of the requested scope; risks removing a live task's checkpoint.
