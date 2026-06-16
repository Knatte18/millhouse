MILL_REVIEW_BEGIN
# Review: Fix unit test suite failures, spurious review warning, and implementer verify-gate gaps — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-06-16
```

## Findings

### [BLOCKING] Verify gate silently skips on subprocess exception

**Location:** `plugins/mill/scripts/_implementer_common.py:137-139`
**Issue:** `_run_verify_gate` catches all exceptions and returns `None`, which the caller interprets as "gate passed"; a missing binary or other `FileNotFoundError` from `subprocess.run` will silently approve the success instead of demoting to `stuck_type: verify`.
**Fix:** Change the bare `except Exception: pass` to return a stuck dict with an appropriate reason string (e.g. `f"verify gate raised: {e}"`) so callers can distinguish a silent pass from a genuine exception.

### [NIT] New #489 test cases use bare assert instead of errors accumulator

**Location:** `plugins/mill/unit_tests/test-review-common.py:2396-2443`
**Issue:** The two new functions `test_parse_blocking_count_clean_review_zero_headings` and `test_parse_blocking_count_with_headings_still_warns` use bare `assert` + `print("PASS: ...")` and are called directly at lines 2442-2443 — a failure raises `AssertionError` and exits `main()` immediately rather than printing `FAIL:` and accumulating into `errors`, inconsistent with the file's stated convention and plan card 3's requirement to "contribute to the same failure accounting the other cases use."
**Fix:** Wrap each new test block in a `try/except Exception` like the surrounding cases and accumulate failures to `errors`.

### [NIT] Batch 02 Edits lists test-plan-validate.py but overview omits it from All Files Touched

**Location:** `_mill/plan/02-ascii-arrow-fix.md` (Edits), `_mill/plan/00-overview.md` (All Files Touched)
**Issue:** Card 4's `Edits:` includes `plugins/mill/unit_tests/test-plan-validate.py`, but this file has no U+2192 characters, was not modified, and is absent from the overview's `## All Files Touched` union; the batch file and overview are inconsistent.
**Fix:** Remove `test-plan-validate.py` from card 4's `Edits:` list (since no changes are made to it) and leave the overview unchanged.

## Verdict

REQUEST_CHANGES
Two nits plus one blocking gap where a subprocess exception in the verify gate silently approves a success.
MILL_REVIEW_END
