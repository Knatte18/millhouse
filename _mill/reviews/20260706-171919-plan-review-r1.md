I have verified all the plan's claims against source. All read-site line references, finalize signatures, the millpy-fix.py `--review-file` unconditional validation, the SKILL.md anchors (mill-go step 6 line 150, mill-start Entry steps, workflow Anti-patterns incident #19), and the `run-all.py --only` interface are accurate. I found one genuine defect in the test design for Cards 2-4.

MILL_REVIEW_BEGIN
# Review: Fix agent-mode dispatch gaps: HTML escaping, missing flags, timeouts, and stale skill content — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-07-06
```

## Findings

### [BLOCKING] Cards 2-4 unescape tests are structurally vacuous
**Location:** Batch 1, Cards 2, 3, 4 (test-review-finalize.py)
**Issue:** The prescribed tests are "modeled on `test_review_code_finalize_no_prepare`" and told to `assert` the finalize mock's `call_args` holds the unescaped `raw_text`; but that model function wraps everything in `except Exception: return True` (test-review-finalize.py lines 88-89, 300-301, 378-379), and its inner `except AssertionError` only returns False for the literal "prepare() must not be called" message — any other `AssertionError` re-raises and is swallowed to `return True` (PASS). A bare `assert raw_text == "Q&amp;A send &lt;guid&gt;"` therefore can never fail the test, so the batch verify goes green whether or not `html.unescape` was applied.
**Fix:** Direct the three new tests to make the unescape comparison the function's return value (e.g. `return finalize_mock.call_args.args[2] == "Q&amp;A send &lt;guid&gt;"`) instead of a bare `assert`, or to catch the mismatch in the inner handler and `return False`, so a non-unescaped read fails the test.

## Verdict

REQUEST_CHANGES
One BLOCKING: Cards 2-4's tests cannot fail; the fix must make the unescape assertion load-bearing.
MILL_REVIEW_END