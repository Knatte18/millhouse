MILL_REVIEW_BEGIN
# Review: mill-plan review severity counting and validation schema gaps

```yaml
verdict: APPROVE
reviewer_model: sonnet
reviewed_file: _mill/discussion.md
date: 2026-07-25
```

## Findings

### [NOTE] Only 1 of 5 inline `run()` call sites gets a dedicated regression test
**Section:** Testing / `_review_plan.py`'s 5 inline call sites
**Issue:** Scope requires fail-loud treatment at all 5 duplicated inline `parse_blocking_count(severity="BLOCKING")` sites (lines 284, 734, 947, 965, 982), but Testing specifies only one regression test (synchronous dispatch path).
**Fix:** Acceptable if the fix is applied via one identical helper call copy-pasted at each site (untested sites are then trivially equivalent), but worth an explicit note in the plan that the other 4 are covered by code-identity rather than a discrete test, in case any site's surrounding logic diverges (e.g. the double-retry NEED_CONTEXT paths at 947/965).

## Verdict

APPROVE
Source-grounded against current code (line numbers, docstrings, test assertions all verified); no new blocking gaps found in round 5.
MILL_REVIEW_END
