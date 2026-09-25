MILL_REVIEW_BEGIN
# Review: Ask the parent session when stuck (parent_thread)

```yaml
duration_s: 165.8
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-09-25
```

## Findings

### [BLOCKING:design] go-handoff-gate conflates two guidance-injection paths
**Section:** `converted-sites` table, `go-handoff-gate` row.
**Issue:** The row merges the done-gate-after-fixer halt and the "unfixed nits" halt under one `retry` effect ("dispatch the fixer once more with the guidance"). The done-gate path dispatches `Agent(subagent_type: "mill-done-gate-fixer")` with a free-text brief, so guidance fits naturally. The nits path re-dispatches `millpy-fix.py --nits-only`, whose only args are `--review-file`, `--round`, `--nits-only`, `--prior-blocking <digest-path>` (verified in `plugins/mill/scripts/millpy-fix.py`) — none accept free-text guidance, and `--prior-blocking` is a fixed-format prior-BLOCKING digest, not a slot for arbitrary parent text.
**Fix:** Split the row's `retry` effect per sub-site, or specify how parent guidance reaches the NIT-fix CLI dispatch (e.g., appended to the review file before re-dispatch, or a new CLI flag) — the discussion currently has no answer for the nits sub-case.

## Verdict
REQUEST_CHANGES
go-handoff-gate's retry guidance-injection mechanism is undefined for the unfixed-nits sub-case.
MILL_REVIEW_END
