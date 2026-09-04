MILL_REVIEW_BEGIN
# Review: millpy-implement/bg: Windows baseline-worktree teardown (WinError 145) and stale liveness reporting

```yaml
duration_s: 371.0
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

### [BLOCKING:design] Per-batch corroboration control-check reruns in an already-tainted environment
**Section:** Decisions > `baseline-undercount-corroboration`. **Issue:** The control-check reruns the failing command "directly in `project_root`," but `project_root` is exactly where the live replay (`_run_verify_gate` inside `_forward_output`/`_run_verify_gates`, `_implementer_common.py` lines ~1719-1765, 1052-1072) already ran and failed — it already contains this batch's own new commits. Re-running the identical command in the identical, already-modified worktree can only confirm determinism (not flakiness), never "unrelated to the batch's own changes" as the rationale claims; it cannot distinguish a genuine regression introduced by this batch from a true pre-existing failure. This differs from `compute_baseline`'s control check (`_verify_baseline.py` `_run_module_wide_verify_algorithm`), which corroborates a transient-parent-branch-checkout failure against `project_root` *before* any task changes exist — a meaningfully different environment at that point in the task lifecycle. **Fix:** Specify that the corroboration run must target a state that predates this batch's changes (e.g. a fresh parent-branch/`start_sha` checkout), not `project_root` itself, or otherwise justify why re-running in the tainted worktree is sound.

### [NIT:consistency] Retry-loop test plan doesn't cover the actual `dotnet build-server shutdown` call site
**Demoted-from:** BLOCKING
**Section:** Testing > `_worktree.remove_safe` retry/backoff. **Issue:** The testing description says to mock `_subprocess_util.run` (git calls) and `_safe_rmtree.safe_rmtree`, then "asserts `dotnet build-server shutdown` is invoked once per retry." But `remove_safe`'s dotnet-shutdown call (`_worktree.py` lines 344-350) uses the raw stdlib `subprocess.run` imported directly in that module, never `_subprocess_util.run` — mocking only the two named seams cannot intercept or count that call, and would let a real `dotnet build-server shutdown` subprocess fire during a unit test. **Fix:** Add `subprocess.run` (module-level, in `_worktree.py`) to the explicit mock list for this test.

### [NIT:scope] Technical Context omits existing `OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION,...)` precedent
**Section:** Technical context / `bg-liveness-probe-fix`. **Issue:** `_vscode_processes.py`'s `_probe_windows` already wraps `ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)` for an unrelated purpose; the discussion's Technical Context list doesn't cite it even though it's the closest existing convention for the exact win32 call the new probe proposes. **Fix:** Note this file in Technical Context so mill-plan keeps the new probe's ctypes idiom consistent with it.

## Verdict

REQUEST_CHANGES
Per-batch corroboration control-check logic rests on a false premise about which environment it validates against.
_Note: 1 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 1._
MILL_REVIEW_END
