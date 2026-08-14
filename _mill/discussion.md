# Discussion: mill-go/millpy-implement: Windows dotnet build-server file-lock races in verify/baseline stages

```yaml
task: mill-go/millpy-implement: Windows dotnet build-server file-lock races in verify/baseline stages
slug: mill-go-windows-buildserver-lock-hygiene
status: discussing
parent: main
```

## Problem

On Windows, two independent parts of the `mill-go` implementer pipeline race lingering
`dotnet`/MSBuild file locks left behind by a *previous* `dotnet` process in the same
worktree, and both currently surface the race as a hard failure instead of self-healing:

1. **Finalize-stage verify replay** (`millpy-implement.py --stage finalize`, and the
   identical `millpy-fix.py --stage finalize` path): after an implementer agent finishes a
   batch whose `verify:` is a `dotnet test`/`dotnet build` command, finalize immediately
   re-runs that same command as a regression guard. On Windows, the implementer's own
   just-finished `testhost.exe` process can still hold file handles into `bin/`/`obj/`
   when the replay starts, so the replay's MSBuild copy step fails with `MSB3021`/`MSB3027`
   ("the process cannot access the file ... locked by testhost"). This is misclassified as a
   genuine `stuck_type: verify` regression and escalated to the operator, even though a bare
   retry moments later (once Windows releases the handle) succeeds with no code changes
   (GitHub #848, #860).
2. **Baseline-stage disposable-worktree teardown** (`millpy-implement.py --stage baseline`):
   the task-scoped module-wide/per-batch verify baseline is computed in a transient worktree
   at `.scratch/verify-baseline-<hash>/`, torn down afterward via `_worktree.remove_safe`.
   On Windows, a lingering lock inside a `dotnet build`-generated `obj/` tree makes
   `git worktree remove --force` fail, and the `_safe_rmtree.safe_rmtree` fallback then
   raises a raw, uncaught `[WinError 145] The directory is not empty` that propagates all
   the way out of `_run_baseline_stage` — crashing the whole `--stage baseline` invocation
   instead of the graceful "log and continue to batch 1" degradation the function's own
   docstring already promises and `mill-go-base/SKILL.md` already documents as the expected
   behavior on baseline-computation failure (GitHub #846, #859).

**Why now:** both races were observed directly during real `mill-go` runs on a Windows
build server (`NORCE-DrillingAndWells/Models`, 2026-08-12 and 2026-08-13), each requiring
manual operator intervention (a stuck-report investigation, or a stray `.scratch/` dir) for
something that was, in both cases, a pure timing artifact with no underlying code problem.

## Scope

**In:**
- `_implementer_common._run_verify_gate`: detect the MSB3021/MSB3027 lock signature in a
  failed dotnet verify command's output and, on match, run `dotnet build-server shutdown`
  then retry the same verify command once before returning a stuck dict.
- `_worktree.remove_safe`: on Windows, when the `_safe_rmtree.safe_rmtree` fallback raises
  an OSError with `winerror == 145` (directory not empty), run a best-effort
  `dotnet build-server shutdown` and retry the fallback once before giving up.
- `millpy-implement.py` `_run_baseline_stage`: wrap both `_worktree.remove_safe` call sites
  (the shared-checkout-failure early-return path and the `finally` teardown) so a
  still-failing teardown (after `remove_safe`'s own retry is exhausted) is logged to stderr
  and swallowed, never propagates, and the stage's two JSON summary lines are always printed.
- Unit tests for both retry paths using the existing `sys.platform`/`subprocess.run` mocking
  convention (see `test-implementer-common.py`'s `#556` tests), plus a regression test
  confirming `_run_baseline_stage` never raises even when `remove_safe` is fully exhausted.

**Out:**
- `millpy-fix.py` and `millpy-merge-in.py` need no separate code change — they call the same
  shared `_implementer_common.finalize_from_output` / `_forward_output` → `_run_verify_gate`
  path, so the finalize-stage fix covers them for free.
- No change to the existing unconditional post-run `dotnet build-server shutdown` in
  `_run_verify_gate` (added by #554/#556) — it keeps firing exactly as today, regardless of
  exit code. The new signature-triggered retry is additive.
- No change to `_is_benign_windows_cleanup` / `_has_windows_cleanup_race_signature`'s
  existing signature list (`unlinkat`, `access is denied`, `winerror 5`, `winerror 32`) or
  their "treat as pass" semantics — see Decision `finalize-retry-not-benign-passthrough`
  below for why extending that list would not work for this race.
- No change to the Handoff done-gate pattern in `handoff.md` — it already runs its own
  post-gate shutdown; not part of this task's observed failure modes.
- No dotnet-project detection (scanning for `*.csproj`/`*.sln`) before attempting a shutdown
  in either fix — both shutdown calls are unconditional and best-effort.
- No change to `_safe_rmtree.safe_rmtree`'s own junction-stripping/blacklist/rmtree logic —
  the retry wraps the *caller* (`remove_safe`), not `safe_rmtree` itself.

## Decisions

### finalize-retry-not-benign-passthrough

- Decision: fix the finalize-stage (and any other dotnet verify call's) MSB3021/MSB3027
  lock race by detecting the signature in the failed output, running
  `dotnet build-server shutdown`, and re-running the *actual* verify command once — not by
  adding MSB3021/MSB3027 to `_is_benign_windows_cleanup`'s existing "treat as pass" signature
  list.
- Rationale: `_is_benign_windows_cleanup` only returns "benign, treat as pass" when the
  output has zero failure markers. But an MSBuild run that hits MSB3021/MSB3027 always ends
  with `Build FAILED.` in its output, which already matches the existing
  `"build failed"` failure-marker substring check — so `has_failure_marker` is always `True`
  whenever the new signature would also match, meaning the benign-passthrough path can never
  actually fire for this race. It also would be unsafe even if it could fire: a build that
  fails to compile for a genuine (non-lock) reason produces the same "no test ran, no test
  markers" shape as a lock race, so blindly treating MSB3021/MSB3027 as pass risks masking a
  real regression. Actually re-running the command and judging the retry's own exit code is
  the only approach that both self-heals the race and never silently passes a genuinely
  broken build.
- Rejected: extending `_is_benign_windows_cleanup`'s signature list (structurally a no-op,
  see above); an unconditional pre-command shutdown on every dotnet verify call regardless
  of whether a race actually occurred (adds latency to the overwhelming majority of calls
  that never race).

### verify-gate-retry-shared-not-stage-specific

- Decision: implement the retry inside the shared `_run_verify_gate` helper
  (`_implementer_common.py:753`), gated only on `sys.platform == "win32"`, `"dotnet"` in the
  command string, and the MSB3021/MSB3027 signature appearing in the failed output — not as
  finalize-stage-specific logic in `millpy-implement.py`/`millpy-fix.py`.
- Rationale: `_run_verify_gate` has no notion of which stage (`full`, `finalize`, or a
  module-wide/batch-level call during either) invoked it, and the underlying race — a stale
  build-server node from an earlier `dotnet` invocation in the same worktree — is not unique
  to the finalize replay call site; it was simply where it was first observed. Fixing it once
  in the shared helper covers every current and future caller (including `millpy-fix.py`'s
  identical finalize path) without duplicating retry logic per caller.
- Rejected: a finalize-stage-only pre-check in `millpy-implement.py`, which would leave
  `millpy-fix.py`'s finalize path and any future dotnet-based module-wide/batch verify call
  unprotected.

### verify-gate-retry-one-shot-no-sleep

- Decision: on signature match, retry exactly once, with `dotnet build-server shutdown`
  (best-effort, wrapped in try/except, 30s timeout — matching the existing post-run shutdown
  call's timeout) as the only wait between attempts; no additional fixed sleep or backoff.
- Rationale: both #848 and #860 report the race clearing itself by the time of a bare manual
  re-invocation moments after the failure, with no explicit delay involved; `dotnet
  build-server shutdown` already blocks until the build-server process has actually exited,
  which is the real synchronization point. Adding a sleep/backoff on top adds latency and
  complexity for a race both source issues describe as already gone one invocation later.
- Rejected: a fixed extra sleep after shutdown; exponential backoff over multiple retries —
  both are unsupported by the evidence in the issues and add wall-clock cost to every finalize
  replay of a dotnet-based batch.

### verify-gate-retry-outcome-annotated

- Decision: when the post-retry attempt still fails, return the *retry's own* stuck dict
  (its own reason/signatures from the second subprocess run) with its `reason` prefixed by a
  short marker, e.g. `"[retried once after dotnet build-server shutdown; still failing] "`.
  When the retry passes, return `None` exactly like any other pass — no marker, nothing to
  annotate.
- Rationale: the marker preserves the "this raced and got a second chance before being
  reported as broken" signal for the operator/agent reading the eventual stuck report,
  distinguishing a flaky-then-still-broken batch from one that failed clean on the first try
  — useful triage context at zero cost on the success path.
- Rejected: silently discarding the original failure and returning only the bare retry
  result with no indication a retry happened at all.

### baseline-teardown-defense-in-depth

- Decision: fix the baseline-stage `WinError 145` crash at two layers: (a)
  `_worktree.remove_safe`'s fallback path (`_worktree.py:299-311`) catches an `OSError` from
  `_safe_rmtree.safe_rmtree` with `getattr(exc, "winerror", None) == 145`, runs a
  best-effort `dotnet build-server shutdown`, and retries `safe_rmtree` once before raising
  `WorktreeLockedError`; and (b) `_run_baseline_stage`'s two `remove_safe` call sites
  (`millpy-implement.py:379` and `:426`) are each wrapped in their own try/except so a
  `WorktreeError`/`WorktreeLockedError` that survives (a) is logged to stderr and swallowed,
  never crashing the process.
- Rationale: `remove_safe` is a shared helper (also used by `mill-merge`/`mill-cleanup`
  worktree teardown), so fixing the retry there benefits every caller, not just baseline.
  But `_run_baseline_stage`'s own docstring already documents "Never raises -- every failure
  path prints a JSON line ... and returns 0", and `mill-go-base/SKILL.md` documents the
  orchestrator's expectation of "log the reason and continue to batch 1 anyway" on a baseline
  error — a promise the current code violates by letting a bare `OSError` from the `finally`
  block's teardown call propagate out uncaught. Fixing only the retry (layer a) still leaves
  a crash if the lock genuinely never clears (e.g. a truly stuck process); fixing only the
  wrapper (layer b) leaves every other `remove_safe` caller exposed to the same crash. Both
  layers together give real self-healing (retry) plus a hard guarantee the documented
  contract holds even when self-healing fails, matching the issue's own framing of an
  orphaned `.scratch/verify-baseline-*` dir as acceptable, gitignored clutter — never a
  crash.
- Rejected: retry-only (still crashes if the lock never clears); wrapper-only (never
  self-heals, always leaves an orphaned scratch dir even for the common transient case).

### baseline-retry-match-on-winerror-not-string

- Decision: match the retry-eligible error via `getattr(exc, "winerror", None) == 145`,
  falling back to a string check (`"directory not empty" in str(exc).lower()`) only when the
  exception has no `winerror` attribute (e.g. a test double or non-Windows OSError).
- Rationale: `winerror` is a stable numeric attribute independent of the OS display
  language, unlike the human-readable message text (which the same function's *existing*
  `git`-stderr string matching already relies on for a different signal — that's pre-existing
  debt for a different subsystem, not something this task needs to fix). Retrying on *any*
  `OSError` regardless of code would risk masking an unrelated fallback bug (e.g. a genuine
  permissions/ownership failure) behind a silent retry loop instead of surfacing it as the
  distinct `WorktreeLockedError`/`WorktreeError` it already becomes today.
- Rejected: broad `except OSError: retry` with no code check; string-only matching on the
  (locale-dependent) message text as the primary signal.

### baseline-shutdown-unconditional

- Decision: the baseline-stage retry's `dotnet build-server shutdown` call is unconditional
  and best-effort (try/except, swallow all errors) whenever the Windows WinError-145 retry
  path fires — no attempt to detect whether the transient worktree actually contains a
  dotnet project (`*.csproj`/`*.sln`) first.
- Rationale: unlike `_run_verify_gate`, which has the verify command string to check for
  `"dotnet"`, `remove_safe` only has a worktree path with no equivalent signal already in
  hand; scanning the tree for project files first adds I/O and complexity for a call that is
  already sub-second/no-op when no dotnet build-server process is actually running. This
  matches the codebase's existing philosophy of unconditional, best-effort dotnet cleanup
  calls (see `_run_verify_gate`'s own post-run shutdown and the Handoff done-gate pattern in
  `handoff.md:114-117`).
- Rejected: pre-scanning for `*.csproj`/`*.sln` before deciding whether to shut down.

## Technical context

- `_implementer_common._run_verify_gate` (`plugins/mill/scripts/_implementer_common.py:753`)
  is the single point every verify command (batch-level, module-wide, and finalize-stage
  replay, across `millpy-implement.py` and `millpy-fix.py`) funnels through via
  `_run_verify_gates` (`_implementer_common.py:882`). It already runs the subprocess via
  `_posix_shell_run_args`, checks `_is_benign_windows_cleanup` on a non-zero exit
  (`_implementer_common.py:848`), and unconditionally attempts
  `dotnet build-server shutdown` after the subprocess completes when
  `sys.platform == "win32"` and `"dotnet" in verify_cmd.lower()`
  (`_implementer_common.py:832-844`) — added by #554/#556, with existing tests at
  `test-implementer-common.py:1912` (`Test C1`/`C2`) using the
  `unittest.mock.patch("sys.platform", "win32")` + mocked `subprocess.run` (with
  `side_effect` lists) pattern. The new signature-triggered retry is a second, distinct
  `subprocess.run` call inserted between the existing post-run shutdown and the
  `result.returncode != 0` branch's stuck-dict construction (`_implementer_common.py:845`
  onward) — only entered when the MSB3021/MSB3027 signature is present in `output`.
- The signature check itself should live alongside `_has_windows_cleanup_race_signature`
  (`_implementer_common.py:490`) as its own small helper (e.g.
  `_has_dotnet_lock_race_signature`), matching case-insensitively on `"msb3021"`,
  `"msb3027"`, and/or `"is locked by:"` (the common substring across both MSB codes' observed
  output in #848/#860) — kept distinct from `_has_windows_cleanup_race_signature`
  (`unlinkat`/`access is denied`/`winerror 5`/`winerror 32`) since the two trigger different
  responses (benign-pass vs. retry-then-judge), per Decision `finalize-retry-not-benign-passthrough`.
- `_worktree.remove_safe` (`plugins/mill/scripts/_worktree.py:222`) is the junction-safe
  worktree teardown used by baseline-stage cleanup and elsewhere. Its existing fallback
  (`_worktree.py:299-311`) already special-cases `PermissionError` →
  `WorktreeLockedError`; the new retry sits in that same `except`-adjacent block, catching
  the `OSError` `_safe_rmtree.safe_rmtree` raises (via its own `except OSError: raise` at
  `_safe_rmtree.py:174-176`) before it currently propagates uncaught past `remove_safe`
  entirely.
- `_run_baseline_stage` (`plugins/mill/scripts/millpy-implement.py:216`) calls
  `_worktree.remove_safe(tmp_path, cwd=git_root, junctions_cfg={})` at two sites: the
  shared-checkout-failure early return (`millpy-implement.py:379`) and the `finally` block
  after both module-wide and per-batch computation attempts (`millpy-implement.py:426`). The
  function's own docstring already states "Never raises -- every failure path prints a JSON
  line describing the outcome and returns 0"; `mill-go-base/SKILL.md:546` documents the
  orchestrator's matching expectation ("log the reason and continue to batch 1 anyway" on a
  `{"result": "error", ...}` baseline line). Neither promise currently holds when
  `remove_safe` itself raises from inside the `finally` block, since nothing there catches it.
- `_safe_rmtree.safe_rmtree` (`plugins/mill/scripts/_safe_rmtree.py:95`) is the function that
  actually raises the `WinError 145`, via its `shutil.rmtree(..., onexc=_onexc_chmod_retry)`
  call (`_safe_rmtree.py:169-176`); `_onexc_chmod_retry` only handles the read-only-bit case
  for git pack files and does not address a lock held by a still-live process, so a genuinely
  locked `obj/` file continues to raise past it. This task does not change `safe_rmtree`
  itself — only how its caller (`remove_safe`) reacts to that raised `OSError`.
- Handoff done-gate pattern (`plugins/mill/skills/mill-go-base/handoff.md:114-117`) is the
  one other place in the codebase already doing dotnet-lock hygiene (an unconditional
  post-gate `dotnet build-server shutdown` on win32 when the gate command contains
  `"dotnet"`), referenced by the task brief as the pattern to mirror. It is out of scope for
  this task (not a call site in either observed race) but is useful prior art for the
  shutdown-call shape (`subprocess.run(['dotnet', 'build-server', 'shutdown'],
  capture_output=True, timeout=30)`).

## Testing

- `test-implementer-common.py`: extend the existing `_run_verify_gate` test block (near
  `Test C`, `#556`) with a new `Test D` covering the MSB3021/MSB3027 retry:
  - D1: first `subprocess.run` call returns a failing result whose output contains
    `MSB3021`/`"is locked by:"`; second call is the shutdown; third call (the retry) returns
    a passing result — assert the function returns `None` and that exactly one retry
    `subprocess.run` call was made with the same command/cwd as the first.
  - D2: same setup, but the retry's own `subprocess.run` result also fails — assert the
    returned stuck dict's `reason` is prefixed with the retry marker and reflects the
    *second* attempt's own output, not the first's.
  - D3: a failing dotnet command whose output does NOT contain the MSB3021/MSB3027 signature
    (a genuine, unrelated test failure) — assert no retry `subprocess.run` call is made
    (`mock_run.call_args_list` length matches the no-retry case) and the original failure's
    reason is returned unmodified.
  - D4: non-dotnet command — assert the signature check is never consulted / no retry occurs,
    mirroring the existing "cleanup does NOT fire when the command does not contain dotnet"
    assertion pattern already in Test C.
  Reuse the `unittest.mock.patch("sys.platform", "win32")` + mocked
  `_implementer_common.subprocess.run` (`side_effect` list) convention throughout, exactly as
  Test C already does.
- `test-worktree.py` (or wherever `remove_safe` is currently tested — confirm exact file via
  `Grep` before writing): add a test mocking `_safe_rmtree.safe_rmtree` to raise an
  `OSError` with `winerror=145` on first call and succeed on a second call, with
  `sys.platform` patched to `"win32"` and `subprocess.run` mocked for the shutdown call —
  assert `remove_safe` succeeds (no exception) and that exactly one shutdown call plus one
  retried `safe_rmtree` call occurred. A companion test where the retry also raises
  `winerror=145` should assert `remove_safe` raises `WorktreeLockedError` (not the raw
  `OSError`). A third test with a non-145 `OSError` (e.g. a plain permissions issue with no
  `winerror` attribute matching 145) should assert no retry is attempted and the original
  exception's type/behavior is preserved exactly as today.
- `test-millpy-implement.py` (or equivalent — confirm exact test file location for
  `_run_baseline_stage` via `Grep`): add a regression test that mocks
  `_worktree.remove_safe` to raise `WorktreeLockedError` (simulating a fully-exhausted
  retry) from within `_run_baseline_stage`'s `finally`-block call site, and asserts the
  function still returns `0` and still prints both expected JSON lines (module-wide and
  per-batch) rather than letting the exception propagate — directly exercising the
  "never raises" contract the function's docstring already claims. Cover both call sites
  (the early-return shared-checkout-failure path at `:379` and the `finally` path at `:426`)
  if they end up sharing one wrapper helper, or one test per site if implemented separately.
- No integration-test coverage needed (these are Windows-`sys.platform`-gated code paths;
  the existing unit-test mocking convention is the established way this codebase verifies
  win32-only branches from a non-Windows dev/CI environment — see `#556`'s own tests for
  precedent).

## Q&A log

- **Q:** How should the finalize-stage (and any other dotnet verify call's) MSB3021/MSB3027
  testhost-lock race be fixed — retry-on-signature (re-run the real command), a blanket
  pre-command shutdown, or extending `_is_benign_windows_cleanup`'s auto-pass list? **A:**
  [auto-pick] Retry-on-signature inside `_run_verify_gate`. **Why:** extending the
  benign-cleanup list is a structural no-op (MSB3021 failures always coincide with the
  existing "build failed" blocking marker, so the benign-pass branch can never fire for this
  signature) and would be unsafe even if it could fire (masks genuine build breakage); a
  blanket pre-shutdown adds latency to every dotnet verify call, not just the rare racing
  ones.
- **Q:** How many retries, and with what backoff? **A:** [auto-pick] One retry, gated only by
  `dotnet build-server shutdown` itself (no extra sleep). **Why:** both source issues (#848,
  #860) report the race already cleared by the time of a bare manual re-invocation moments
  later with no explicit delay; the shutdown call already blocks until the server process
  exits, which is the real synchronization point.
- **Q:** Does the retry logic live in the shared `_run_verify_gate` helper or as
  finalize-stage-specific code? **A:** [auto-pick] Shared `_run_verify_gate`. **Why:** the
  helper has no notion of which stage called it, and the race isn't unique to finalize replay
  — it also covers `millpy-fix.py`'s identical finalize path and any dotnet-based
  module-wide/batch-level verify call for free.
- **Q:** Should the baseline-stage `WinError 145` crash be fixed only in `remove_safe`
  (retry), only at the `_run_baseline_stage` call sites (swallow-and-log), or both? **A:**
  [auto-pick] Both. **Why:** `remove_safe` is shared beyond baseline (also used by
  `mill-merge`/`mill-cleanup`), so the retry benefits every caller; but
  `_run_baseline_stage`'s own docstring already promises "never raises," a promise the
  current code breaks whenever the retry itself is eventually exhausted (e.g. a genuinely
  stuck process) — belt-and-suspenders keeps that documented contract true either way.
- **Q:** What should trigger the baseline retry — a specific `winerror` code, or any
  `OSError` from the fallback? **A:** [auto-pick] `getattr(exc, "winerror", None) == 145`,
  string-fallback only when unavailable. **Why:** `winerror` is locale-independent, unlike
  matching the OS message text; retrying on any `OSError` risks masking an unrelated
  fallback bug (e.g. a real permissions failure) behind a silent retry loop.
- **Q:** Should the baseline-stage shutdown call first check whether the transient worktree
  actually contains a dotnet project? **A:** [auto-pick] No — unconditional, best-effort,
  swallow-all-errors. **Why:** `remove_safe` has no existing "is this dotnet" signal
  (unlike `_run_verify_gate`, which has the verify command string); the shutdown call is
  already cheap/no-op when nothing is running, matching the codebase's existing
  unconditional-best-effort-cleanup philosophy elsewhere.
- **Q:** Reuse the existing `sys.platform`/`subprocess.run` mocking convention
  (`test-implementer-common.py`'s `#556` tests) for both new retry paths, runnable from a
  non-Windows dev/CI machine? **A:** [auto-pick] Yes, for both fixes plus a
  `_run_baseline_stage` never-raises regression test. **Why:** this is the codebase's
  established way of verifying win32-only branches without a real Windows box; skipping
  tests on a task whose entire content is Windows-specific lock hygiene would leave the fix
  unverified.
- **Q:** On a still-failing retry, does the function return the retry's own outcome
  silently, or annotate it? **A:** [auto-pick] Annotate — keep the retry's own
  reason/signatures, prefixed with a short "retried once after dotnet build-server shutdown;
  still failing" marker. **Why:** preserves the flaky-vs-broken triage signal for the
  operator at zero cost on the success path (nothing to annotate when the retry passes).
- **Q:** Does the new retry replace the existing unconditional post-run shutdown added by
  #554/#556, or run alongside it? **A:** [auto-pick] Alongside — the existing shutdown keeps
  firing exactly as today; the new signature-triggered retry is additive. **Why:** the
  existing behavior already has passing tests and a documented contract for every other
  caller/scenario; narrowly adding the new retry avoids risking a regression by restructuring
  working code.
