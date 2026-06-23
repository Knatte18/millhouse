MILL_REVIEW_BEGIN
# Review: Fix nit-enforcement gate, Windows verify false-positive, reviewer oscillation, and scope-violation handling -- holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-06-23
```

## Findings

### [BLOCKING] `_is_benign_windows_cleanup` omits bare `fail` failure marker

**Location:** `plugins/mill/scripts/_implementer_common.py:45-49`
**Issue:** Card 1 requires failure markers to include the bare `"fail"` token (plan: "case-insensitive none of: `fail`, `--- fail`, `panic:`, `build failed`"). The implementation omits it, using only `["--- fail", "panic:", "build failed"]`. A standard `go test` run reports `FAIL\t<pkg>` at the end of output without a `--- FAIL` prefix; if that output also contains an `unlinkat` race signature, the benign-cleanup gate would incorrectly suppress a real test failure.
**Fix:** Add `"fail"` as the first entry in `failure_markers` to match the plan's stated requirement.

### [BLOCKING] `_is_windows_lock_error` delegation widens behaviour beyond "exactly as before"

**Location:** `plugins/mill/scripts/millpy-fix.py:51-57`
**Issue:** Card 2 requires "Net behaviour: returns `True` for WinError-32 sharing-violation exceptions **exactly as before**". The old inline list was `["winerror 32", "process cannot access", "being used by another process"]`. Delegating to `_is_benign_windows_cleanup` now also matches `"unlinkat"`, `"access is denied"`, and `"winerror 5"`, classifying any LLM error mentioning those strings as `stuck_type: verify`. The `winerror 5` case is explicitly called out in plan Card 1 as a verify-gate signature but was never part of the lock-error vocabulary -- a transient LLM error message containing "winerror 5" now misroutes to verify instead of transient.
**Fix:** Either revert to the original inline list for `_is_windows_lock_error`'s string branch (keeping only `winerror 32` and process-sharing terms), or narrow the shared helper's signature set per each call site's distinct semantics.

### [NIT] Test case 24 only covers `--- FAIL` not bare `FAIL`

**Location:** `plugins/mill/unit_tests/test-implementer-common.py:776-812`
**Issue:** The four-way matrix in Card 3 tests `--- FAIL` (with the prefix) but does not exercise a bare `FAIL\t<pkg>` line as would appear in real `go test` output. Even after the bare `"fail"` is added to the implementation, the test matrix will not catch a regression that removes it again.
**Fix:** Add a sub-case to test case 24 (or a new case 24b) where the verify output contains `FAIL\tgithub.com/...` without a `--- FAIL` prefix and confirm it still stays `stuck/verify`.

## Verdict

REQUEST_CHANGES
Two blocking issues: missing bare `fail` failure marker and over-wide `_is_windows_lock_error` delegation.
MILL_REVIEW_END
