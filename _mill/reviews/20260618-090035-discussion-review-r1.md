MILL_REVIEW_BEGIN
# Review: Fix agent error recovery, implementer/review false-success contracts, VS Code watcher, and plan-validator Deletes

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-18
```

## Findings

### [NOTE] API-error marker matching may over/under-match
**Section:** Decision 499-502-agent-error-recovery (point 3) + Note
**Issue:** The marker set (`API Error`, `Internal server error`, HTTP 5xx) is named but the matching method (substring vs regex, case sensitivity, anchoring) is left to the plan; a legitimate stuck `reason` string containing "API Error" prose could be misrouted to `transient`.
**Fix:** Have the plan pin the exact matcher (e.g. case-insensitive substring on the captured `.out.md` body only when no JSON parsed) so Case 2 (plain garbage) stays `logic` and the new test asserts both directions.

### [NOTE] mill-go SKILL insertion point line refs slightly off
**Section:** Decision 499-502 (point 1) / Technical context
**Issue:** Text says insert "between Call Agent tool and Capture output" and cites L105-138 / properties L136-137; in source the dispatch is a 6-step numbered list (Call Agent = step 3, Capture = step 4) with properties at L133-137 — conceptually correct but the cited line numbers are approximate.
**Fix:** None required for plan correctness; planner should locate by step name (between step 3 and step 4), not raw line number.

## Verdict

APPROVE
All seven decisions are grounded, scoped, and tested; only minor non-blocking matcher/line-ref notes.
MILL_REVIEW_END
