# Review: Wiki-daemon + bg-worker + test-suite robustness on Windows

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md (round 2)
date: 2026-05-30
```

## Findings

### [GAP] mill-start dead-worker recovery action unspecified
**Section:** Technical Context — `mill-start/SKILL.md`
**Issue:** The discussion says mill-start "should adopt the helper / liveness check for consistency" but does not specify the recovery action when `wait_for_bg_terminal` returns `("dead", pid)` for a discussion-review worker. Mill-start has no `stuck_type` machinery; the plan writer must choose between halt-with-user-error, auto-re-fire (mimicking mill-go autonomous policy), or another path — and these have meaningfully different UX.
**Fix:** Add a one-line recovery policy for mill-start's dead-worker case — e.g. "surface an error to the user and halt (mill-start is always interactive; no auto-retry)."

## Verdict

GAPS_FOUND
One gap: mill-start dead-worker recovery policy is unspecified, blocking the plan writer from implementing the SKILL.md change.