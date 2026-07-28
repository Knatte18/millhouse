MILL_REVIEW_BEGIN
# Review: Plan review verdict correctness: unverified platform claims and missing nit_count in subprocess dispatch — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: plan/
date: 2026-07-28
```

## Findings

### [NIT] Asymmetric dead-code cleanup between Card 2 and Card 4
**Location:** Batch 1 (01-review-plan-counting-fix.md) / Card 2, vs. Card 4
**Issue:** Card 4 explicitly removes the now-dead `verdict = parse_verdict(raw)` reassignment in `run()`'s holistic NEED_CONTEXT resume-retry-success branch (site a), since `finalize_scope()` re-derives verdict from `raw` internally. Card 2 leaves the exact analogous reassignment in `_review_one_batch()`'s per-batch resume-retry branch untouched, even though it becomes equally dead once the terminal block reads `review_entry["verdict"]` instead of the local `verdict`.
**Fix:** Add the same instruction to Card 2: remove the post-retry `verdict = parse_verdict(raw)` line (the one following `# Second NEED_CONTEXT propagates to caller untouched.`), since nothing downstream reads it after the `finalize_scope()` refactor. Purely cosmetic — traced both branches; behavior (including the ReviewError-on-unparseable-retry path) is byte-identical either way since `finalize_scope()` performs the same `parse_verdict` call regardless.

## Verdict

APPROVE
Cross-checked all 20 cards against current source (`_review_plan.py`, `_review_common.py`, both test files, both templates, `_plan_validate.py`, `plugin.json`); one cosmetic NIT, no BLOCKING issues.
MILL_REVIEW_END
