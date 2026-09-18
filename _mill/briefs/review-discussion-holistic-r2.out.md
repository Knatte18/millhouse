MILL_REVIEW_BEGIN
# Review: Review output reliability: metadata misattribution and factual-accuracy failures

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-09-18
```

Verified against source: `reviewer_self_id` line numbers in `review-discussion.md` (39, 64), `review-plan-holistic.md`/`review-plan-batch.md` (85, 107) all match cited `~` values; `review-code-holistic.md`/`review-code-batch.md` confirmed to lack both `reviewer_self_id` and the mechanism-claim paragraph, and both end their `## Source-grounding rule` section with the exact "Fabricating file contents…" sentence the Decision cites as the insertion anchor. `review-output.schema.md` field-table row (19) and explanatory paragraph (59) confirmed, including the two-sentences-on-one-line structure the Decision describes. `_review_common.py`'s `apply_actual_model_override` (2587) and all three CLIs' `--actual-model` finalize-only flag confirmed; `millpy-review-summary.py` reads only `reviewer_model` (138), never `reviewer_self_id`, confirmed. `mill-go-base/SKILL.md` step 5's `--actual-model` threading (362) and step 2's "model value actually passed" capture (251-252) confirmed present and worded as described; `mill-plan/SKILL.md` both dispatch call sites (432, 517) confirmed to route through the shared Agent-mode dispatch pattern with no competing path. `test-review-common.py`'s two `reviewer_self_id` round-trip tests (737, 852) and `test-review-templates.py`'s `test_plan_mechanism_claim_rule_present` (142, currently plan-only) confirmed exactly as described. `test-review-finalize.py`'s six `--actual-model` round-trip tests (discussion/plan/code × override/omitted) confirmed present and passing-shaped. No `CONSTRAINTS.md` at hub root, confirmed. Scope, decisions (each with rationale + rejected alternatives), and testing plan are all internally consistent with the verified source; no undecided items or unaddressed failure modes found.

## Verdict

APPROVE
All checkable file/line citations verify against source; scope, decisions, and testing are complete and consistent.
MILL_REVIEW_END
