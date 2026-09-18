MILL_REVIEW_BEGIN
# Review: Review output reliability: metadata misattribution and factual-accuracy failures

```yaml
duration_s: 127.0
verdict: APPROVE
reviewer_model: sonnet
reviewer_self_id: claude-sonnet-5
reviewed_file: /home/knatte/Code/millhouse/wts/review-output-reliability-and-attribution-bugs/_mill/discussion.md
date: 2026-09-18
```

## Findings

### [NIT:consistency] schema.md line 59 paragraph: delete-whole vs. keep-part conflict
**Demoted-from:** BLOCKING
**Section:** Decision `reviewer-self-id-removed` vs. `## Technical context` bullet for `review-output.schema.md`.
**Issue:** Confirmed by reading `review-output.schema.md` line 59: it is a single paragraph whose first sentence explains `reviewer_self_id` and whose second sentence explains `apply_actual_model_override()`'s role/contrast with `reviewer_model`. The Decision instructs removing "the paragraph starting `reviewer_self_id is unverified and reviewer-reported…`" (the whole paragraph, verbatim), but the Technical context bullet for the same file says the `apply_actual_model_override()` text "(~line 59) — this text is already accurate and does not need to change" — the same line, opposite instruction.
**Fix:** State explicitly whether the plan should (a) delete the full paragraph as one unit (losing the still-accurate `apply_actual_model_override()` explanation, which appears nowhere else in the schema doc), or (b) split the paragraph, deleting only the first sentence and keeping a rewritten second sentence.

## Verdict

APPROVE
One BLOCKING: schema.md's line-59 paragraph fate is contradicted between the Decision and Technical context sections.
_Note: 1 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 0._
MILL_REVIEW_END
