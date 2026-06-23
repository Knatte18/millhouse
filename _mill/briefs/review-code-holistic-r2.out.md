MILL_REVIEW_BEGIN
# Review: Fix nit-enforcement gate, Windows verify false-positive, reviewer oscillation, and scope-violation handling — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-06-23
```

## Findings

### [BLOCKING] Card 2 delegation not implemented in `_is_windows_lock_error`

**Location:** `plugins/mill/scripts/millpy-fix.py:58-63`
**Issue:** Card 2 requires the string-signature branch of `_is_windows_lock_error` to delegate to `_implementer_common._is_benign_windows_cleanup(str(e))`, replacing the inline list `["winerror 32", "process cannot access", "being used by another process"]`. The implementation keeps the inline list unchanged and does not import or call `_is_benign_windows_cleanup` for this purpose.
**Fix:** Either implement the delegation as specified (which requires adding `"process cannot access"` and `"being used by another process"` to `_is_benign_windows_cleanup`'s signature vocabulary so the contract is preserved), or update the plan to formally record that the delegation was intentionally skipped because `_is_benign_windows_cleanup` does not carry those lock-error patterns. As written, the plan contract is unmet and the batch file says it was delivered.

### [NIT] `_is_benign_windows_cleanup` docstring omits bare `"fail"` marker

**Location:** `plugins/mill/scripts/_implementer_common.py:22-23`
**Issue:** The docstring lists only `--- fail, panic:, build failed` as failure markers, but the implementation at line 46 also checks bare `"fail"` (which makes `"--- fail"` on line 47 redundant since it is a strict substring). The docstring is the declared API contract for callers.
**Fix:** Add `fail` to the docstring marker list, or remove the redundant `"--- fail"` entry from the code if bare `"fail"` is intentionally the canonical check.

### [NIT] `test-review-code-flow.py` test 18b double-seed overwrites first seed

**Location:** `plugins/mill/unit_tests/test-review-code-flow.py:1137,1141`
**Issue:** Line 1137 calls `stub.seed([(APPROVE_TEXT, "sid-r1")])` then line 1141 immediately calls `_seed_approve(1)` which itself calls `stub.seed(...)` and clears the prior queue. The seed at 1137 has no effect and misleads future readers about the test setup.
**Fix:** Remove the dead `stub.seed(...)` at line 1137.

## Verdict

REQUEST_CHANGES
Card 2 delegation from `_is_windows_lock_error` to `_is_benign_windows_cleanup` was not implemented; the plan contract is unmet.
MILL_REVIEW_END
