MILL_REVIEW_BEGIN
# Review: Repair two failing unit tests on main — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-09-24
```

## Findings

### [NIT:consistency] Missing space after comma in BANNED_LITERALS
**Location:** `plugins/mill/unit_tests/test-mill-go-base-agent-only.py:27`
**Issue:** `("psmux","dispatch == subprocess")` has no space after the comma, unlike the neighbouring `COMPANIONS` tuple on line 26.
**Fix:** Write `("psmux", "dispatch == subprocess")`.

## Verdict

APPROVE
Both cards are realised as planned. The fake accepts `done_gate=None` keyword-only, and `millpy-bg` is dropped from the banned literals. No out-of-plan files.
MILL_REVIEW_END
