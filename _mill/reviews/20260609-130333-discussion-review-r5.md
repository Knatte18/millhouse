The conflicts finalize at line 196-202 is shared between both modes (it appears before the `args.mode` branch at line 216). Note line 199-201 passes `start_sha=None, snapshot_path=None, session_id=None`. This is the Gap D finalize. The discussion's claim that conflicts mode has no pre-commit/rev-parse in the prepare path is consistent with what I see in `_run_conflicts` (line 238-242: prepare just renders brief and calls `emit_prepare` with no rev-parse).

I have verified all the substantive technical claims in the discussion against source. The discussion is in round 5 with an extensive Q&A log showing prior gaps were resolved. Every concrete claim I checked holds.

MILL_REVIEW_BEGIN
# Review: agent-pipeline-reliability

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-09
```

## Findings

### [NOTE] session_id passed to finalize is a fresh UUID today
**Section:** Scope (In) / Decision: session-id-via-cli-arg
**Issue:** `millpy-fix.py` finalize currently passes `session_id=session_id` (the regenerated UUID at line 172), not `start_sha=None` alone — so Gap B is "wrong UUID," not "no UUID"; the plan should make `--session-id` the source so finalize stops minting a fresh value.
**Fix:** State explicitly that the finalize branch must drop the local `uuid.uuid4()` for session_id and read it solely from `--session-id`.

### [NOTE] Conflicts finalize is shared, not conflicts-only
**Section:** Scope (Out) / Decision: persist-start-sha-via-cli-arg
**Issue:** The `finalize_from_output(start_sha=None, ...)` call in `millpy-merge-in-subagent.py` sits before the `args.mode` branch, so it serves both conflicts and verify-fix; "conflicts finalize is correct as-is" is true but the code path is mode-agnostic.
**Fix:** Note that leaving start_sha=None there is intentionally correct for both modes, so a plan writer does not "fix" it.

## Verdict

APPROVE
All four gaps and every cited signature/contract verified against source; scope is decided and testable.
MILL_REVIEW_END
