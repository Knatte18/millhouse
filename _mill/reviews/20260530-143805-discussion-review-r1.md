# Review: Wiki-daemon + bg-worker + test-suite robustness on Windows

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-30
```

## Findings

### [GAP] `--resume` recovery path lacks implementation route
**Section:** `### 391-detect-and-recover`, `### 391-infrastructure-stuck-policy`
**Issue:** Both decisions say "pass `--resume` for the implementer so the warm session is reused," but `millpy-implement.py` accepts only a positional `batch_name`, hardcodes `resume=False` (line 186), and is absent from Technical Context. The existing mill-go Resume path for `running` state (SKILL.md:318) explicitly says "session is dead and cannot be re-attached — fresh batch start is the correct recovery," directly contradicting the `--resume` claim. Mill-plan has no described mechanism to thread the `implementer_session` ID from status.md through to `_llm_claude.run(resume=True)`.
**Fix:** Either (a) add `millpy-implement.py` to Technical Context with a new `--resume-session <id>` flag and explain how it differs from the general `running`-state crash-recovery, or (b) clarify that recovery is a fresh re-fire (no `--resume`), same as the existing path, and remove the `--resume` language from both decisions.

### [NOTE] `wait_for_socket_reachable` API mismatch with current spawn loop
**Section:** `### 395-hardening-not-live-bug`, Technical Context
**Issue:** The proposed `wait_for_socket_reachable(host, port, *, timeout, interval)` signature assumes host/port are known before the call. The current `_ensure_daemon` spawn poll (`:521-533`) reads the state file *inside* the loop to discover host/port, because the daemon writes that file on startup. Mill-plan must either restructure the outer loop to poll the state file first and only call the helper once host/port are known, or use a different helper signature.
**Fix:** Acknowledge the restructuring in the decision (or note "mill-plan's call on the exact loop shape") so the plan writer knows the current loop cannot be mechanically split without a design choice.

## Verdict

GAPS_FOUND
One blocking gap: the `--resume` recovery mechanism has no described implementation path in `millpy-implement.py`.