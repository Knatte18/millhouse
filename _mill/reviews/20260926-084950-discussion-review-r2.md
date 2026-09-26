MILL_REVIEW_BEGIN
# Review: Post-merge teardown: keep PR notes, remove checkpoint branches

```yaml
duration_s: 40.6
verdict: APPROVE
reviewer_model: sonnet
reviewed_file: /home/knatte/Code/millhouse/wts/merge-teardown-hygiene/_mill/discussion.md
date: 2026-09-26
```

## Findings

### [NIT:consistency] Success-path deletion contradicts existing merge-in text
**Demoted-from:** BLOCKING
**Section:** Decisions / Delete the checkpoint at the end of a successful merge-in **Issue:** `mill-merge-in/SKILL.md` Step 6 still prints `Checkpoint: <CHK> (delete manually...)` and ends with "Leave the checkpoint branch in place on success. The user decides when to delete it"; the decision says delete after Step 5 but never disposes of these statements, and Step 6 reports a branch that no longer exists. **Fix:** State that both the Step 6 `Checkpoint:` line and the "Leave the checkpoint" paragraph are removed or reworded, and where the delete block sits relative to Step 6.

### [NIT:decision] mill-merge Step 2 consumes the printed checkpoint name
**Demoted-from:** BLOCKING
**Section:** Scope / Decisions **Issue:** `mill-merge/SKILL.md` Step 2 says "Capture the checkpoint branch name it prints; you may need it on rollback", which the deletion makes stale (and its rollback already uses `origin/<parent_branch>`); the discussion places `mill-merge` out of scope without addressing this reference. **Fix:** Give a disposition for that sentence (update or leave, with reason).

### [NIT:scope] In-place cleanup early-return paths skip checkpoint deletion
**Section:** Decisions / mill-cleanup deletes the checkpoint **Issue:** `_apply_inplace_record` returns early when parent branch or checkout fails, and skips branch deletion when `task_branch` is empty; the "right after task-branch deletion" placement leaves the checkpoint in those cases without saying so. **Fix:** State that checkpoint deletion is tied to task-branch deletion and is skipped on those paths.

## Verdict

APPROVE
Merge-in deletion leaves contradictory Step 6 and mill-merge text with no stated disposition.
_Note: 2 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 0._
MILL_REVIEW_END
