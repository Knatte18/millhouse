MILL_REVIEW_BEGIN
# Review: Fix unit test suite failures, spurious review warning, and implementer verify-gate gaps — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-16
```

## Findings

### [BLOCKING] Card 7 test pattern won't execute in its host file
**Location:** Batch 3 (implementer-verify-gate), Card 7
**Issue:** Card 7 says to "mirror the git-init/commit setUp pattern in test-review-common-guard.py" (a `unittest.TestCase` file), but `test-implementer-common.py` is a `main()`/`_capture_stdout` runner with `sys.exit(main())` and NO `unittest.main()`; a bare `TestCase` class added there is never discovered/run, so the new gate cases silently provide zero coverage while verify stays green.
**Fix:** Direct Card 7 to add cases inside the existing `main()` body using the file's `_capture_stdout` + `_setup_fixture` convention (not a `TestCase` class), or require also wiring `unittest.main()`.

### [NIT] Card 3 misnames the host file's test convention
**Location:** Batch 1 (review-common-fixes), Card 3
**Issue:** Card 3 says "Follow the existing test conventions in the file (module-path bootstrap, `unittest.TestCase`)", but `test-review-common.py` uses a `main()`/manual-`PASS`/`FAIL`-counter convention with `redirect_stderr`, not `unittest.TestCase`.
**Fix:** Replace the parenthetical with the actual convention (module-path bootstrap, `main()` runner, `contextlib.redirect_stderr` to capture the warning).

### [NIT] Verify gate not threaded into millpy-fix.py
**Location:** Batch 3 (implementer-verify-gate), Card 6
**Issue:** Card 6 threads `verify_cmd` only through the two `millpy-implement.py` callsites; the `millpy-fix.py` callsites (lines ~198, ~356) also trust self-reported success and gain no gate, leaving the same false-success risk on the review-fix path. (`millpy-merge-in-subagent.py` is already covered by its `verify-fix` re-run, so its omission is fine.)
**Fix:** Either thread `verify_cmd` into the `millpy-fix.py` finalize/full callsites too, or add one line to the batch scope explicitly scoping the gate to the implement path and stating why fix is excluded.

## Verdict

REQUEST_CHANGES
Plan is accurate and well-grounded; Card 7's test pattern would not execute, plus two minor fixes.
MILL_REVIEW_END
