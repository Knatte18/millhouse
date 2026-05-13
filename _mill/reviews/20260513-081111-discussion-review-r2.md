Now I have enough to write the review.

# Review: (A) — Subprocess handling: timeout + JSON-exit + Windows detach

```yaml
verdict: APPROVE
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md (subprocess-fixes branch)
date: 2026-05-13
```

## Findings

### [NOTE] Watchdog reader threads undefined for non-PIPE stdout
**Section:** Decision: timeout-watchdog-stream-handling
**Issue:** The decision specifies reader threads on `proc.stdout.readline()` / `proc.stderr.readline()`, but `run` accepts `stdout=<filehandle>` overrides, which leave `proc.stdout = None`. No decision is stated for the `timeout=` + non-PIPE case.
**Fix:** Add a line clarifying the watchdog conditionally starts reader threads only when `proc.stdout is not None` (i.e. `stdout=PIPE`), or states the combination of `timeout=` + non-PIPE stdout is unsupported. No existing caller uses that combination, so no callers change, but the plan writer needs a decision rather than an inference.

### [NOTE] START sentinel "fail fast" requires caller updates not in scope
**Section:** Decision: worker-start-sentinel / Scope In
**Issue:** The decision states callers treat absent START sentinel after ~3 s as a "worker-never-started" failure, but `mill-start`, `mill-plan`, and `mill-go` skill files are not listed in scope. Without updating their poll loops, the sentinel is post-mortem-diagnostic only; the "fail fast" behavior is not deliverable in this task.
**Fix:** State explicitly whether the caller poll-loop update is in or out of scope. If out, say the sentinel's benefit in this task is diagnostic (distinguishes "never ran" from "slow start") and defer the fail-fast behavior to a follow-on.

## Verdict

APPROVE
All four fixes are well-specified; both notes are plan-writer guidance, not blockers.