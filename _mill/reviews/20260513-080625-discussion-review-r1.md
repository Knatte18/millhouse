Now I have everything I need to write the review.

# Review: (A) — Subprocess handling: timeout + JSON-exit + Windows detach

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-13
```

## Findings

### [GAP] millpy-implement-holistic.py caller unresolved

**Section:** Scope / Decision: session-id-propagation  
**Issue:** `millpy-implement-holistic.py` exists (confirmed) and calls `_forward_output(output, project_root)` at line 176 with no `session_id`. A `session_id = str(uuid.uuid4())` is in scope at that call site (line 113). The discussion defers with "(if it exists; check during plan)" and the `session-id-propagation` decision names only `millpy-implement.py`'s two call sites. Plan writers cannot write complete scope without a concrete decision.  
**Fix:** Add a decision: either include `millpy-implement-holistic.py`'s call site in the session_id plumbing (same rationale applies), or explicitly exclude it with a reason.

### [GAP] Integration test for #271 requires job-bound parent — mechanism unspecified

**Section:** Testing → Integration scenarios  
**Issue:** The test spec says "launch `millpy-bg.py` from inside a parent that has `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` set on its job" but does not specify how the test ensures that condition. If the test runner is not in a job-bound process (e.g. plain cmd.exe), both the old and new code produce the same result, and the test vacuously passes without verifying the fix.  
**Fix:** Specify whether the test manufactures the job condition via ctypes (`SetInformationJobObject`) or explicitly requires the test to be run from within VS Code / CC Bash and documents that requirement as a `# MUST run from VS Code / CC Bash` guard.

## Verdict

GAPS_FOUND  
Two decisions deferred to plan that a plan writer cannot safely resolve without returning to the discussion.

---

### [NOTE] `proc.pid` in `millpy-bg.py` launcher changes meaning after two-stage launch

**Section:** Decision: detach-mechanism-windows  
**Issue:** After the fix, `popen_detached` returns a handle for the intermediate cmd.exe, which exits immediately. `millpy-bg.py`'s launcher prints `pid={proc.pid}`, so the printed PID will be cmd.exe's (stale), not the worker's. Skills only poll `log=<path>` and don't act on the PID value, so this is non-breaking — but the authoritative worker PID moves to the `[mill-bg] WORKER PID=...` sentinel, silently.  
**Fix:** Document this shift explicitly (e.g., "the printed `pid=` is the launcher-shim PID; the worker PID is in the START sentinel") so plan writers know callers don't need updating.