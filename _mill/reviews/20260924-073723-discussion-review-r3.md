MILL_REVIEW_BEGIN
# Review: Remove batch review (plan-review.batch / code-review.batch)

```yaml
duration_s: 211.5
verdict: APPROVE
reviewer_model: sonnet
reviewed_file: _mill/discussion.md
date: 2026-09-24
```

## Findings

### [NIT:scope] Test-file enumeration misses test-fix-finalize.py
**Demoted-from:** BLOCKING
**Section:** Scope "Tests:" bullet / Testing section.
**Issue:** `plugins/mill/unit_tests/test-fix-finalize.py` Test 5 and Test 6 call `millpy_fix.main([...])` with the literal args `--scope batch --batch-name test-batch`, exercising exactly the flags the `millpy-fix-scope-flag` Decision removes from `millpy-fix.py`. This file is absent from both the "Known files" list under Scope and the per-file Testing worklist, despite containing genuine batch-scope CLI coverage (unlike, e.g., `test-review-code-flow.py`, correctly listed, or `test-review-finalize.py`/`test-review-class-taxonomy.py`, which carry no batch-scope hits). A repo-wide grep for `--batch-name`/`--scope batch` finds it; the discussion's manual "Known files" enumeration did not.
**Fix:** Add `test-fix-finalize.py` to the Testing worklist (rewrite its batch-scope cases, Test 5/Test 6), and have the plan writer run the same repo-wide grep the Testing section's own final gate already specifies once during planning, rather than relying on a hand-curated file list.

## Verdict

APPROVE
One test file with real batch-scope CLI coverage is missing from the test-removal inventory.
_Note: 1 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 0._
MILL_REVIEW_END
