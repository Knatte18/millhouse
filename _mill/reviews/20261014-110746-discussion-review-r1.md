# Review: Instrument and bound the verify runner

```yaml
verdict: APPROVE
reviewer_model: orchestrator
reviewed_file: _mill/discussion.md
date: 2026-10-14
```

## Findings

### [NIT:scope] A named verify target is already red, and the waiver that used to hide it is gone

**Demoted-from:** BLOCKING
**Section:** Testing — "`millpy-bg.py` — `test-millpy-bg.py` / `test-bg-liveness.py`: heartbeat line format includes `elapsed=` and `cmd=`, long commands truncated; liveness parsing unaffected."

**Issue:** `test-bg-liveness.py` exits 1 on this worktree today: `Ran 32 tests ... FAILED (failures=3)`, namely `test_log_oserror_fallback_to_mtime`, `test_systemerror_fallback_to_mtime` and `test_check_bg_status_killed_before_json_fresh_mtime`.
It is one of `main`'s pre-existing failures, and the companion task (`e408e454`) removed the baseline waiver that previously let a gate pass despite them.
A batch whose `verify:` covers that file therefore cannot go green, and mill-go halts on it.
The overlap is not incidental: all three failures are in liveness/mtime parsing, which is exactly what the discussion wants to prove "unaffected".
Every other named target passes — `test-status.py`, `test-done-gate.py`, `test-millpy-bg.py`, `test-millpy-merge-in-subagent.py`, `test-implementer-common.py` — so this is the only one.
Constraints does not mention pre-existing failures at all, and the template's own `done_gate` comment already warns "never set this to a command that is currently failing on pre-existing debt".

**Suggested fix:** Decide it here rather than leaving it to the plan. Either scope the heartbeat batch's `verify:` to `test-millpy-bg.py` alone and state how "liveness parsing unaffected" is demonstrated instead (a targeted new case, or an asserted-unchanged failure count), or declare the three liveness failures in scope and fix them in their own batch ahead of the heartbeat change. Add a Constraints bullet naming the pre-existing-failure hazard so later batches do not re-introduce it.

### [NIT:scope] `dotnet build-server shutdown` is both out of scope and routed through the runner

**Section:** Scope/Out — "The existing `dotnet build-server shutdown` post-step and the dotnet lock-race retry — kept as they are, now routed through the new runner."

**Issue:** The two halves of that bullet disagree for the shutdown step. The lock-race retry is unambiguously routed — Decisions/Timeout gives it its own budget and Observability gives it the `<batch>:retry` label. The shutdown post-step (`_done_gate.py:189`, `subprocess.run(["dotnet", "build-server", "shutdown"], capture_output=True, timeout=30)`) is not a verify command, and routing it through `run_verify` would hand it a label, a timeout budget, a first-run marker and a `## Verify log` row. A plan writer could reasonably leave it untouched or convert it.

**Suggested fix:** Split the bullet: say the lock-race retry is routed and the `build-server shutdown` call is left exactly as it is.

### [NIT:consistency] Config-sync testing is non-committal and weaker than the existing precedent

**Section:** Testing — "Config sync: whatever existing test checks template/hub key parity covers `pipeline.verify_timeout_minutes`; if none, assert the key exists in the template."

**Issue:** The precedent exists and the discussion did not find it: `test-ask-thread.py:229-234` loads both the hub `mill-config.yaml` and `plugins/mill/templates/mill-config.yaml` and asserts `pipeline.parent_escalation_timeout_minutes` equals the module default in each. The fallback offered here is weaker than that — template only, existence only — and "whatever existing test" leaves the plan to rediscover it.

**Suggested fix:** Name the pattern: assert `pipeline.verify_timeout_minutes` is present in both files and equals the module default, mirroring `test-ask-thread.py`.

## Verdict

APPROVE
Scope, decisions and technical context are accurate against worktree source and the brief is fully covered — including the pipe trap, the per-worktree first-run semantics and the rejection of the 30-minute floor — but the testing plan names a verify target that is already failing on `main` now that the baseline waiver is gone.
_Note: 1 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 0._
