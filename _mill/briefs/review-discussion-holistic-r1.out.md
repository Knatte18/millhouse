MILL_REVIEW_BEGIN
# Review: mill-plan: planning-process documentation/procedure gaps

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5 (Sonnet 5)
reviewed_file: _mill/discussion.md
date: 2026-09-19
```

## Findings

### [BLOCKING:design] max-rounds-blocked-resume decision conflates two distinct resume paths
**Section:** Decision `max-rounds-blocked-resume-harmonization` (targets SKILL.md paragraph at line 324 vs. blockquotes at lines 479/530).
**Issue:** The line-324 paragraph is explicitly scoped `(revise_from_blocked only)` — it fires when `/mill-plan --revise` resumes a blocked task, using `blocked_resume_round` (computed at line 316). The blockquotes at 479/530 fire "only when this loop was entered via the Entry `blocked` re-entry row" (line 117's "Entry: resuming after a max-rounds block" — a bare `/mill-plan` re-invocation, no `--revise`), using `local_max_review_rounds`. Entry step 4's `--revise` pre-check intercepts and bypasses the `blocked` table row entirely when `--revise` is passed, so these two mechanisms are mutually exclusive, not two inconsistent statements of one rule. The decision's own "Rejected: using `blocked_resume_round`... instead of `local_max_review_rounds`... as the harmonized value" treats them as competing values for one scenario. Implementing the decision as written deletes the `revise_from_blocked` paragraph and replaces its trigger condition with the Entry-blocked-reentry condition, leaving the `revise_from_blocked` flow with no `--max-rounds` threading rule at all and orphaning `blocked_resume_round` (still computed at line 316, never consumed again) — while `revise_from_blocked` still has the identical unaddressed "every round after the first hits the CLI's hard round-cap error" problem `local_max_review_rounds` was invented to solve for the other path (no equivalent "Resumed-loop round-cap substitution"-style extension exists for `blocked_resume_round`).
**Fix:** Split the decision in two: (1) keep the correct part — add the missing `local_max_review_rounds` reminder blockquote to the two Agent-mode dispatch sites for the Entry-blocked-reentry path only; (2) separately decide, for `revise_from_blocked`, whether it needs its own every-round extended-budget threading (mirroring `local_max_review_rounds`, keyed off `blocked_resume_round`) or whether single-round threading is intentionally sufficient there and why — do not overwrite the `revise_from_blocked` paragraph with the other mechanism's condition/value.

## Verdict

REQUEST_CHANGES
The blocked-resume decision merges two mutually-exclusive resume paths, silently dropping revise_from_blocked's own threading rule.
MILL_REVIEW_END
