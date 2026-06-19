MILL_REVIEW_BEGIN
# Review: Fix config unknown-key warning on git namespace and commit _mill/briefs/ after dispatch

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-19
```

## Findings

### [GAP] verify-fix brief commit timing is contradictory
**Section:** Scope > Gap B (mill-merge-in) / Q&A log Q4
**Issue:** The fix stages `_mill/briefs/` "before `git ... merge --continue`" and claims this makes "the `merge/conflicts` **and** `merge/verify-fix` briefs land in the merge commit" — but the `merge/verify-fix` brief is written in step 4 (Verify), which runs *after* the step-3 `merge --continue`, so it cannot be in that commit. On a clean merge (no conflicts), step 3 does no `merge --continue` at all, so neither brief gets staged by this path. Verified: `millpy-merge-in-subagent.py` writes the `merge/verify-fix` brief at line 324, and step 4's sub-agent commit (lines 353-359) stages only its own fix changes, not `_mill/briefs/`.
**Fix:** Add a separate orchestrator commit (or `git add _mill/briefs/` step) in mill-merge-in step 4 for the `merge/verify-fix` brief, and decide whether the conflict-path staging must also cover the clean-merge case; the single pre-`merge --continue` add does not capture verify-fix.

### [NOTE] parent-branch is a net-new template key, not in the current comment
**Section:** Decisions > Gap A / Technical context
**Issue:** The Decision says "replace the commented `git:` block" implying all three keys exist commented out, but the actual template (lines 80-82) comments only `require_pr_to_base` and `base_branch`; `parent-branch` is a brand-new addition.
**Fix:** State explicitly that `parent-branch: null` is net-new (the planner must add it, not uncomment it).

### [NOTE] git read-site attributed to wrong skill
**Section:** Technical context (bullet 2)
**Issue:** `git.require_pr_to_base` / `git.base_branch` are described as "read by `mill-merge/SKILL.md` (steps ~30-31)", but the actual `cfg.get("git", ...)` reads live in `mill-finalize/SKILL.md` (lines 32-33); mill-merge only documents them in prose. Defaults (`false` / `main`) are confirmed correct.
**Fix:** Correct the attribution to mill-finalize; does not affect the template-registration fix.

## Verdict

GAPS_FOUND
One scope/timing gap: the verify-fix brief cannot land in the merge commit as stated.
MILL_REVIEW_END
