MILL_REVIEW_BEGIN
# Review: mill-go/millpy-implement: Windows dotnet build-server file-lock races in verify/baseline stages — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5 (Sonnet 5 per harness label)
reviewed_file: plan/
date: 2026-08-14
```

## Findings

### [NIT:consistency] Card 2 misdescribes Test C's try/except granularity
**Location:** batch 1, Card 2 (Test I). **Issue:** Requirements cite "Test C1/Test C2" as precedent for "per-sub-case try/except granularity," but `test-implementer-common.py`'s actual Test C (lines 1912-2019) wraps all three sub-cases (C1, C2, non-dotnet) in ONE shared `TemporaryDirectory`/`try`/`except` — every other lettered Test block (A through H) in the file follows the same one-block-per-Test norm, not one-block-per-sub-case. **Fix:** Correct the citation, or explicitly note Test I is intentionally introducing finer-grained sub-case isolation than the file's norm (functionally harmless either way — the four-sub-case structure Card 2 specifies is otherwise fully self-contained and unambiguous).

### [NIT:consistency] Card 6's compute_batch_baselines mock instruction is self-contradicting
**Location:** batch 2, Card 6, `test_baseline_stage_finally_teardown_failure_never_raises`. **Issue:** Requirements first say `return_value={"batch-a": [], "batch-b": []}`, then in the same parenthetical reverse course and mandate a `side_effect` function instead — but a flat `return_value` dict containing both keys actually works fine here (both per-batch calls index into the same dict with their own name, unlike the failure-isolation test where behavior differs per batch). **Fix:** Simplify to a single unambiguous instruction (either is functionally correct; the current wording is confusing to read literally).

## Verdict

APPROVE
Round-2 plan is thoroughly source-grounded — every cited line number, function boundary, and identifier verified against actual files; only cosmetic NITs remain.
MILL_REVIEW_END
