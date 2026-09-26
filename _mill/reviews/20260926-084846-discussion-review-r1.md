MILL_REVIEW_BEGIN
# Review: Post-merge teardown: keep PR notes, remove checkpoint branches

```yaml
duration_s: 31.3
verdict: REQUEST_CHANGES
reviewer_model: sonnet
reviewed_file: /home/knatte/Code/millhouse/wts/merge-teardown-hygiene/_mill/discussion.md
date: 2026-09-26
```

## Findings

### [NIT:decision] Stash helper: script or inline prose is undecided
**Demoted-from:** BLOCKING
**Section:** Scope (In, last bullet) vs Testing (stash helper bullet) **Issue:** Scope promises a shared pr-notes stashing helper in `_finalize_cleanup.py` with unit tests, but Testing says "if implemented as a script helper rather than inline skill text", and the Decision describes only inline copy steps in the SKILL. **Fix:** State which one it is; if a helper, name it and its signature.

### [BLOCKING:design] Stale scratch file can leak into an unrelated PR
**Section:** Decision: Fold pr-notes via a scratch stash **Issue:** git-pr appends `.scratch/pr-notes.md` whenever it exists, and deletes it only after a successful `gh pr create`. A leftover from a failed or abandoned finalize (or a different task in the same worktree) attaches to the next PR. The idempotency rule "keep the scratch copy when the source is gone" and the case where both exist (overwrite or keep) are not specified against this. **Fix:** Define the overwrite rule when both exist, and how a stale scratch file is detected or cleared when `_mill/pr-notes.md` is absent and the run is fresh.

### [NIT:design] Non-finalize git-pr invocations are not actually isolated
**Section:** Decision: Fold pr-notes via a scratch stash **Issue:** "Unaffected" holds only if nothing else writes `.scratch/pr-notes.md`. The `.scratch/` directory is a shared scratch space. **Fix:** Note the file-name collision risk or use a task-specific name.

### [NIT:scope] pr-reap deletion point is not pinned
**Section:** Decision: mill-cleanup deletes the checkpoint **Issue:** "the branch-deleting part of `_apply_pr_reap_record`" is vague, since the teardown is delegated after the merged state check. **Fix:** Name the exact call site or the helper it goes through, so the plan does not double-delete or miss the path.

## Verdict

REQUEST_CHANGES
One undecided helper-vs-inline choice and an unspecified stale scratch-file rule need resolving before planning.
_Note: 1 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 1._
MILL_REVIEW_END
