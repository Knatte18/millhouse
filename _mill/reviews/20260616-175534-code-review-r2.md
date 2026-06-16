MILL_REVIEW_BEGIN
# Review: Fix unit test suite failures, spurious review warning, and implementer verify-gate gaps — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-06-16
```

## Findings

### [NIT] Card 3 test (a) does not isolate verdict-line filter
**Location:** `plugins/mill/unit_tests/test-review-common.py:2396-2421`
**Issue:** The zero-heading suppression fires before the verdict-line filter runs, so the test does not independently verify that `verdict:` lines are excluded from the prose scan in the heading_count > 0 path.
**Fix:** Add a third mini-case with one `### [GAP]` heading, a diverging prose count, and a `verdict: GAPS_FOUND` line — assert the warning fires (meaning the verdict line did not inflate the prose count and produce a false divergence in the opposite direction).

### [NIT] Case 20 assertion weaker than intended
**Location:** `plugins/mill/unit_tests/test-implementer-common.py:664-665`
**Issue:** `assert "reason" in data or data["status"] == "success"` is always true when status is success, making the second disjunct a vacuous pass even if something unexpected appeared in the output.
**Fix:** Replace with `assert data["status"] == "success"` and optionally `assert "reason" not in data` to pin that no stuck fields leaked through.

## Verdict

APPROVE
Implementation is correct and complete across all four batches; two test-quality nits are the only gaps.
MILL_REVIEW_END
