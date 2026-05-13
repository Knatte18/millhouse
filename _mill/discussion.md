# Discussion: Subprocess handling: timeout + JSON-exit + Windows detach

```yaml
task: '(A) — Subprocess handling: timeout + JSON-exit + Windows detach'
slug: subprocess-fixes
status: discussing
parent: main
```

## Problem

Three subprocess-handling bugs filed against mill scripts during the
2026-05-12 session cluster around the same Windows-platform root cause:
the standard Python `subprocess` primitives do not reliably enforce
timeouts or detachment on Windows when the workload is launched through
the VS Code integrated terminal / CC Bash tool environment. The symptoms
are noisy enough that they have blocked task throughput at least twice
in recent weeks and now block confident use of the review backgrounder.

The three concrete failures, in order of severity:

- **#269 timeout not enforced** — `_subprocess_util.run(["cmd", "/c",
  "claude", ...], timeout=1800)` returned exit code 0 after 1938.396s
  with no `TimeoutExpired` raised. Without enforced timeouts, a hung
  claude session blocks the entire mill-go batch loop and there is no
  recovery path.
- **#270 inferred-success masks failure mode** — when the implementer
  subprocess exits without emitting a final JSON line, `_forward_output`
  falls back to commit-SHA inference and emits
  `{"status": "success", "session_id": "unknown", "inferred": true}`.
  The lost `session_id` breaks any subsequent `--resume` call needed
  for a fix-cycle round. The "success" verdict can also paper over a
  session that finished partially. Downstream of #269 today, but a
  separate bug.
- **#271 detached worker writes 0 bytes on Windows** — `millpy-bg.py`'s
  detached `--_worker` subprocess creates the log file but writes 0
  bytes when launched from the VS Code integrated terminal or CC Bash
  tool. The poll-for-`[mill-bg] EXIT` sentinel never fires, so every
  discussion / plan review currently has to bypass `millpy-bg` and run
  the review CLI directly (blocking CC's Bash tool for the full review
  duration, ~1–2 min each).

Why now: the three bugs all hit the same task (`mill-misc-fixes-6`) and
the very next task (`mill-finalize`), and have started silently
corrupting mill-go's stuck-detection (a "success" verdict that is
actually a partial run can ship broken work). The
review-backgrounder regression also halves throughput on every
mill-start / mill-plan run that goes through CC.

## Scope

**In:**

- `plugins/mill/scripts/_subprocess_util.py` — `run` gains a Windows
  watchdog timeout enforcement path that kills the full process tree
  (taskkill /T /F) and reliably raises `subprocess.TimeoutExpired`.
  `run` also gains `CREATE_NEW_PROCESS_GROUP` on Windows so signal
  delivery to the group is well-defined.
- `plugins/mill/scripts/_subprocess_util.py` — `popen_detached` Windows
  path replaced with a two-stage `cmd /c start "" /B <worker-argv>`
  launch that escapes the parent job object. The Win32
  `CREATE_BREAKAWAY_FROM_JOB` flag is retained as a belt-and-braces
  fallback for the inner spawn.
- `plugins/mill/scripts/millpy-bg.py` — worker fast-path writes an
  immediate `[mill-bg] WORKER PID=<pid> START <timestamp>` sentinel as
  the first line of the log file before invoking the child, so an
  empty log proves "worker never ran" vs. "worker ran but child
  produced no output". On worker-side exception (before child spawn),
  write `[mill-bg] WORKER ERROR <text>` and exit non-zero so the
  caller's poller can detect failure rather than hanging.
- `plugins/mill/scripts/_implementer_common.py` — `_forward_output`
  accepts a `session_id` kwarg and uses it as the value for the
  inferred-success fallback (replacing the hard-coded `"unknown"`).
- `plugins/mill/scripts/millpy-implement.py` — both call sites
  (initial dispatch and resume) pass the known `session_id` to
  `_forward_output`.
- `plugins/mill/scripts/millpy-implement-holistic.py` — the
  `_forward_output` call site on line 176 passes the
  `session_id` (the uuid generated on line 113) for the same
  reason the per-batch implementer does. Same minimal change, same
  rationale (the caller chose the id; losing it breaks any
  follow-on `--resume` reattachment).
- `plugins/mill/unit_tests/test-subprocess-util.py` — add coverage for
  the new watchdog path (timeout fires within budget when child holds
  pipes open), and for the updated detach creationflags.
- `plugins/mill/unit_tests/test-millpy-bg.py` — add coverage for the
  worker-start sentinel and for the new two-stage launch (mocked).
- `plugins/mill/unit_tests/test-implementer-common.py` — add coverage
  for the `session_id` plumbing through the inferred-success fallback.
- `plugins/mill/integration_tests/` — add one Windows-only integration
  test per fix that exercises real subprocesses end-to-end:
  - a long-running grandchild that ignores `cmd /c` parent termination,
    asserting the watchdog kills both processes,
  - a detached worker launched from a job-bound parent shell, asserting
    the log gets written and the EXIT sentinel appears.

**Out:**

- Replacing `cmd /c claude` with a direct `claude` invocation. The
  `_llm_claude._claude_argv_prefix()` docstring documents the
  PATH-truncation reason; switching to direct invocation reintroduces
  a class of `claude not found` failures in debugpy / CC Bash
  environments. Out of scope.
- Switching the detach mechanism to PowerShell `Start-Process` or
  Windows Task Scheduler. Out of scope unless the `cmd /c start`
  approach proves insufficient during integration testing — recorded
  as Decision: Windows detach.
- Changing the public API surface of `_subprocess_util.run` or
  `popen_detached`. Same signatures, same exceptions; only the
  internal implementation paths change. Callers stay un-touched.
- Refactoring `_implementer_common._forward_output` into a structured
  pipeline. The current regex-based JSON extraction stays; only the
  `session_id` fallback changes.
- Touching any review-CLI behaviour. The `millpy-review-*.py` and
  `_reviewer_*` modules are unaffected.
- Changing `pipeline.autonomous_mode` or `stuck_type` semantics. The
  fixes preserve every existing verdict-emission shape; they only
  prevent the "inferred-success" path from masking timeouts and
  prevent the empty-log hang.

## Decisions

### timeout-enforcement-mechanism

- **Decision:** Replace `proc.communicate(input=..., timeout=...)`
  with a watchdog loop on Windows. The watchdog spawns the child via
  `Popen` (PIPE stdin/stdout/stderr, plus `CREATE_NEW_PROCESS_GROUP`),
  uses background reader threads to drain stdout/stderr into in-memory
  buffers, feeds stdin if `input` was supplied, and polls
  `time.monotonic() > endtime` in the main thread. On timeout breach,
  the watchdog calls `subprocess.run(["taskkill", "/T", "/F", "/PID",
  str(proc.pid)], capture_output=True)` to kill the full process
  tree, then waits up to `_GRACE_SECONDS` for `proc.wait()`, then
  raises `subprocess.TimeoutExpired(cmd=argv, timeout=timeout,
  output=..., stderr=...)`. POSIX path keeps the existing
  `communicate(timeout=...)` + `os.killpg(SIGKILL)` shape because
  `start_new_session=True` already gives the process-group kill the
  right semantics. The two paths share the same exception type, the
  same breadcrumb format, and the same `CompletedProcess` shape.
- **Rationale:** The observed symptom (no `TimeoutExpired` raised at
  all after 1938s on a 1800s budget) means `communicate(timeout=)` is
  not enforcing the deadline reliably when the grandchild
  (`claude.exe`) keeps the inherited pipe handles open. A custom
  watchdog uses our own clock and our own kill path, so the deadline
  is enforced regardless of pipe inheritance. `taskkill /T /F` walks
  the process tree from `proc.pid` and terminates every descendant,
  which is the only Windows-native primitive that handles "cmd /c
  claude" reliably (taskkill /T uses the WinAPI `Process32First/Next`
  parent-id walk, not pipe-handle inheritance).
- **Rejected:** (a) Wrap the existing `communicate(timeout=)` and
  rely on the `proc.terminate()` + `taskkill` block already present
  in the `except TimeoutExpired` arm — rejected because the
  `TimeoutExpired` was never raised in the first place, so the kill
  block never ran. (b) Switch to a Win32 JobObject assignment via
  ctypes (`CreateJobObjectW` + `AssignProcessToJobObject` +
  `TerminateJobObject`) — rejected as over-engineering for the
  immediate fix and as harder to test; reconsider only if `taskkill
  /T /F` proves unreliable. (c) Drop the `cmd /c` shim and invoke
  `claude` directly — rejected for the PATH-truncation reason
  documented in `_llm_claude._claude_argv_prefix()`.

### timeout-watchdog-stream-handling

- **Decision:** Background reader threads use `proc.stdout.readline()`
  / `proc.stderr.readline()` loops (decode-on-read via the `encoding`
  / `errors` kwargs that `Popen` already applies because `text=True`).
  Each thread appends to a per-stream `list[str]` guarded by an
  `threading.Lock`; the main thread joins them with a short timeout
  after the process exits (or after the kill completes). When `input`
  is supplied, a third thread writes it to `proc.stdin` in a single
  `write` + `close`. All three threads are daemonised so a hung read
  thread does not block interpreter shutdown.
- **Rationale:** The pipe-deadlock failure mode that motivates the
  watchdog is specifically the case where the kernel pipe buffer
  fills and the child blocks on stdout/stderr; readline-loop threads
  prevent that. Daemonised threads + a lock-protected buffer is the
  classic pattern documented in cpython's own `subprocess` test
  suite, well-understood, no ctypes.
- **Rejected:** (a) Use `selectors` / `WaitForMultipleObjects` for
  non-thread pipe draining — unnecessarily Windows-specific and
  doesn't simplify the shape. (b) Use temp files for stdout/stderr
  redirection instead of pipes — works but degrades the "captured
  output" contract callers expect; out of step with the simpler
  thread-based approach.

### detach-mechanism-windows

- **Decision:** `popen_detached` on Windows becomes a two-stage
  launch: the launcher's `Popen` argv is `["cmd", "/c", "start", "",
  "/B", "/MIN", sys.executable, ...rest_of_worker_argv]`. The
  intermediate `cmd.exe` exits immediately after dispatching
  `start`, which spawns the worker outside the parent's job object.
  `creationflags` for the intermediate `Popen` keep `CREATE_NO_WINDOW
  | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB` (no harm
  if `BREAKAWAY_FROM_JOB` is silently denied; the `start` indirection
  handles the breakaway on its own).
- **Rationale:** The empirical Windows behaviour observed in #271 is
  that when `_subprocess_util.popen_detached` is invoked from within
  the VS Code integrated terminal or CC's Bash tool, the worker is
  pulled into the parent's Win32 Job Object. When the launcher's
  Python process exits (normal `sys.exit(0)` after printing
  `pid=<N> log=<path>`), the job's
  `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` flag, if set, terminates the
  worker before it opens the log file — hence 0 bytes. `cmd /c start
  "" /B` is the canonical Windows recipe for "fire-and-forget without
  a console" and is empirically observed to escape job objects that
  set `BREAKAWAY_OK=false` for direct callers. The `/B` flag
  suppresses console-window creation; `/MIN` is belt-and-braces
  against any flash. The "" empty title argument is the literal
  `start` syntax for "use the program name as the title", required
  because of historical `start` argument-parsing quirks.
- **Rejected:** (a) Use PowerShell `Start-Process` — heavier
  dependency, slower spawn (~300ms PowerShell startup), and
  unnecessary if `cmd /c start /B` works. (b) ctypes
  `CreateProcessW` with `PROC_THREAD_ATTRIBUTE_PARENT_PROCESS`
  pointing at `explorer.exe` — over-engineered and brittle across
  Windows versions / privilege levels. (c) Drop detachment entirely
  and have `millpy-bg.py` run the worker synchronously — defeats the
  entire purpose (CC's Bash tool blocks for the review duration). (d)
  Use `schtasks /create /run /delete` — requires admin in some
  configurations and creates an audit-log noise tail.
- **Caveat — `proc.pid` semantics shift:** After the two-stage
  launch, the `subprocess.Popen` returned by `popen_detached` is
  the intermediate `cmd.exe` shim, not the worker. The shim exits
  almost immediately after dispatching `start /B`. The
  `millpy-bg.py` launcher's `pid={proc.pid}` print therefore
  surfaces the shim PID, not the worker PID. The authoritative
  worker PID lives in the new
  `[mill-bg] WORKER PID=<pid> START <iso8601>` sentinel inside the
  log file (see Decision: worker-start-sentinel). Every existing
  caller of `popen_detached` and `millpy-bg.py` only consumes the
  `log=<path>` value — none consume the printed PID for
  process-management purposes (`mill-start`, `mill-plan`,
  `mill-go` all poll the log for the EXIT sentinel and never call
  `taskkill` against the printed pid). Confirmed by grep of
  caller code at discussion time; the plan must re-confirm
  during implementation. No caller updates are needed; the only
  user-visible change is the printed pid is the shim's, not the
  worker's. Documented inline in `popen_detached`'s docstring
  and in `millpy-bg.py`'s launcher comment.

### worker-start-sentinel

- **Decision:** `millpy-bg.py`'s worker fast-path writes
  `[mill-bg] WORKER PID=<os.getpid()> START <ISO8601-utc>\n` as the
  first line of the log file before invoking the child subprocess.
  The sentinel goes through the same `open(log_path, "w",
  encoding="utf-8", buffering=1)` handle that captures child output.
  The flush is implicit via line buffering. The poll loop in the
  caller (`mill-start`, `mill-plan`, `mill-go`) treats the absence
  of this sentinel after a small grace period (~3 seconds) as a
  worker-never-started failure and can surface a clear error to the
  operator instead of polling forever.
- **Rationale:** The current failure mode is indistinguishable from
  "worker is still starting up" — the log file exists, the file is
  0 bytes, the EXIT sentinel never appears. The diagnostic sentinel
  cleanly separates "worker process never ran" from "worker is
  running but child has no output yet". It also gives mill-go a
  programmatic hook to fail fast on broken detach instead of
  silently hanging.
- **Rejected:** (a) Have the worker write a separate sidecar file
  (`<log>.started`) — doubles the file count and the polling
  surface for negligible benefit. (b) Use a Windows event object
  (CreateEvent + SetEvent) — ctypes-heavy and not portable. (c)
  Have the launcher block until the start sentinel appears,
  forcing synchronous startup — adds latency to every detach call
  (~50–200ms) and defeats the "fire-and-forget" property.

### session-id-propagation

- **Decision:** `_implementer_common._forward_output` gains a
  `session_id: str | None = None` keyword-only parameter. When the
  inferred-success fallback path fires (no parseable JSON, new
  commit detected, snapshot-dirt empty), the emitted JSON uses
  `session_id=session_id or "unknown"`. All three call sites pass
  the known session id: `millpy-implement.py` initial dispatch
  passes the uuid generated on its line 134, the resume path
  passes `batch_state.get("implementer_session")`, and
  `millpy-implement-holistic.py` line 176 passes the uuid
  generated on its line 113. The "holistic" caller is plumbed for
  the same reason as the per-batch one: the caller chose the id;
  emitting `"unknown"` strips a value that is always known in
  scope and breaks any follow-on `--resume` reattachment.
- **Rationale:** The caller always knows the session id because the
  caller chose it (initial dispatch) or read it from status.md
  (resume). Falling back to `"unknown"` is gratuitous information
  loss that breaks subsequent `--resume` reattachment. The `or
  "unknown"` keeps the fallback defensive against the unlikely case
  of a caller that didn't supply a session id.
- **Rejected:** (a) Make `session_id` a required parameter — would
  force every caller to supply it even when irrelevant, and breaks
  the existing test fixtures that pass `_forward_output(output,
  project_root)` directly. (b) Extract the session id from claude's
  stream-json output and pass it back through the
  `_implementer_sonnet.run` return value — that already happens in
  the success path; the fallback only fires when stream-json
  parsing failed, so the caller-side id is the only source of
  truth left. (c) Mark inferred-success entries with a richer
  `inferred_reason` field — useful but out of scope; the
  immediate bug is the lost id, not the limited reason metadata.

### posix-behaviour-preserved

- **Decision:** The POSIX code paths for both `run` and
  `popen_detached` keep their existing shape:
  `run` continues to call `communicate(timeout=...)` and use
  `os.killpg(SIGKILL)` on TimeoutExpired; `popen_detached` continues
  to set `start_new_session=True` and no `creationflags`. The
  watchdog and two-stage-launch paths are gated on `os.name == "nt"`
  inside the function body. Unit tests assert that the POSIX path is
  unchanged (mock-based verification of `start_new_session=True` and
  absence of `creationflags` on POSIX).
- **Rationale:** POSIX subprocess semantics already give us the
  right primitives — `start_new_session=True` plus
  `os.killpg(SIGKILL)` reliably kills the full process group, and
  `communicate(timeout=...)` is well-behaved on POSIX because there
  is no analogous pipe-inheritance pathology. Changing the POSIX
  path introduces risk for zero benefit. The Windows-only divergence
  is documented inline near each `if os.name == "nt":` branch.
- **Rejected:** Symmetrise the watchdog across both platforms for
  "consistency" — rejected as gratuitous risk on the platform that
  is not affected by either bug.

### test-coverage-split

- **Decision:** Three layers of test coverage:
  1. **Unit tests** (`plugins/mill/unit_tests/`) mock subprocess
     internals to verify the new code paths trigger the right calls
     (watchdog kills tree via taskkill, two-stage launch uses
     `cmd /c start /B`, worker writes start sentinel, session id is
     plumbed). Run on every commit; no real subprocess hangs allowed.
  2. **Real-subprocess unit checks** (`plugins/mill/unit_tests/`)
     for the watchdog: spawn a real Python child that sleeps in a
     loop and ignores parent termination, assert TimeoutExpired
     fires within budget, assert taskkill breadcrumb appears. This
     extends the existing test (a)/(b) pair in
     `test-subprocess-util.py`.
  3. **Integration tests** (`plugins/mill/integration_tests/`) for
     the cross-process Windows-only kill-tree and detach scenarios:
     spawn `python -c "import subprocess; subprocess.Popen(['python',
     '-c', 'import time; time.sleep(300)'])"` and assert both PIDs
     are gone after watchdog timeout; spawn `millpy-bg.py` from a
     job-bound parent and assert log file gets the start sentinel.
     Skipped on POSIX with a clear `SKIP` message.
