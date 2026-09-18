MILL_REVIEW_BEGIN
# Review: mill-plan: entry-gate wait for upstream mill-start misses discussion-gap-fix-r{N} and races the pinning commit — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-09-18
```

## Findings

### [NIT:consistency] Clean-tree sentence placed in a new paragraph, not the opening one
**Location:** `plugins/mill/scripts/_phase_wait.py:38-41`
**Issue:** Card 1 asks for "one sentence to the docstring's opening summary paragraph" mentioning clean-tree gating, but the implementation adds it as a separate new paragraph (line 40-41) after a blank line, rather than extending the single-sentence opening paragraph (line 38) in place.
**Fix:** Merge the clean-tree sentence into the same paragraph as the opening summary line, or accept as an immaterial doc-formatting deviation.

## Verdict

APPROVE
All three cards (signature extension, call-site wiring, five new test cases) faithfully match the plan; only a trivial docstring-formatting nit found.
MILL_REVIEW_END
