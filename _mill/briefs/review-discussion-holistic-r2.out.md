MILL_REVIEW_BEGIN
# Review: Repair two failing unit tests on main

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-09-24
```

## Findings

### [NIT:decision] Docstring/comment update conditional is loose
**Section:** Decisions / millpy-bg ban **Issue:** "Update docstrings only if they name millpy-bg" is grep-dependent; the test file shows no other millpy-bg mention (only line 27), so likely a no-op. **Fix:** None required; the plan writer can confirm with a grep.

## Verdict

APPROVE
Claims verified (fake signature at line 327, banned literal at line 27, done_gate at line 56); scope and decisions are clear.
MILL_REVIEW_END
