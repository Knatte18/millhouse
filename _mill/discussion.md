# Discussion: millpy-implement/bg: Windows baseline-worktree teardown (WinError 145) and stale liveness reporting

```yaml
task: millpy-implement/bg: Windows baseline-worktree teardown (WinError 145) and stale liveness reporting
slug: mill-go-windows-baseline-teardown-and-bg-liveness
status: discussing
parent: main
```

## Problem

On Windows, three related-but-distinct bugs in mill-go's baseline pre-flight and background-worker
machinery have been reported a total of 7 times across 6 different downstream task branches
(2026-08-21 through 2026-08-26), all in the `NORCE-DrillingAndWells/Models` .NET repo except #917
(reported against millhouse itself):

1. **Teardown lock (#929, #928, #918, #909 — 4 duplicate reports).** The transient
   `verify-baseline-<hash>` worktree that `millpy-implement.py --stage baseline` creates to compute
   the module-wide/per-batch verify baseline fails to tear down: `git worktree remove --force` exits
   255, and the `_safe_rmtree` fallback fails with `WinError 145: The directory is not empty` on a
   path under `obj/**/staticwebassets` or `obj/Debug/net9.0` — a `dotnet`/MSBuild build-server process
   still holds a file handle open inside the throwaway worktree. The step is designed to never block
   the task (non-fatal), but the orphaned `.scratch/verify-baseline-*` directory is left on disk
   permanently, never cleaned up by this run or any later mill-go gate.

2. **Stale liveness reporting (#940, #959 — 2 duplicate reports).** `_bg.check_bg_status` (used by
   mill-go's poll-until-EXIT loop for backgrounded `millpy-bg.py` workers, including baseline
   pre-flight) reports a live worker as `"dead"` mid-run — while the actual command it's running
   (e.g. `millpy-implement.py --stage baseline`) is still executing as a child process and the log
   later completes normally with valid JSON output. This causes the orchestrator to give up on a
   baseline computation (or any other `millpy-bg`-backed job) that was in fact still succeeding.

3. **Baseline undercount (#917 — 1 related report).** The per-batch eager verify baseline computed by
   `_verify_baseline.compute_batch_baselines` (transient-checkout of the parent branch) failed to
   reproduce a real, deterministic 3-of-3 test-guard failure that a live worktree checkout of the
   *exact same committed content* (confirmed via `git diff` — byte-identical) reproduces every time,
   undercounting to 2-of-3. This caused a batch's `--stage finalize` to be misclassified as
   `stuck_type: verify` even though the extra failure was unrelated to the batch's own changes.

**Why now:** all 7 reports landed in the wiki backlog on the same day (2026-09-04) via
`mill-ghissues-to-tasks`; #1 has already had one fix attempt land (`07334bff` 2026-08-14,
`9cdd393f` 2026-08-20 — a `dotnet build-server shutdown` + single-retry fallback in
`_worktree.remove_safe`) but all 4 duplicate reports postdate that fix and still reproduce it, so
the existing mechanism is confirmed insufficient, not merely unshipped.

## Scope

**In:**
- Strengthen `_worktree.remove_safe`'s WinError145 rmtree-fallback retry (currently one retry) with
  a bounded multi-attempt retry/backoff, applied generically (not just the baseline call site) since
  the lock scenario is not baseline-specific.
- Add a permanent safety net: extend mill-cleanup's existing sweep pass to reclaim orphaned
  `.scratch/verify-baseline-*` directories that survive all in-process retries.
- Replace `_bg._probe_liveness`'s Windows liveness check. Root cause: `os.kill(pid, 0)` on Windows
  maps (via CPython's `posixmodule.c`) to `OpenProcess` + `TerminateProcess(handle, sig)` for any
  non-CTRL signal including `0` — it does not probe the process, it **kills** it. This explains the
  reported symptom exactly: the probed worker process dies (because the probe itself just terminated
  it with exit code 0), while its already-spawned child (`subprocess.run(cmd, stdout=log_f,
  stderr=STDOUT, creationflags=CREATE_NO_WINDOW)` inside `millpy-bg.py`'s `_worker_main`) survives
  independently and keeps writing to the inherited log-file handle, appearing to "complete later"
  from a process that `check_bg_status` already called dead. This is ordinary Windows parent/child
  process independence, not `CREATE_BREAKAWAY_FROM_JOB` acting twice: that flag is set only once, on
  the launcher→worker `Popen` call inside `_subprocess_util.popen_detached` (escaping the *launcher's*
  Win32 Job Object so the worker itself survives launcher exit) — the worker's own child command is
  spawned with plain `creationflags=CREATE_NO_WINDOW`, no breakaway flag, no Job Object relationship
  between worker and child at all. `TerminateProcess`ing the worker simply has no effect on an
  unrelated sibling process the OS never tied to it.
- Add a `ctypes`-based, non-destructive liveness probe for `sys.platform == "win32"`
  (`OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION)` + `GetExitCodeProcess`, no signal sent), gated
  so the POSIX `os.kill(pid, 0)` path is untouched.
- Extend the module-wide baseline's existing "control-check in `project_root`" corroboration pattern
  (`compute_baseline`) to the per-batch subset-diff-mismatch path in `_implementer_common`'s
  verify-gate consumer: when a live replay's failure-signature set is not a subset of the cached
  per-batch baseline, re-run the offending command once in `project_root` before blocking; if it
  reproduces there too, treat it as corroborated pre-existing, waive the batch, and persist the
  expanded signature set into the cached baseline (self-healing for the rest of the task).
- Unit tests for all of the above using mocked/injected boundaries (mocked `subprocess.run`,
  monkeypatched `os.kill`/the new ctypes call, `sys.platform` patched where needed to exercise
  Windows-only branches on this Linux dev machine).

**Out:**
- Root-causing the exact checkout-vs-live-worktree environment divergence behind #917's undercount
  itself. Neither the original reporter nor this discussion's exploration could pin it (confirmed
  byte-identical file content between branches; the temp checkout is a real `git worktree add` of the
  same repo, not obviously different in layout). It is not reproducible outside a live Windows
  environment. The fix targets the *consequence* (false `stuck_type: verify`) via corroboration, not
  the divergence's root cause.
- Any change to `millpy-bg.py`'s worker architecture beyond the liveness-probe fix (e.g. periodic
  heartbeat writes) — YAGNI once the probe stops being destructive; there is no remaining problem for
  a heartbeat to solve.
- Increasing `_worktree.remove_safe`'s retry to unbounded/exponential-backoff-to-timeout — would slow
  every worktree teardown (mill-merge, mill-cleanup, baseline) far more than the rare failure case
  warrants.
- Any live Windows reproduction or manual testing — not available in this dev environment; validated
  via mocked unit tests only, per existing project convention for infra scripts.

## Decisions

### teardown-retry-strengthen

- Decision: Change `_worktree.remove_safe`'s WinError145 rmtree-fallback from a single
  `dotnet build-server shutdown` + one retry to a bounded loop of up to 3 total rmtree attempts, each
  preceded by the same `dotnet build-server shutdown` call, with a short fixed backoff between
  attempts (e.g. 0.5s, then 1.5s) rather than no delay. Applied inside `remove_safe` itself so every
  caller (baseline pre-flight, mill-merge, mill-cleanup) benefits, not a baseline-only wrapper.
- Rationale: All 4 duplicate reports postdate the existing single-retry fix
  (`07334bff`/`9cdd393f`), so a Windows dotnet-build-server lock does not always clear within one
  immediate retry. A short bounded backoff gives the lock more realistic time to clear without
  meaningfully slowing the success path (only the failure path pays the extra latency, capped at
  ~2s worst case).
- Rejected: unbounded/exponential retry to a hard timeout (too much latency risk for a shared,
  frequently-called helper); baseline-call-site-only scoping (duplicates the same fix logic at every
  future caller that hits the identical dotnet-lock class of failure).

### teardown-safety-net

- Decision: Extend mill-cleanup's existing sweep pass to glob `.scratch/verify-baseline-*` per hub
  worktree and remove any directory no longer registered in `git worktree list` (i.e., orphaned after
  `git worktree remove` already failed and the retry loop above was also exhausted), reusing the
  junction-safe/`_safe_rmtree` primitives mill-cleanup already has available.
- Rationale: Even a strengthened retry loop cannot guarantee success against an arbitrarily
  long-lived build-server lock; the reports show the orphaned directory is currently never reclaimed
  by any later gate. A sweep-based safety net bounds worst-case disk cruft to "until the next
  mill-cleanup run" instead of "forever."
- Verification (detection criterion): "no longer registered in `git worktree list`" is deregistered
  by `git worktree remove --force` itself, independent of whether `_worktree.remove_safe`'s own
  trailing `git worktree prune` call ever runs. Empirically confirmed by reproduction (a worktree
  whose directory is made undeletable, so `git worktree remove --force` exits 255 exactly like the
  reported WinError145 case): the `.git/worktrees/<id>` administrative entry is removed and
  `git worktree list` stops showing the worktree even though the command's own exit code is
  non-zero and the physical directory survives on disk. This matches #918's and #909's explicit
  field reports ("no longer shows up in `git worktree list`", "an orphaned directory git itself has
  forgotten about") verbatim. `remove_safe`'s own `prune` call (skipped when `WorktreeLockedError`
  is raised, since the raise unwinds before reaching it) is therefore not the deregistration
  mechanism for this leak and its skip is irrelevant to the safety net's detection criterion —
  `git worktree remove --force` already deregisters internally, before it ever attempts to delete
  the working directory, regardless of the deletion's own success or failure. mill-plan should treat
  "not in `git worktree list`" as the correct, verified detection criterion, not merely an assumed
  one.
- Edge case (accepted race): because deregistration happens immediately when `git worktree remove
  --force` itself fails — before `remove_safe`'s own in-process rmtree retry loop (the strengthened
  3-attempt loop above) even starts — a concurrently-running mill-cleanup sweep in a different
  session could, in the worst case, target the same directory while the original process's retries
  are still in flight on it (bounded to the retry loop's own ~2s worst-case window). This is an
  accepted, benign race: both sides are only ever deleting the same already-abandoned directory tree
  (nothing is being freshly written there), so a second, concurrent `rmtree`/`safe_rmtree` attempt is
  idempotent-ish in effect — at worst one side finds less left to delete, never a data-loss or
  double-use hazard. No lock or skip-if-recently-touched guard is added for this window; mill-plan
  should not add one either unless a real failure mode (not just a theoretical double-delete) is
  found during implementation.
- Rejected: no safety net (matches current behavior — leaves the exact leak the 4 issues report);
  an mtime/age-based or remove-then-check-registration heuristic instead of registration alone (the
  registration criterion is already correct per the verification above, so an alternative heuristic
  would add complexity without fixing anything).

### bg-liveness-probe-fix

- Decision: Add a Windows-native, non-destructive liveness probe to `_bg.py`, used only when
  `sys.platform == "win32"`: `OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)` via
  `ctypes.windll.kernel32`, followed by `GetExitCodeProcess` to check for `STILL_ACTIVE`. On
  `OpenProcess` failure with `ERROR_ACCESS_DENIED` (WinError 5), treat as alive — a direct port of
  the existing POSIX `PermissionError` → `"affirmative-alive"` branch, not a new decision axis. The
  POSIX `os.kill(pid, 0)` path is untouched.
- Rationale: root-caused via CPython's Windows `os.kill` implementation — sig=0 is not
  special-cased there; it goes through `OpenProcess` + `TerminateProcess(handle, 0)`, which
  succeeds silently (no exception) if the process exists, killing it. `_probe_liveness`'s current
  code then reads "no exception raised" as `"affirmative-alive"`, when it actually just terminated
  the process it meant to check. This matches both reports precisely: the worker (whose PID is
  logged) dies immediately after being probed, while its own child subprocess — spawned via plain
  `subprocess.run(cmd, ..., creationflags=CREATE_NO_WINDOW)` inside `millpy-bg.py`'s `_worker_main`,
  with no `CREATE_BREAKAWAY_FROM_JOB` or other Job Object relationship tying it to the worker —
  continues and finishes normally as an ordinary, independent Windows process, writing further log
  output that arrives after `check_bg_status` already reported `"dead"`.
- Rejected: adding `psutil` as a dependency — not because the mill script family is stdlib-only
  project-wide (it isn't: `plugins/mill/pyproject.toml` already depends on `pyyaml`, `pygit2`, and
  `tinydb`), but on narrower merits: this fix is a single win32-only branch inside `_probe_liveness`,
  a new runtime dependency is unwarranted for it, and `ctypes.windll` keeps the fix symmetric with the
  untouched POSIX `os.kill(pid, 0)` path (stdlib on both sides, not stdlib on one and a third-party
  package on the other). `millpy-bg.py`'s worker fast-path docstring's "stdlib only" note is scoped to
  that file's own startup-perf hot path (`if "--_worker" in sys.argv:`), not a project-wide rule, and
  is cited here only as a convention this fix happens to stay consistent with, not as the reason
  itself. Heartbeat-based liveness as an alternative signal was also rejected (solves a problem that
  no longer exists once the probe itself stops being destructive).

### baseline-undercount-corroboration

- Decision: When `_implementer_common`'s verify-gate subset-diff check finds a live replay's
  failure-signature set is *not* a subset of the cached per-batch baseline (the case that currently
  produces a `stuck_type: verify` false positive), re-run the specific failing command once in a
  **fresh transient worktree checked out at the batch's own `start_sha`** (the commit `_run_verify_gate`'s
  live replay started from — captured and stored on `status.md` before the implementer made any
  commits, per `millpy-implement.py`'s existing `start_sha` capture/resume machinery) before blocking
  — reusing `_verify_baseline`'s existing `_checkout_parent_branch`/`_link_dependency_dirs`/
  `_worktree.remove_safe` transient-checkout machinery, generalized to accept an arbitrary ref/SHA
  rather than only a named branch. If the control run reproduces the same extra failure signature,
  treat it as corroborated pre-existing: waive the batch and merge the expanded signature set into
  the cached per-batch baseline so later batches in the same task don't re-pay the same false block.
  If the control run does *not* reproduce it, block exactly as today (genuine regression).
- Rationale: `compute_batch_baselines` was deliberately designed without this control-check step
  (per its own docstring, deferring to "finalize's own verify-replay run against the real,
  in-progress worktree" as the intended downstream corroboration point) — but #917 shows that replay
  currently only *compares against* the baseline, it never *corroborates a mismatch against live
  reality* the way the module-wide path already does. Extending the same, already-trusted pattern to
  this path closes exactly the gap #917 hit, without requiring the unreproducible
  checkout-vs-live-environment root cause to ever be found.
- **Correction (round-3 review):** the control run must target `start_sha`, never `project_root`
  itself. `project_root` is the exact same live task worktree the failing replay already ran in —
  by the time finalize's verify-gate runs, it already contains this batch's own commits. Re-running
  the identical command in the identical, already-modified worktree can only confirm the failure is
  deterministic, never that it's "unrelated to the batch's own changes": a genuine regression the
  batch itself introduced would reproduce there just as reliably as a true pre-existing failure would,
  so it cannot discriminate between the two cases the corroboration exists to tell apart. This is
  exactly why `compute_baseline`'s own control check is sound where the naive per-batch version above
  was not: it corroborates the transient-checkout failure against `project_root` at a point in the
  task lifecycle *before* any batch has made changes yet — a genuinely different, pre-task-changes
  environment, not the same one the primary run already used. Checking out `start_sha` fresh restores
  that same "known-prior-state, no task changes yet" property for the per-batch case. This still
  reuses the temp-checkout mechanism that #917 showed can itself under-detect vs. a live worktree —
  a residual, accepted risk (a false "not reproduced" on a signature that genuinely was present pre-batch,
  same environment-parity gap as #917), but strictly better than today's zero-corroboration behavior,
  and the question being asked here is narrower (does this one already-observed signature reproduce
  in the pre-batch state) than #917's original full-baseline-discovery use of the same mechanism.
- Rejected: continuing to chase the exact environment-divergence root cause (open-ended, not
  reproducible outside a live Windows session, and the original reporter already spent a session on
  it without success); diagnostic-only logging with no self-healing (leaves the false-block problem
  unresolved, just better-explained); re-running in `project_root` itself (round-3 review — cannot
  discriminate regression from pre-existing failure, see Correction above).

### fail-safe-boundary-preserved

- Decision: All new code (retry loop, ctypes probe, control-check re-run) stays inside the existing
  try/except fail-safe boundaries that already make the baseline pre-flight stage non-fatal on any
  infrastructure failure.
- Rationale: the baseline stage's entire design contract is "never blocks the task" — an imperfect
  fix must degrade to today's already-acceptable non-fatal behavior (baseline left unset, gate runs
  strict) rather than introduce a new hard-blocking failure mode.
- Rejected: none considered — this is a hard invariant of the existing system, not a new trade-off.

## Technical context

- `plugins/mill/scripts/_worktree.py`: `remove_safe()` (junction-strip → kill stale holders →
  `git worktree remove --force` → `_safe_rmtree` fallback → WinError145 handling with
  `dotnet build-server shutdown` + retry). The WinError145 handling to strengthen is in the
  `except OSError as exc` branch after the first `_safe_rmtree.safe_rmtree` call inside the fallback
  path. `_is_dir_not_empty_error()` already correctly detects WinError 145 by errno/message match —
  reuse it, don't reimplement.
- `plugins/mill/scripts/_bg.py`: `_probe_liveness()` is the sole site of the `os.kill(pid, 0)` bug.
  `check_bg_status()` and `is_bg_worker_alive()` both call it and need no changes themselves — they
  already correctly branch on the returned state tuple.
- `plugins/mill/scripts/millpy-bg.py`: worker fast-path is intentionally stdlib-only (`if "--_worker"
  in sys.argv:` branch at the top of the file, before any mill imports) — the new Windows probe
  belongs in `_bg.py` (consumed by the orchestrator side), not here.
- `plugins/mill/scripts/_vscode_processes.py`: `_probe_windows()` already wraps
  `ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)` for an
  unrelated purpose (matching VS Code window titles to workspace paths) — the closest existing
  in-repo convention for the exact win32 ctypes idiom the new `_bg.py` probe needs. Keep the new
  probe's `ctypes.windll.kernel32` usage style (constant naming, `False` for `bInheritHandle`, handle
  cleanup pattern) consistent with this precedent rather than inventing a new idiom.
- `plugins/mill/scripts/_subprocess_util.py`: `popen_detached()` — confirms `CREATE_BREAKAWAY_FROM_JOB`
  is applied only to the launcher→worker `Popen` call (escaping the *launcher's* Job Object so the
  worker survives launcher exit), not to the worker's own inner `subprocess.run(cmd, ...)` child.
  That child is an ordinary Windows process with no Job Object tie to the worker at all — which is
  why `TerminateProcess`ing the worker (the actual bg-liveness bug) doesn't affect it. No change
  needed here; included for corroboration only.
- `plugins/mill/scripts/_verify_baseline.py`: `compute_baseline()` (module-wide, has the 3-run/
  control-check algorithm already — see `_run_module_wide_verify_algorithm`) vs.
  `compute_batch_baselines()` (per-batch, 2-run union only, no control check — this asymmetry is
  what the undercount decision above closes on the consumer side).
- `plugins/mill/scripts/_implementer_common.py`: subset-diff waiver logic around line 1057-1068
  (`normalized_replay.issubset(normalized_baseline)`) — this is the exact site that needs the new
  control-check-on-mismatch step before it blocks with `stuck_type: verify`.
- `plugins/mill/skills/mill-cleanup/` (script backing it, likely `millpy-cleanup.py` or similar under
  `plugins/mill/scripts/`) — existing sweep pass to extend with the orphaned
  `.scratch/verify-baseline-*` reclamation; mill-plan should locate the exact sweep-loop function
  during planning.
- Fix history for context (do not re-do): `07334bff` (2026-08-14, first dotnet-build-server-shutdown
  fix, more general Windows verify/baseline lock handling) and `9cdd393f` (2026-08-20, worktree
  teardown WinError145/long-path specific hardening) — both already landed; this task's teardown fix
  builds on top of, not instead of, that existing code path.

## Testing

- `_worktree.remove_safe` retry/backoff: unit test mocking `_subprocess_util.run` (git calls),
  `_safe_rmtree.safe_rmtree` (to raise `OSError` matching WinError145 a controlled number of times —
  e.g. fails twice then succeeds on the 3rd attempt → asserts success; fails all 3 → asserts
  `WorktreeLockedError` still raised as today), **and the module-level `subprocess.run` imported
  directly in `_worktree.py`** (the actual call site of `dotnet build-server shutdown` — it is not
  routed through `_subprocess_util.run`, so that seam alone cannot intercept or count it; mocking only
  `_subprocess_util.run` would let a real `dotnet build-server shutdown` fire during the test).
  Asserts `subprocess.run(["dotnet", "build-server", "shutdown"], ...)` is invoked once per retry,
  not just once total. TDD candidate.
- mill-cleanup sweep extension: unit test with a fixture `.scratch/` containing both a
  currently-registered worktree dir (must survive) and an orphaned `verify-baseline-*` dir not in
  `git worktree list` output (must be removed).
- `_bg._probe_liveness` Windows probe: unit test monkeypatching `sys.platform = "win32"` and
  `ctypes.windll.kernel32.OpenProcess`/`GetExitCodeProcess` (mocked, since real `ctypes.windll` isn't
  available on Linux) to cover: process alive → `"affirmative-alive"`; process exited (`STILL_ACTIVE`
  false) → not alive; `OpenProcess` fails with access-denied → `"affirmative-alive"` (mirrors POSIX
  `PermissionError` branch); `OpenProcess` fails with process-not-found → `"dead"`. Also a regression
  test confirming the POSIX branch (`os.kill(pid, 0)`) is untouched when `sys.platform != "win32"`.
  TDD candidate — this is the highest-value test in the task, since it's the one that would have
  caught the actual reported bug.
- Baseline-undercount control-check corroboration: unit test on the subset-diff-mismatch branch in
  `_implementer_common`, injecting a live-replay signature set that is NOT a subset of the cached
  baseline, mocking the `start_sha`-checkout control-check run (the generalized
  `_checkout_parent_branch`-style transient worktree, not `project_root`) to (a) reproduce the extra
  failure → assert waived + baseline updated to include it, and (b) not reproduce it → assert still
  blocks with `stuck_type: verify` exactly as today. Also assert the control check's checkout target
  is `start_sha`, not `project_root` — a regression test for the round-3 review correction above.
  TDD candidate.
- All tests run via the existing `plugins/mill/unit_tests/test-*.py` + `run-all.py` convention, no
  real git/LLM/Windows dependency, matching the project's existing in-memory/tempfile fixture
  pattern.

## Q&A log

- **Q:** Include all 3 sub-bugs (teardown lock, bg-liveness false-dead, baseline undercount) in scope? **A:** [auto-pick] All three, as folded in the wiki task. **Why:** the brief explicitly lists all 7 source issues under this one task.
- **Q:** Teardown lock — the existing `07334bff`/`9cdd393f` shutdown+retry fix already exists but all 4 duplicate reports postdate it; strengthen it rather than assume it's unimplemented? **A:** [auto-pick] Yes, strengthen the existing mechanism. **Why:** confirmed via commit dates (2026-08-14/20) vs. issue timestamps (2026-08-21 to 08-24) that the fix landed before all 4 reports and still failed.
- **Q:** bg-liveness — replace the Windows leg of the probe with a `ctypes`-based non-destructive check rather than adding `psutil`? **A:** [auto-pick] ctypes-based, stdlib-only, platform-gated. **Why:** matches the existing stdlib-only convention for mill scripts (see `millpy-bg.py` worker fast-path docstring); root cause confirmed via CPython's Windows `os.kill` implementation actually calling `TerminateProcess`.
- **Q:** Baseline undercount — extend the existing module-wide control-check corroboration pattern to the per-batch path rather than keep chasing the unreproducible checkout/live divergence? **A:** [auto-pick] Extend the control-check pattern. **Why:** the divergence itself isn't reproducible outside Windows and the original reporter already failed to root-cause it in a live session; the control-check pattern already exists and is trusted for the module-wide case.
- **Q:** Testing approach given no Windows CI/repro in this dev environment? **A:** [auto-pick] Mocked/injected-boundary unit tests, monkeypatching `sys.platform` and the relevant subprocess/ctypes/os calls. **Why:** matches existing project unit-test convention (in-memory/tempfile fixtures, no real git/LLM/Windows dependency).
- **Q:** Retry count/backoff for the WinError145 rmtree fallback? **A:** [auto-pick] Bounded 3-attempt retry with short fixed backoff, combined with a permanent cleanup safety net. **Why:** balances added latency (only on the failure path, ~2s worst case) against the demonstrated insufficiency of a single retry.
- **Q:** Scope the strengthened retry generically in `remove_safe`, or baseline-call-site-only? **A:** [auto-pick] Generic, in `remove_safe` itself. **Why:** the dotnet-lock scenario isn't baseline-specific — mill-merge/mill-cleanup teardown hit the identical failure class.
- **Q:** Add a mill-cleanup sweep safety net for dirs that still fail teardown after retries? **A:** [auto-pick] Yes, extend the existing sweep pass. **Why:** even a strengthened retry can't guarantee success against an arbitrarily long-lived lock; without a sweep the leak is permanent, matching what the 4 issues report today.
- **Q:** Must all new code stay inside the existing "never blocks the task" fail-safe boundary? **A:** [auto-pick] Yes, exactly. **Why:** hard invariant of the baseline pre-flight stage's existing design contract.
- **Q:** Where does the new Windows-native liveness probe live? **A:** [auto-pick] Small platform-gated helper inside `_bg.py`. **Why:** consumed only by the orchestrator side (`_probe_liveness`), not the stdlib-only worker fast-path in `millpy-bg.py`.
- **Q:** Add a periodic heartbeat write to the worker log as defense-in-depth? **A:** [auto-pick] No. **Why:** YAGNI — once the probe stops being destructive, there is no remaining liveness-detection problem for a heartbeat to solve.
- **Q:** Does the new Windows probe need an access-denied-but-alive branch mirroring POSIX's `PermissionError`? **A:** [auto-pick] Yes. **Why:** straight port of the existing POSIX semantics, not a new decision axis — `ERROR_ACCESS_DENIED` from `OpenProcess` means the process exists but we lack query rights, exactly analogous to POSIX `EPERM`.
- **Q:** Should the new control-check corroboration self-heal the cached baseline on a reproduced mismatch? **A:** [auto-pick] Yes, waive and persist the expanded signature set. **Why:** avoids re-paying the same false block for every later batch in the same task once the pre-existing failure is corroborated once.
- **Q:** Test strategy for all three fixes given no Windows repro? **A:** [auto-pick] Mocked/injected-boundary unit tests for every Windows-only branch. **Why:** same rationale as the earlier testing question — matches existing project convention, no live Windows dependency required.
