Good — `validate_role_refs` is called in both CLI mains before any stage branch, so it must be mocked to prevent actual reviewer validation against the stub config. The mock is needed even if the variable isn't explicitly asserted. This is correct.

Now let me check the `discover_round` call behavior in `millpy-review-plan.py` — the finalize branch calls `resolve_path` twice (once for discovery, once for the actual `reviews_dir`), and both invocations are covered by the single `mock_resolve.return_value = reviews_dir` mock. This should work correctly.

One issue I need to verify: the test patches at `_review_common.resolve_path` but `millpy-review-plan.py` imports `resolve_path` via `from _review_common import ... resolve_path` inside `main()`. Since this import happens at call-time (inside main), patching `_review_common.resolve_path` will correctly intercept both calls to `resolve_path(...)` within finalize because at call-time the name lookup goes through `_review_common.resolve_path`. This is correct.

Now I have everything needed to produce the final review.

MILL_REVIEW_BEGIN
# Review: Fix nested-junction teardown, Windows verify gate in merge-in, and review-plan --round threading — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-06-18
```

## Findings

### [NIT] mock_validate unused variable in test-review-plan-finalize-round.py

**Location:** `plugins/mill/unit_tests/test-review-plan-finalize-round.py:86,139,189,243`
**Issue:** `mock_validate` is captured from the `_reviewers.validate_role_refs` patch context manager but never used or asserted in any of the four test cases; it is a silently unused binding that linters will flag.
**Fix:** Either drop the assignment (`with unittest.mock.patch(...):` without `as mock_validate`) or add a minimal `mock_validate.assert_called_once()` assertion to confirm the path was exercised.

### [NIT] review-plan finalize: resolve_path called twice with same result

**Location:** `plugins/mill/scripts/millpy-review-plan.py:177-182`
**Issue:** `resolve_path(cfg["paths"]["reviews_dir"], slug)` is called twice in the finalize branch — once for `reviews_dir_for_discovery` and once for `reviews_dir` — producing an identical path object both times; the second call is redundant.
**Fix:** Assign the result to a single variable (`reviews_dir`) before the `if round_n is None` block and reuse it for both the discovery call and the `finalize(...)` call.

## Verdict

APPROVE
Implementation is correct across all three batches; two NITs only, no blocking issues.
MILL_REVIEW_END