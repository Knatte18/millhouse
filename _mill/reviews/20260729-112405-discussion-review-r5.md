MILL_REVIEW_BEGIN
# Review: mill-plan/review validation false-positives, hard-fails, and truncated failure reasons

```yaml
verdict: APPROVE
reviewer_model: sonnetxhigh
reviewed_file: _mill/discussion.md
date: 2026-07-29
```

## Findings

### [NOTE] Technical Context overstates docstring completeness
**Section:** Technical context, `_plan_validate.py`'s `run()` bullet
**Issue:** Claims the docstring at lines 13-46 "enumerates every check key," but verified against source it omits `missing-overview`, `batch-index-parse`, `out-of-worktree-target`, and `batch-oversized` (all real, currently-emitted check keys).
**Fix:** Soften to "lists most check keys" or drop the completeness claim; the instruction to add `verify-excludes-edited-tagged-test` there still stands either way.

### [NOTE] Fix 3's header-scan bound (20 lines) has no stated rationale
**Section:** Decisions — Fix 3, step 3
**Issue:** The leading-comment scan is capped at "e.g. 20 lines" as a "safety net against pathological files," but real Go license headers (Apache/BSD boilerplate) can approach or exceed 20 lines, risking a silent false-negative for exactly the header-preceded-`//go:build` case round 1 added this scan to catch.
**Fix:** Either justify 20 as generously sufficient (e.g. cite typical header lengths) or document the false-negative risk as an accepted limitation, mirroring how the `Creates:` exclusion is explicitly called out.

## Verdict

APPROVE
Zero GAPs; all traced line numbers, function signatures, and call shapes verified accurate against current source.
MILL_REVIEW_END
