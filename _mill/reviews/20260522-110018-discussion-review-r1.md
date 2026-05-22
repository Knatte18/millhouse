# Review: V3 wiki module with daemon and in-process cache

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-22
```

## Findings

### [GAP] Startup sequence: gitignore maintenance vs O_EXCL ordering unspecified
**Section:** `state-file-and-log` + `spawn-race-and-staleness`
**Issue:** Both sections say their activity happens "on startup" but neither specifies which runs first. If gitignore maintenance (commit + push) runs before O_EXCL, two racing daemons can both attempt that push, producing a non-fast-forward conflict neither is equipped to handle at that point in startup. The correct ordering — O_EXCL first, gitignore maintenance second (only by the winner) — must be stated explicitly.
**Fix:** Add one sentence to `spawn-race-and-staleness`: "O_EXCL must be the first startup action; `.gitignore` housekeeping runs only after the daemon has won the O_EXCL race."

### [NOTE] CAS client-retry count is "bounded" but unspecified
**Section:** `write-commit-push-cas`
**Issue:** "Bounded retries, then raises" gives the plan writer no concrete number. The integration test asserts "CAS forces one to retry and both edits survive" — it depends on at least 1 retry succeeding.
**Fix:** State a concrete default (e.g., 3 retries) so the plan writer doesn't invent an arbitrary value and the integration test can assert the right behaviour.

### [NOTE] `protocol_version` canonical constant location not named
**Section:** `spawn-race-and-staleness` + `api-surface`
**Issue:** The client compares the state file's `protocol_version` against an expected value to detect stale daemons, but the discussion doesn't say where that constant lives. Both `_client.py` and `_server.py` need the same value; without a named home (e.g., a top-level constant in `_daemon.py` or `wiki/__init__.py`) the plan writer may define it in two places and let them drift.
**Fix:** Name the single source of truth for `protocol_version` in the module layout description.

## Verdict

GAPS_FOUND
One startup-ordering ambiguity creates a real spawn-race bug; two notes are non-blocking.