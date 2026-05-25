# Review: Finish V3 wiki adoption — complete batch 3 port and test sweep

```yaml
verdict: APPROVE
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md (round 3)
date: 2026-05-25
```

## Findings

### [NOTE] `merge_tasks` set_phase tuple type hint mismatch
**Section:** Technical context — V3 wiki API table
**Issue:** Table documents `set_phase: tuple[int | str, str | None] | None` but `_client.py:294` has `set_phase: tuple[str, str | None] | None` — first element is `str` only, not `int | str`.
**Fix:** Update the table entry to reflect the actual annotation (`str`), or note that passing an int slug also works at runtime (consistent with the standalone `set_phase` function's `int | str` contract).

## Verdict

APPROVE
All scope, constraints, decisions, and technical claims are verified against source; one minor type-hint discrepancy in the API table, not a blocker.