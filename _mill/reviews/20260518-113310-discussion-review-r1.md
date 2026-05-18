Now I have enough information to write the review.

# Review: Keep psmux TUI alive across calls for session continuity

```yaml
verdict: APPROVE
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-18
```

## Findings

### [NOTE] `list_sessions()` does not raise on no-server; returns `[]`
**Section:** Technical Context — Gotchas; Testing — Test S8
**Issue:** Gotchas states "`_psmux.list_sessions()` raises `PsmuxError` if the psmux server is not running." The actual code (`_psmux.py:127-129`) catches the "no server running" case internally and returns `[]` — it never raises for that condition. Test S8 is therefore based on a false premise: the real no-server case silently returns `[]`, so mocking `list_sessions` to raise PsmuxError is testing a different (non-"no server") failure path.
**Fix:** Correct the Gotchas note to say "`list_sessions()` returns `[]` when no server is running; it re-raises `PsmuxError` for all other failures." Update Test S8 to describe what it actually tests ("list_sessions raises PsmuxError for an unexpected error") rather than claiming it covers the no-server case.

## Verdict

APPROVE
One factual misstatement about `list_sessions` behavior; all design decisions are sound and implementation-ready.