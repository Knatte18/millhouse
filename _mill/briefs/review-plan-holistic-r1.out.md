MILL_REVIEW_BEGIN
# Review: Prefix session names with repo short name; add MH:orch session — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/
date: 2026-09-24
```

## Findings

### [NIT:scope] millpy-terminal's new ValueError branch has no test
**Location:** batch 2 / card 6
**Issue:** Card 6 adds `session_prefix(short, selected_slug)` with a `ValueError` -> `[mill-terminal] invalid session name: ...` / return 1 branch (`plugins/mill/scripts/millpy-terminal.py`), but the card's three new tests (POSIX, nt, fallback) only cover the success path — none exercises the ValueError branch.
**Fix:** Add one case (e.g. a slug or short name containing `:`) asserting the stderr message and exit code 1.

## Verdict

APPROVE
Plan is internally consistent, decisions are faithfully implemented, and claims verified against source hold.
MILL_REVIEW_END
