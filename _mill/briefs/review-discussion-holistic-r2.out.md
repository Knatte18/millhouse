MILL_REVIEW_BEGIN
# Review: Skill doc/table accuracy gaps across mill-groom, mill-start/mill-plan, and implementer-brief

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-25
```

All four issues carry a clear Decision with rationale + rejected alternative; scope in/out is explicit; every load-bearing source claim verified: mill-groom Entry check stale junction at lines 17-25, mill-start's two "Thread `--round`" sentences (166, 196), `millpy-review-discussion.py`'s literal `--agent-output required for finalize stage` (line 147), mill-go step 6's `output_path`->`--agent-output` contract (lines 116/153), and mill-plan's entry table catch-all halt for unrecognized phases (line 37). The r1 two-edit-site gap is resolved. Only minor NOTEs below.

## Findings

### [NOTE] Trim must preserve global auto-NOTE-FIX rule
**Section:** Decisions -> mill-start-discussion-fix-handoff-gap (edit site 2, ~line 37)
**Issue:** Delegating the `--auto` restatement "verbatim" to interactive 4b removes its "best judgment / PUSH BACK unavailable" NOTE-handling wording; that semantics is only separately guaranteed by the `--auto` subsection's global line ("every gap AND every NOTE... treated as FIX... PUSH BACK unavailable").
**Fix:** Note in the plan that the trim removes only the status-append/commit enumeration, and that auto NOTE-resolution semantics must remain sourced from that existing global `--auto` rule so nothing is lost.

### [NOTE] verify: null vs markdown-lint equivalent left open
**Section:** Testing (last bullet)
**Issue:** "mill-plan should set `verify: null` (or the repo's markdown-lint-only equivalent, if one exists)" leaves the plan-time choice unresolved.
**Fix:** State the concrete expectation (this uv/Python repo has no markdown-lint gate -> `verify: null`) so the plan writer does not re-investigate.

## Verdict

APPROVE
Thorough, well-grounded; zero blocking gaps, two minor clarifications only.
MILL_REVIEW_END
