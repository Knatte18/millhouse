Good. Now I have everything I need to produce the review.

MILL_REVIEW_BEGIN
# Review: Fix agent-pipeline reliability gaps in finalize/success contract -- holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-06-09
```

## Findings

### [BLOCKING] test-review-finalize Test 3 passes vacuously on plan CLI

**Location:** `plugins/mill/unit_tests/test-review-finalize.py:191-216`
**Issue:** `_review_plan.finalize` is mocked to return a `MagicMock` object, but `millpy-review-plan.py` accesses the return value as a dict (`review_entry["verdict"]`, `review_entry["blocking_count"]`). Subscript on a MagicMock returns another MagicMock, so `json.dumps` raises a `TypeError`, which is caught by the outer `except Exception: return True` at line 215-216. The test reports PASS regardless of whether `prepare()` was or was not called.
**Fix:** Mock `_review_plan.finalize` to return a plain dict `{"scope": "holistic", "verdict": "APPROVE", "blocking_count": 0, "nit_count": 0, "file": "x.md"}` matching what the real backend returns.

### [NIT] result_dict missing nit_count in millpy-review-plan.py finalize

**Location:** `plugins/mill/scripts/millpy-review-plan.py:168-174`
**Issue:** The assembled `result_dict` omits `nit_count`, which `ReviewResult.to_dict()` includes and which mill-go reads to decide whether to dispatch a NIT-only fix pass. The code-review finalize path uses `result.to_dict()` (which includes `nit_count`), so plan-finalize silently drops it.
**Fix:** Add `"nit_count": review_entry["nit_count"]` to the `result_dict` alongside `"blocking_count"`.

### [NIT] Test coverage gap: --round required not tested for plan and discussion CLIs

**Location:** `plugins/mill/unit_tests/test-review-finalize.py:288-336`
**Issue:** `test_review_code_finalize_round_required` covers only `millpy-review-code.py`. The plan and discussion CLIs also guard `args.round is None` (added by this task), but neither has a corresponding `--round` required test.
**Fix:** Add `test_review_plan_finalize_round_required` and `test_review_discussion_finalize_round_required` following the same pattern as the code test (call without `--round`, assert `rc == 1`).

## Verdict

REQUEST_CHANGES
One test passes vacuously due to wrong mock type; nit_count dropped in plan finalize result.
MILL_REVIEW_END