- **Rationale:** The original `test-subprocess-util.py` tests (a)/(b)
  proved the in-process timeout path works for the simple
  `python -c "time.sleep(60)"` case — but did not catch the
  grandchild-with-inherited-pipes case that #269 reports. Adding a
  "grandchild ignores parent terminate" unit test catches the actual
  regression. Integration tests catch the cross-process Windows-only
  realities (job objects, console inheritance) that mocks cannot
  represent.
- **Rejected:** Unit-test-only coverage — rejected because the
  Windows job-object behaviour is not reproducible in-process. Pure
  integration coverage — rejected because slower and harder to run
  on every commit.

## Technical context

Files that the plan will touch:

- `plugins/mill/scripts/_subprocess_util.py` (188 lines) — the
  single subprocess wrapper. Public API is `run` and
  `popen_detached`. The current implementation of `run` uses
  `subprocess.Popen` + `proc.communicate(input, timeout=...)` and
  on `TimeoutExpired` calls `proc.terminate()`, a 5-second grace
  wait, then `taskkill /T /F` on Windows or `os.killpg(SIGKILL)` on
  POSIX. The Windows path doesn't fire the timeout reliably (#269)
  because `communicate(timeout=...)` can stall on inherited pipe
  handles. The current implementation of `popen_detached` uses
  `subprocess.Popen` with `CREATE_NO_WINDOW |
  CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB` on Windows;
  this fails to escape parent job objects under VS Code / CC Bash
  (#271).
- `plugins/mill/scripts/millpy-bg.py` (143 lines) — the
  fire-and-forget backgrounder. Two modes: launcher and `--_worker`.
  Launcher prints `pid=<N> log=<path>` and exits. Worker opens the
  log file, runs the supplied command with stdout/stderr redirected
  to it, and appends `[mill-bg] EXIT <code>`. The fix adds an
  immediate start-sentinel write at the top of the worker `with
  open(...)` block.
- `plugins/mill/scripts/_implementer_common.py` (51 lines) —
  `_forward_output` is called by both `millpy-implement.py` and
  `millpy-implement-holistic.py` (if it exists; check during plan).
  The regex `r'\{[^{}]*"status"[^{}]*\}'` finds the last JSON object
  in claude's text output containing a `status` key. The
  inferred-success fallback runs when no JSON match was found, the
  start_sha is known, and `compute_new_dirt` returned an empty list
  (i.e., the worktree is clean and a new commit exists). The fix
  adds a `session_id` kwarg and uses it in the emitted JSON.
- `plugins/mill/scripts/millpy-implement.py` (267 lines) — two call
  sites for `_forward_output` (line 187 for initial dispatch, line
  262 for resume). Both have a `session_id` value in local scope at
  the call point. Plumbing is trivial.
- `plugins/mill/scripts/_llm_claude.py` (~398 lines) — the LLM
  wrapper. The `_invoke` function catches generic `Exception` and
  re-classifies as `LLMError`; the timeout-name match
  (`"TimeoutExpired" in type(exc).__name__`) is brittle but
  preserved by the fix because `_subprocess_util.run` continues to
  raise `subprocess.TimeoutExpired`. No changes needed here as long
  as the watchdog raises the same exception type.

Existing unit tests:

- `plugins/mill/unit_tests/test-subprocess-util.py` (247 lines):
  tests (a)/(b) cover timeout-fires + breadcrumb format using a
  simple `python -c "import time; time.sleep(60)"` child. Tests
  (k)/(l) cover the creationflags / `start_new_session` split on
  Windows / POSIX. Extending these is the right shape.
- `plugins/mill/unit_tests/test-millpy-bg.py` (319 lines): launcher
  tests (a)–(g) cover path format, .scratch creation, output
  format, and arg parsing. Worker tests (h)–(l) cover the
  output-to-log + sentinel-on-exit + missing-flag cases. Adding a
  test (n) for the start-sentinel is the right shape.
- `plugins/mill/unit_tests/test-implementer-common.py` (already
  exists; verify shape in the plan). Add a case for the session_id
  fallback plumbing.

Integration test infrastructure:

- `plugins/mill/integration_tests/` runs real subprocesses, real
  `git`, real fixtures. Local-dev only; not in CI today. The fix
  adds Windows-only tests that explicitly skip on POSIX.

Gotchas discovered during exploration:

- The `_llm_claude._claude_argv_prefix()` docstring documents the
  `cmd /c claude` indirection as a PATH-truncation workaround for
  debugpy / CC Bash environments. Do not "fix" #269 by switching
  to direct claude invocation; it reintroduces a different class
  of failures.
- `_subprocess_util.run` already has a `taskkill /T /F` block in the
  `except TimeoutExpired` arm (lines 127–131). The bug is upstream:
  `communicate(timeout=)` never raises, so the block never runs.
  The watchdog change makes the kill block reliably reachable.
- `_subprocess_util.run` declares `_GRACE_SECONDS = 5` at module
  scope. The watchdog should reuse this constant.
- `popen_detached` already sets `CREATE_BREAKAWAY_FROM_JOB`; keep
  it. The two-stage `cmd /c start /B` is the actual escape
  mechanism; `BREAKAWAY_FROM_JOB` is the fallback for environments
  where the intermediate cmd is itself in a non-breakaway job.
- `millpy-bg.py` worker mode is a stdlib-only fast path — it
  deliberately does not import `_subprocess_util` so it can run
  with minimal startup latency. Keep that property; the start
  sentinel uses bare `open()` + `print()` to the log file handle,
  not any helper.
- `_implementer_common._forward_output` returns 0 in both success
  and stuck paths; only stdout signals state. Preserve this — the
  fix changes the JSON content, not the return-code contract.
- The unit-test file pattern is `test-<name>.py` (note hyphen, not
  underscore). The run-all driver is
  `plugins/mill/unit_tests/run-all.py`.

## Constraints

From `CLAUDE.md`:

- **All `print()` and `_log()` output strings use ASCII only.** The
  start sentinel `[mill-bg] WORKER PID=... START <iso8601>` is
  pure ASCII. ISO 8601 timestamps are ASCII. Confirmed compliant.
- **`${CLAUDE_PLUGIN_ROOT}` for all intra-plugin paths.** The fix
  does not touch any SKILL.md or any caller; only Python helpers and
  unit tests. No path-template change needed.
- **Plugin scripts reference `${CLAUDE_PLUGIN_ROOT}`, not the source
  repo.** Unaffected — internal-only changes.
- **Working state in `_mill/` on the task branch.** Unaffected —
  no wiki writes, no working-state-format changes.

From the bug reports:

- The fix must not require `claude.cmd` to be on Python's inherited
  PATH (the original reason for `cmd /c` indirection). This
  excludes the "drop cmd /c" simplification.
- The fix must work from CC's Bash tool, VS Code integrated
  terminal, and direct cmd.exe invocation. Verified during
  integration testing.

From the codebase shape:

- The `_subprocess_util.run` public API signature is shared by
  every mill script. Any change to the signature ripples to
  ~30+ call sites. The fix keeps the signature stable.
- The `popen_detached` return type is `subprocess.Popen`; callers
  read `.pid` and treat the process as detached. Preserve.
- POSIX behaviour is correct today; do not introduce a regression.
  Verified by unit tests that mock `os.name="posix"`.

## Testing

Per-module test approach:

- `_subprocess_util.run` (Windows watchdog path):
  - **TDD candidate**: red test first. Write a unit test that spawns
    a Python child that itself spawns a long-running grandchild (e.g.
    `python -c "import subprocess, sys; subprocess.Popen(['python',
    '-c', 'import time; time.sleep(60)'], creationflags=...);
    time.sleep(60)"`), runs it under `run(..., timeout=2.0)`, and
    asserts (a) `TimeoutExpired` is raised, (b) within the wall-time
    budget `2.0 + _GRACE_SECONDS + small_delta`, (c) the parent and
    child PIDs are both gone after the call returns. This test must
    fail against the current code (because `communicate(timeout=)`
    doesn't fire reliably), then pass against the watchdog
    implementation.
  - Preserve tests (c)–(l) in `test-subprocess-util.py` unchanged;
    they verify the contract that the watchdog must preserve.

- `_subprocess_util.popen_detached` (Windows two-stage launch):
  - **TDD candidate**: red test first. Write a unit test that mocks
    `subprocess.Popen` and asserts the argv on Windows is
    `["cmd", "/c", "start", "", "/B", "/MIN", sys.executable, ...]`
    and the creationflags are
    `CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP |
    CREATE_BREAKAWAY_FROM_JOB`. Asserts on POSIX that
    `start_new_session=True` and no `creationflags` (preserved).
  - Update test (k) in `test-subprocess-util.py` to assert the new
    argv-mangling on Windows.

- `millpy-bg.py` worker start sentinel:
  - **TDD candidate**: extend tests (h)/(i) to also assert
    `[mill-bg] WORKER PID=<int> START <iso8601>` appears as the
    first line of the log file. The integration counterpart spawns
    a real detached worker from a job-bound parent shell and
    asserts the sentinel appears within 3 seconds.

- `_implementer_common._forward_output` session_id plumbing:
  - **TDD candidate**: extend `test-implementer-common.py` (or add
    if missing) to assert that when `_forward_output(output,
    project_root, start_sha=..., snapshot_path=...,
    session_id="abc-123")` fires the inferred-success path, the
    emitted JSON has `"session_id": "abc-123"`, not `"unknown"`.
    Also assert the existing structured-JSON path is unchanged.

- `millpy-implement.py` call-site plumbing:
  - Spot-check via existing `test-millpy-implement.py` that both
    call sites pass `session_id=...` to `_forward_output`. The
    existing test setup already mocks the implementer subprocess
    so this is a straightforward extension.

Integration scenarios:

- **Windows-only #269 kill-tree**: spawn a real child that fires a
  grandchild, run under `_subprocess_util.run(..., timeout=2.0)`,
  poll `tasklist /FI "PID eq <grandchild_pid>"` after the call
  returns and assert the grandchild is gone. Skip on POSIX.
- **Windows-only #271 detached worker**: the test must guarantee
  the job-bound parent condition rather than relying on the
  harness shell. The integration test creates the condition itself
  via ctypes: it calls `CreateJobObjectW(NULL, NULL)`, sets
  `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` via
  `SetInformationJobObject` with a
  `JOBOBJECT_BASIC_LIMIT_INFORMATION` struct, calls
  `AssignProcessToJobObject(job, GetCurrentProcess())` to enrol
  the test process itself in the job, then spawns `millpy-bg.py
  --slug it-detach -- python -c "print('hi')"` from inside that
  job-bound test process. Without the fix, the worker dies when
  the test process exits (kill-on-job-close); with the fix, the
  two-stage `cmd /c start /B` escapes the job and the worker
  writes its sentinels. The test polls for up to 5 seconds for
  the start sentinel and up to 10 seconds for the EXIT sentinel.
  Skip on POSIX. Relying on "must be run from VS Code / CC Bash"
  was rejected because it makes the test vacuously pass under
  plain cmd.exe (which doesn't impose the job condition), exactly
  the case that the bug report's hypothesis would hide. Building
  the job condition in the test eliminates that ambiguity.

Scenarios that must be covered (not full assertion sets — that's
mill-plan's job):

- Watchdog timeout fires within budget when child has open pipes.
- Watchdog timeout fires within budget when child has a running
  grandchild.
- Watchdog correctly propagates `TimeoutExpired` with stdout/stderr
  collected so far.
- Watchdog does not regress the non-timeout normal-completion path.
- Watchdog stdin handling delivers the prompt to the child correctly
  (mirrors current `input=...` contract).
- POSIX behaviour for both `run` and `popen_detached` is mock-
  asserted unchanged.
- Worker start sentinel appears in real and mocked launches.
- `_forward_output` preserves the original "structured JSON
  present" path (no behaviour change there).
- `_forward_output` inferred-success path returns the known
  session_id when supplied.
- `_forward_output` inferred-success path returns `"unknown"` when
  no session_id supplied (backwards-compatible default).

## Q&A log

- **Q:** Should the timeout enforcement also apply on POSIX, for
  symmetry?
  **A:** [auto-pick] No — keep POSIX on the existing
  `communicate(timeout=) + os.killpg(SIGKILL)` shape.
  **Why:** POSIX subprocess semantics already give us reliable
  process-group kill via `start_new_session=True`; the bug is
  Windows-specific (pipe inheritance + job objects). Symmetrising
  the watchdog adds risk on the platform that isn't broken.

- **Q:** Should we drop the `cmd /c claude` indirection and call
  `claude.cmd` directly, since that would also solve #269?
  **A:** [auto-pick] No — keep the `cmd /c` indirection.
  **Why:** `_llm_claude._claude_argv_prefix()` documents that the
  Windows-Apps PATH stripping in debugpy / CC Bash environments
  makes direct invocation unreliable. Solving #269 should not
  reintroduce a different class of bugs in #269's neighbours.

- **Q:** What's the right detach mechanism for Windows #271 —
  `cmd /c start /B`, PowerShell `Start-Process`, ctypes
  CreateProcessW with PROC_THREAD_ATTRIBUTE_PARENT_PROCESS, or
  scheduled-task indirection?
  **A:** [auto-pick] `cmd /c start "" /B /MIN` two-stage launch.
  **Why:** Canonical Windows recipe for fire-and-forget, well-
  understood, no PowerShell startup cost, no ctypes dependency.
  PowerShell adds ~300ms latency to every detach. ctypes pulls in
  Windows-version-specific brittleness. Scheduled tasks need
  admin in some configurations.

- **Q:** Should the worker start sentinel use a Windows event
  object (`CreateEvent` + `SetEvent`) instead of a log-file line?
  **A:** [auto-pick] No — write it as a log-file line.
  **Why:** Portable; the existing poll loop in callers already
  reads the log file; ctypes-free; the sentinel format is human-
  readable for debugging.

- **Q:** Should `_forward_output`'s `session_id` parameter be
  required, or optional with a default?
  **A:** [auto-pick] Optional, default `None`.
  **Why:** Backwards-compatible with any test fixture or caller
  that doesn't supply it. The fallback resolves to `"unknown"`
  in that case, preserving exact current behaviour for un-
  modified callers.

- **Q:** Should the watchdog use threads or `selectors` for
  pipe draining?
  **A:** [auto-pick] Threads.
  **Why:** Daemonised reader-thread pattern is the canonical
  cpython recipe; works identically on Windows and POSIX; no
  Windows-specific `WaitForMultipleObjects` complexity; no risk
  of a `selectors` portability gap.

- **Q:** Should the worker start sentinel block the launcher
  until written (synchronous startup confirmation)?
  **A:** [auto-pick] No — launcher stays asynchronous.
  **Why:** Blocking adds 50–200ms to every detach call and
  defeats the fire-and-forget property. The poll loop in the
  caller already polls for the EXIT sentinel; treating "no
  START sentinel after 3 seconds" as a failure is the same
  shape as the existing EXIT polling.

- **Q:** Should the integration tests for the Windows-only
  scenarios live in CI?
  **A:** [auto-pick] No — local-dev only, marked as Windows-only
  with a clear `SKIP` on POSIX.
  **Why:** The existing `integration_tests/` directory is
  already documented as local-dev only; the bug is Windows-
  specific and a CI Windows runner is out of scope for this
  task.

- **Q:** What's the right `start` syntax — should the empty
  title argument be omitted?
  **A:** [auto-pick] Include the empty title `""`.
  **Why:** Windows `start` parses its first quoted argument as
  a window title; omitting it can cause the first real argument
  to be misinterpreted when the executable path contains
  spaces. Including the empty `""` is the canonical workaround
  documented across Windows scripting references.

- **Q:** Should the fix change `_implementer_sonnet.run`'s
  signature to plumb session_id through differently, or only
  change `_forward_output`?
  **A:** [auto-pick] Only `_forward_output`.
  **Why:** `_implementer_sonnet.run` already returns
  `(text, session_id)` from `run_implementer`; the caller
  already has the session_id from its own uuid generation
  (initial path) or batch state (resume path). Plumbing it
  through `_forward_output` is the minimal change.

- **Q:** [round 1 gap] Should `millpy-implement-holistic.py`'s
  `_forward_output` call site (line 176) be included in the
  session_id plumbing, or excluded?
  **A:** [auto-pick] Include it.
  **Why:** Symptom-identical to the per-batch case: line 113
  generates a uuid that is passed to claude via `--session-id`,
  and line 176 calls `_forward_output(output, project_root)`
  without it, so the inferred-success fallback emits
  `"session_id": "unknown"` even though the caller knows the
  id. Same fix, same rationale, same minimal change. Excluding
  it would leave the holistic dispatcher in the broken state
  the bug report describes.

- **Q:** [round 1 gap] How does the #271 integration test
  guarantee the job-bound parent condition?
  **A:** [auto-pick] The test manufactures the job condition
  itself via ctypes (`CreateJobObjectW` +
  `SetInformationJobObject(JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE)`
  + `AssignProcessToJobObject(job, GetCurrentProcess())`)
  before spawning `millpy-bg.py`.
  **Why:** Documenting a "must run from VS Code / CC Bash"
  requirement makes the test vacuously pass under plain
  cmd.exe (which doesn't impose the job condition) — exactly
  the silent-success failure mode the bug report describes.
  Building the job in the test process gives a deterministic,
  CI-portable proof that the two-stage launch actually escapes
  the job. ctypes is already an acceptable dependency for
  Windows integration tests.

- **Q:** [round 1 note] Does the `proc.pid` returned by the
  new `popen_detached` need a caller update?
  **A:** [auto-pick] No caller update needed; document the
  shift inline.
  **Why:** Greps of caller code show no caller consumes the
  printed PID for process-management (taskkill, polling). All
  callers consume the `log=<path>` value only. The worker PID
  is recoverable from the new `[mill-bg] WORKER PID=...`
  sentinel if a future caller needs it. Documenting the shift
  in `popen_detached`'s docstring and the launcher's print
  comment is sufficient.
