MILL_REVIEW_BEGIN
# Review: mill-plan: Requirements find/replace fences lose byte-exactness under list-nested indentation — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-07-30
```

## Findings

### [BLOCKING] Nested-heading test fixture can't distinguish fence-aware code from broken code
**Location:** `plugins/mill/unit_tests/test-plan-validate.py:2356-2404` (fixture built at lines 2377-2385), exercising `_requirements_fence_aware_body` at `plugins/mill/scripts/_plan_validate.py:1651-1695`.
**Issue:** The test's interior look-alike lines (`"  ### Nested Heading\n"`, `"  - **SomeField:** value\n"`) are indented 2 spaces, but `any_field_header_re = re.compile(r"^-\s*\*\*[A-Za-z]+:\*\*")` in `_requirements_fence_aware_body` requires the line to start with `-` at column 0 with zero leading whitespace. Because the look-alike line never matches that regex regardless of `in_fence` state, this fixture passes identically whether the `in_fence` guard is present, broken, or removed outright — it does not actually prove the `fence-aware-boundary-detection` Decision's core property (which round-1 discussion review previously flagged as a GAP). Manually tracing the fixture confirms `in_fence` toggling has zero effect on the outcome here.
**Fix:** Make the interior look-alike line flush-left (column 0, e.g. `"- **SomeField:** value\n"` with no leading spaces) while keeping the fence delimiters flush-left too, so the line genuinely matches `any_field_header_re` and would incorrectly truncate the field body without a working `in_fence` guard — proving the guard is load-bearing. (A uniform per-line drift can still be applied only to the non-look-alike lines, since `_strip_n_leading_spaces` already tolerates heterogeneous per-line indentation.)

## Non-blocking carryover (not escalated, no new information)

- CRLF test doesn't isolate the explicit normalization step (`_plan_validate.py:1783`, `test-plan-validate.py:2311-2350`) — unchanged from prior round; `Path.read_text`'s universal-newline translation likely already converts `\r\n`→`\n` before the explicit `.replace()` runs, so the test doesn't isolate that step. Same location and same nature as previously judged; not escalating.

## Verdict

REQUEST_CHANGES
One BLOCKING: the nested-heading test doesn't actually discriminate fence-aware code from broken/absent in_fence tracking.
MILL_REVIEW_END
