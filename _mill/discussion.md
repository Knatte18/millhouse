# Discussion: Instrument and bound the verify runner

```yaml
task: Instrument and bound the verify runner
slug: verify-runner-instrumentation
status: discussing
parent_branch: main
```

## Problem

A single verify command took 87 minutes in NORCE-DrillingAndWells/Models on 2026-10-13.
Finding out why took two days and three sessions,
because the runner logged only a bare `[mill-bg] HEARTBEAT` every 30 seconds and its log died with the worktree.
The root cause was in that repo:
a `[SetUpFixture]` shells out to `dotnet run` on a cold worktree and reads stdout to EOF,
while MSBuild nodes started with `/nodeReuse:true` inherit the pipe and outlive the child,
blocking the read for their ~15-minute idle timeout.
Only a worktree's first verify run is slow.

Mill has the same blind spot and the same exposure.
Every verify site captures output with `subprocess.run(..., capture_output=True)`,
which waits for pipe EOF rather than child exit,
so a verify command that leaves MSBuild nodes behind hangs mill exactly as it hung the NORCE harness.
No verify site records which command is running, for how long, whether it was the worktree's first run,
and none has a timeout.

Why now: the companion task `drop-verify-baseline-preflight` (commit `e408e454`) removed the eager pre-flight and its `pipeline.baseline_verify_timeout_minutes` knob.
The same runner still executes the batch gates, the finalize replays, the merge-in recompute and the done gate.

## Scope

**In:**

- A shared verify runner module used by every surviving verify site.
- START / HEARTBEAT / END lines per verify command, naming the command, cwd, elapsed/wall time and exit code.
- A first-run-in-this-worktree flag on every run.
- A default per-command timeout, configurable per repo, that fails the gate loudly.
- Output captured to a file instead of a pipe, plus `MSBUILDDISABLENODEREUSE=1` and `DOTNET_CLI_USE_MSBUILD_SERVER=0` in the verify environment.
- A durable per-run summary row in `status.md` that survives worktree teardown via the pushed task branch and the `archive/<slug>` tag.
- Wall time, exit code, first-run and timed-out fields in the JSON results the orchestrator reads.
- `millpy-bg.py`'s heartbeat naming its inner command and elapsed time.
- Verify sites: `_implementer_common._run_verify_gate` / `_run_verify_gates` (all callers, including the finalize replays and the inferred-success check), `_done_gate.run_gate` and `_done_gate.run_preflight`, `millpy-merge-in-subagent.py`'s verify-fix runs, and the `mill-merge-in` SKILL's step-4 verify replay.

**Out:**

- The NORCE fixture bootstrap bug itself — fixed in that repo.
- The Bash-tool 10-minute cap on agent-mode `--stage finalize` calls (`mill-go-base/SKILL.md`, "Give any `--stage finalize` call an extended Bash-tool timeout").
  It stays an outer bound on the whole finalize call; this task does not restructure how finalize is invoked.
- Review CLIs, LLM-provider timeouts (`bulk_timeout`, `holistic_timeout`, ...) and `implementer_timeout` — they run LLMs, not verify commands.
- The `dotnet build-server shutdown` post-steps (`_implementer_common._run_verify_gate` and `_done_gate.run_gate`, both `subprocess.run(["dotnet", "build-server", "shutdown"], capture_output=True, timeout=30)`) — left exactly as they are.
  They are cleanup, not verify commands, so they get no label, no verify timeout, no first-run marker and no `## Verify log` row.
  (The dotnet lock-race *retry* is a verify command and is routed through the runner — see Decisions.)
- The three pre-existing `test-bg-liveness.py` failures and the other files already red on `main` (see Constraints).
- Any new `stuck_type`.
  A timeout is reported as `stuck_type: verify` (see Decisions).
- Any baseline / pre-flight-capture logic; that mechanism is gone.

## Decisions

### Shared runner module

- Decision: add `plugins/mill/scripts/_verify_run.py` exposing one entry point, `run_verify(cmd, *, cwd, label, git_root, timeout_s, shell_mode, env=None, status_path=None) -> VerifyRun`.
  `VerifyRun` is a small dataclass: `label`, `cmd`, `cwd`, `exit_code` (int, or `None` on timeout), `wall_s` (float), `first_run` (bool), `timed_out` (bool), `output` (str, combined stdout+stderr read from the output file), `output_path` (Path).
  It never raises for command failure or timeout; it raises only for programmer errors (e.g. missing `cwd`).
  A launch failure (missing binary, bad cwd) is returned as a `VerifyRun` with `exit_code=None`, `timed_out=False` and the exception text as `output`, so every caller keeps its existing never-raise contract.
- Rationale: there are five call sites with five hand-rolled `subprocess.run` blocks; instrumentation and the pipe fix belong in one place or they drift.
- Rejected: patching each `subprocess.run` site in place (five copies of the heartbeat/timeout/marker logic); extending `_subprocess_util.run` itself (it serves git and every other subprocess in mill, which must not get verify semantics).

### Shell mode preserves each site's current semantics

- Decision: `shell_mode` is `"posix"` or `"native"`.
  `"posix"` reproduces `_implementer_common._posix_shell_run_args`: `[bash, "-c", cmd]` when `bash` is on PATH on Windows, otherwise `[os.environ.get("SHELL") or "/bin/sh", "-c", cmd]` on POSIX and `["cmd", "/c", cmd]` on Windows without bash.
  `"native"` reproduces today's `shell=True` (`cmd /c` on Windows, `/bin/sh -c` on POSIX).
  Batch/module-wide gates and the merge-in paths use `"posix"`; `_done_gate` keeps `"native"`.
  `_posix_shell_run_args` stays the single source of the bash lookup; the runner calls it or shares its helper.
- Rationale: `done_gate` commands are written today against `shell=True`; switching them to bash routing silently changes their meaning on Windows.
- Rejected: one shell mode for all sites.

### Pipe trap: file redirection and node-reuse env vars, both

- Decision: the runner redirects the child's stdout and stderr (stderr merged into stdout) to an output file and reads it only after the child exits.
  It also sets `MSBUILDDISABLENODEREUSE=1` and `DOTNET_CLI_USE_MSBUILD_SERVER=0` in the child environment, on every platform and for every command (not only commands containing `dotnet`).
  The env is built from the caller-supplied `env` (or `os.environ`) with these two keys overriding.
- Rationale: file redirection removes mill's own EOF wait — an orphaned MSBuild node holding the file handle no longer blocks anything.
  The env vars stop the same trap firing *inside* the verify command, which was the NORCE case: their harness inherits the env from mill's verify subprocess.
  They are inert for non-dotnet commands, so gating on `"dotnet" in cmd` buys nothing and misses wrappers like `make test`.
  The reporting repo confirmed both remedies, taking a fixtureless verify from ~18 minutes to 163 seconds.
- Rejected: env vars alone (mill still hangs on any other tool that leaks inherited handles); file redirection alone (the inner harness still hangs and the timeout becomes the only defence, which converts a silent hang into a failed gate but is still wrong).
- Behaviour change accepted: stdout and stderr become interleaved in one stream instead of concatenated `stdout + stderr`.
  `_is_benign_windows_cleanup`, `_has_dotnet_lock_race_signature` and `_extract_failure_signatures` are substring/line scans and keep working on the combined text.

### Timeout: per command, configurable, loud

- Decision: new config key `pipeline.verify_timeout_minutes`, default `20`, added to both `plugins/mill/templates/mill-config.yaml` and the hub `mill-config.yaml` (they must stay in sync), next to the other `pipeline:` keys with a trailing comment.
  It bounds each single command invocation — the batch gate, the module-wide gate, the dotnet lock-race retry and each merge-in replay each get their own full budget.
  The value must be a positive number; a missing key uses the default, and a non-positive or non-numeric value raises a clear `ValueError` naming the key when the runner's caller resolves it (no silent fallback).
  A shared helper (e.g. `_verify_run.timeout_seconds(cfg) -> float`) resolves it so the sites don't each parse it.
- On timeout the runner kills the whole process tree — `taskkill /T /F /PID` on Windows, `os.killpg` on POSIX after starting the child with `start_new_session=True` — exactly the mechanics `_subprocess_util.run` and `_subprocess_util._run_windows_watchdog` already implement; reuse them rather than reimplement (`_subprocess_util.run` with `stdout=<file>`, `stderr=subprocess.STDOUT`, `timeout=`).
- A timed-out run is a failed gate.
  `_run_verify_gate` returns `{"status": "stuck", "stuck_type": "verify", "reason": "[verify timed out after <N>s: <label>] <truncated output>", "timed_out": true}`.
  `_done_gate` returns `{"result": "blocked", "reason": "[verify timed out after <N>s] ..."}`.
  The merge-in paths report it as a failed verify through their existing stuck shape with the same reason prefix.
  A timed-out run never triggers the dotnet lock-race retry and is never classified benign by `_is_benign_windows_cleanup`.
- Rationale: real suites in every repo in play run 2–4 minutes and the reporting repo's worst cold run is now 163 seconds; 20 minutes leaves 5x headroom for a legitimately slow suite while bounding a hang.
  Per command rather than per gate keeps the bound independent of how many commands a gate chains.
  Reusing `stuck_type: verify` keeps mill-go's existing self-resolve-then-escalate routing; the reason prefix and `timed_out` field tell the self-resolver it is not a test failure.
- Rejected: a 30-minute floor (sized against the bug, not the suites); a new `stuck_type: verify_timeout` (touches orchestrator routing in mill-go-base for no behavioural gain); `null` to disable (a disabled bound is the silent degradation the brief rules out — a repo with a slow suite raises the number instead).

### Observability lines: START / HEARTBEAT / END

- Decision: the runner writes these ASCII-only lines:
  - `[verify] START <label> first_run=<true|false> timeout=<N>s cwd=<cwd> cmd=<cmd>`
  - `[verify] HEARTBEAT <label> elapsed=<N>s cmd=<cmd>` every 30 seconds while the child runs (interval is a module constant, overridable in tests)
  - `[verify] END <label> exit=<rc|timeout|launch-error> wall=<N.N>s output=<output_path>`
  
  Each line carries a UTC ISO timestamp prefix (same format as `millpy-bg.py`'s lines).
  Every line goes to two places: the calling process's stderr (so under `millpy-bg` it lands in the bg log, and under agent-mode Bash it lands in the tool output), and an append-only live log at `<git_root>/.scratch/verify/verify.log`, flushed per line, so an operator can tail a run that is still in progress.
  The heartbeat runs on a daemon thread stopped in a `finally`, mirroring `millpy-bg.py`'s `_heartbeat`.
- Command output goes to `<git_root>/.scratch/verify/<YYYYMMDD-HHMMSS>-<sanitized-label>.out` (label sanitized via `_paths.sanitize_filename_component`).
  The file is kept after the run; its path appears in the END line and is appended to any failure reason.
- Labels: the batch name for a batch gate, `<batch>:module-wide` for the module-wide gate, `<batch>:retry` for the lock-race retry, `done-gate` / `done-gate-preflight` for `_done_gate`, and `merge-in:<batch>` for merge-in replays.
  The plan threads the label from each caller; where a caller has no batch name in scope, it passes a fixed descriptive label rather than inventing one.
- Rationale: "slow" vs "stuck" must be distinguishable while the run is in progress.
  Stderr alone is invisible in agent mode until the Bash call returns; the live log closes that gap.
- Rejected: writing markers into the `.out` file (mixes them with the command's output and complicates the failure-reason truncation).

### First-run flag: per worktree, marker in `.scratch`

- Decision: `first_run` is true when `<git_root>/.scratch/verify/first-run.done` does not exist when the run starts.
  The runner creates the marker after the run finishes, whatever the outcome (pass, fail, timeout).
  A hard kill before the marker write leaves the next run flagged first again, which is accurate: the cold-path work may not have completed.
  The flag is per worktree, not per command — matching the brief ("first verify in the worktree").
- Rationale: `.scratch/` lives and dies with the worktree, which is exactly the semantics wanted; a fresh `mill-resume` worktree on another machine is correctly cold.
  Deriving it from the `status.md` verify log would be wrong there, because `status.md` travels with the branch.
  The flag does not mean "first run after a build": deleting `bin/`/`obj/` and rebuilding measured 2 m 19 s vs 2 m 16 s warm.
- Rejected: per-command-string flag (a batch's `dotnet test --filter X` and the module-wide `dotnet test` share one bootstrap; per-command would mislabel the second as cold); flag derived from status.md (wrong across machines).

### Durable record: `## Verify log` in status.md

- Decision: add `_status.append_verify_log(status_path, *, timestamp, label, exit, wall_s, first_run, cmd)` following the existing `append_recovery_log` / `append_inferred_success_log` pattern (a `## Verify log` heading with a fenced `text` block, created on first append).
  One row per command: `<ts>  <label>  exit=<rc|timeout|launch-error>  wall=<N.N>s  first_run=<bool>  cmd=<cmd>`.
  `run_verify` appends the row itself when `status_path` is given; callers resolve `status_path` the way they already do (`_paths.status_path` / `require_status_path`) and pass `None` only where no status file exists, in which case the row is skipped with a one-line stderr note.
  A failure to write the row is caught and reported on stderr; it never changes the verify verdict.
- Commit coverage: the row is only durable once committed.
  The plan must audit each site and make sure a commit that stages `status_path` follows before the worktree can be torn down:
  - batch gates / finalize replays — mill-go's existing per-batch status commits;
  - done gate — Handoff's existing `done` phase commit;
  - `run_preflight` (mill-go Prepare and mill-quick) — the next existing status commit;
  - merge-in replays and `millpy-merge-in-subagent.py` — `mill-merge-in` step 5 currently stages only `_mill/briefs/`; extend it to also stage `status_path`, so rows written during merge-in are committed before `mill-merge`'s cleanup commit removes `_mill/`.
  After that commit, the rows survive teardown through the pushed task branch and the `archive/<slug>` tag that `mill-merge` creates.
- Dirty-tree hazard: writing `status.md` mid-finalize must not trip any dirty-tree check.
  `_in_scope_dirty_stuck` already excludes the task dir.
  The inferred-success check in `_implementer_common` (`git status --porcelain --untracked-files=no` before its `_run_verify_gates` call) is not scoped — the verify-log write happens after that check, but the plan must confirm no other unscoped porcelain check runs after a verify-log write on any path (`_forward_output`'s success/dirty/completeness branches, fixer finalize, merge-in), and exclude `status_path`/the task dir from any that does.
- Rationale: matches the repo's rule that working state lives in `_mill/` on the task branch, reuses an established status.md log-section pattern, and is visible on any machine that fetches the branch or tag.
- Rejected: a container-level log directory (in prefix-form layouts the container is an arbitrary parent directory like `C:\Code`, and the log would be local-only); the hub worktree's `.scratch/` (a child worktree writing into the parent worktree breaks the worktree-isolation rule); a separate `_mill/verify-log.md` (every commit pathspec would need to learn a new file, while `status_path` is already staged everywhere).

### JSON results carry the timings

- Decision: every JSON result produced by a site that ran verify carries `verify_runs: [{"label", "cmd", "exit_code", "wall_s", "first_run", "timed_out"}]`, in execution order, including passing runs:
  - every envelope `_implementer_common._forward_output` / the finalize stages print after running a verify gate (success, stuck, inferred-success);
  - `_done_gate.run_gate` / `run_preflight` result dicts (the `"skipped"` result has none);
  - the merge-in subagent's envelope;
  - the new CLI below.
  `_run_verify_gate`'s `dict | None` return contract stays; the plan picks the mechanism for collecting runs (e.g. an optional `runs: list` accumulator parameter threaded through `_run_verify_gates`) and adds the field at a single emit chokepoint rather than editing each `print(json.dumps(...))` separately.
- Rationale: the orchestrator and the operator see wall time without opening a log, as the brief requires.
- Rejected: wall time only in the log.

### Merge-in SKILL replay goes through a CLI

- Decision: add `plugins/mill/scripts/millpy-verify-run.py --label <label> --cmd <cmd> --cwd <path>` that resolves `git_root`, config, timeout and `status_path`, calls `run_verify` with `shell_mode="posix"`, prints one JSON line (`label`, `cmd`, `exit_code`, `wall_s`, `first_run`, `timed_out`, `output_path`, `verify_runs`, and a `reason` using the same truncation as `_run_verify_gate` on failure), and exits 0 on pass, 1 on fail or timeout.
  `mill-merge-in/SKILL.md` step 4's "Run the command from that resolved cwd" invokes this CLI (cache-form `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-verify-run.py" ...`) instead of running the command bare.
  The SKILL tells the orchestrator to give that Bash call a 600000 ms timeout, matching the existing finalize guidance.
- Rationale: that replay is executed by the orchestrator's own Bash tool today, so it gets none of the instrumentation unless it goes through a script.
- Rejected: leaving the SKILL replay bare (one verify site would stay blind).

### millpy-bg heartbeat names its command

- Decision: `millpy-bg.py`'s worker heartbeat becomes `[mill-bg] HEARTBEAT <ts> elapsed=<N>s cmd=<cmd>`, where `<cmd>` is the inner argv joined with spaces and cut to 200 characters with a trailing `...` when longer.
  The worker stays stdlib-only (its fast path imports no mill modules).
  `_bg.py` does not parse heartbeat text at all (no `HEARTBEAT` match anywhere in it; liveness is PID/mtime/trailing-JSON based), so the format change cannot affect liveness detection and `_bg.py` is not touched.
  The line keeps the `[mill-bg] HEARTBEAT ` prefix anyway, for anyone grepping logs.
- Rationale: under `millpy-bg`, the bg log also receives the runner's own `[verify] HEARTBEAT` lines (stderr is redirected into the log), so the log shows both the outer job and the verify command currently running.
- Rejected: having `millpy-bg` discover the running verify command (cross-process plumbing for information that already arrives on stderr).

## Technical context

- Verify call sites today (all `subprocess.run(..., capture_output=True)`, no timeout):
  - `plugins/mill/scripts/_implementer_common.py` — `_run_verify_gate` (~line 791) and its lock-race retry inside it; `_run_verify_gates` (~line 945) sequences batch then module-wide; callers at ~1610 (inferred-success), ~1726, ~2005, ~2112, ~2219 (`_forward_output` and finalize paths).
    `_posix_shell_run_args` (~line 628) is the bash routing helper.
    `_extract_failure_signatures` and the 2000-char truncation shape are reused by `_done_gate._build_truncated_reason`.
  - `plugins/mill/scripts/_done_gate.py` — `run_preflight` and `run_gate`, `shell=True`, never-raise contract; callers in `skills/mill-go-base/SKILL.md` (Prepare pre-flight, ~line 550), `skills/mill-go-base/handoff.md` (~line 130), `skills/mill-quick/SKILL.md` (~line 101).
  - `plugins/mill/scripts/millpy-merge-in-subagent.py` — three verify `subprocess.run` calls (~lines 315, 456, 525), each with `env=_generous_terminal_env()`; pass that env as the runner's `env` base so the `COLUMNS`/`LINES` floor survives.
  - `plugins/mill/skills/mill-merge-in/SKILL.md` step 4 — orchestrator runs each batch `verify:` command bare via Bash, dispatching the verify-fix subagent on failure.
- `plugins/mill/scripts/_subprocess_util.py` — `run(argv, *, cwd, timeout, env, stdout, stderr, ...)` already kills the full process tree on timeout (`_run_windows_watchdog` with `taskkill /T /F`; POSIX `start_new_session` + `killpg`) and returns as soon as the child exits when stdout is not a pipe.
  It injects `PYTHONIOENCODING=utf-8` and prints spawn/exit breadcrumbs to stderr on non-zero exit; both are acceptable for verify.
- `plugins/mill/scripts/millpy-bg.py` — worker fast path, stdlib-only, `_HEARTBEAT_INTERVAL_S = 30`, heartbeat thread writes to the log file handle.
- `plugins/mill/scripts/_status.py` — log-section helpers to copy: `append_recovery_log`, `append_inferred_success_log`, `append_fork_fallback_log` and their `_find_*_block` helpers.
- `plugins/mill/scripts/_paths.py` — `status_path`, `require_status_path`, `sanitize_filename_component`.
- Config: `pipeline:` block in `plugins/mill/templates/mill-config.yaml` (~line 131) and the hub `mill-config.yaml`.
  `pipeline.baseline_verify_timeout_minutes` no longer exists.
- `mill-merge`'s `step_cleanup_commit` (`_merge.py` ~line 683) deletes `_mill/` in a commit reachable through `archive/<slug>`; anything uncommitted in `status.md` at that point is lost.
- `mill-go-base/SKILL.md` documents that `--stage finalize`'s verify replay inherits the orchestrator Bash shell's PATH; the runner must keep inheriting the environment (it only adds/overrides keys).

## Constraints

- No `CONSTRAINTS.md` at the hub root.
- `print()` / log output ASCII only (CLAUDE.md); all new lines use `--` / `->` style ASCII.
- `mill-config.yaml` hub file and the plugin template must stay in sync.
- Never-raise contracts of `_done_gate.run_gate` / `run_preflight` and `_run_verify_gate` (returns a stuck dict on any exception) are preserved.
- `millpy-bg.py`'s worker fast path stays stdlib-only.
- Path resolution goes through `_paths.py`; no inline container/hub path building.
- Verify commands in plan files start with `PYTHONPATH=` (this is a Python project).
- Tests use in-memory/tempfile fixtures; no real git/LLM in unit tests. Real short-lived child processes (`sys.executable -c ...`) are fine.
- **Pre-existing red tests on `main`.** The companion task (`e408e454`) removed the verify-baseline waiver, so a batch `verify:` that includes an already-failing test can never pass and halts mill-go.
  Measured on this worktree at discussion time, `run-all.py` reports `FAIL -- 13 of 125`, including `test-bg-liveness.py` (3 failures: `test_log_oserror_fallback_to_mtime`, `test_systemerror_fallback_to_mtime`, `test_check_bg_status_killed_before_json_fresh_mtime`) and `test-ask-thread.py`.
  Therefore: no batch `verify:` (batch-level or module-wide) may run `run-all.py` or any test file that fails before the batch's own change.
  Each verify names the specific test files the batch touches, and the plan writer re-checks each named file passes on the batch's base before using it.
  Fixing the pre-existing failures is out of scope.

## Testing

- `_verify_run.py` — TDD, new `unit_tests/test-verify-run.py`:
  - **Pipe-trap regression (TDD first):** a command whose child spawns a grandchild that inherits stdout and sleeps well past the parent's exit; `run_verify` returns within a small bound after the parent exits, with the parent's exit code.
  - Timeout: a command that sleeps past a tiny `timeout_s` returns `timed_out=True`, `exit_code=None`, and its process tree (including a grandchild) is gone.
  - First-run marker: first call `first_run=True`, second call in the same `git_root` `False`; marker written after a failing run and after a timeout too.
  - START / HEARTBEAT / END lines appear on stderr and in `.scratch/verify/verify.log`, with a heartbeat interval patched down to a fraction of a second; lines are ASCII.
  - Env: the child sees `MSBUILDDISABLENODEREUSE=1` and `DOTNET_CLI_USE_MSBUILD_SERVER=0` and still sees a caller-supplied env key.
  - Output: combined stdout+stderr read back from the `.out` file; `output_path` exists.
  - Launch failure (nonexistent cwd) returns a `VerifyRun` instead of raising.
  - `shell_mode` routing: `"posix"` vs `"native"` argv construction (unit-level, monkeypatched `shutil.which` / `os.name` as the existing `_posix_shell_run_args` tests do).
  - Timeout config resolution: default when absent, positive value honoured, zero/negative/non-numeric raises.
- `_status.append_verify_log` — `test-status.py`: section created on first append, rows appended in order, existing sections untouched.
- `_implementer_common` — `test-implementer-common.py`: existing verify-gate tests keep passing through the runner; timed-out gate returns the stuck dict with the reason prefix and `timed_out`; lock-race retry not attempted on timeout; `verify_runs` present on emitted envelopes for pass and fail.
- `_done_gate` — `test-done-gate.py`: timeout yields `blocked` with the prefix; `verify_runs` present on `ok` and `blocked`; `skipped` unchanged.
- `millpy-merge-in-subagent.py` — `test-millpy-merge-in-subagent.py`: runner is used with the generous-terminal env; timeout reported as a failed verify.
- `millpy-verify-run.py` — new CLI test: JSON shape, exit 0 on pass, 1 on fail and on timeout.
- `millpy-bg.py` — `test-millpy-bg.py` only (passes on `main`): heartbeat line format includes `elapsed=` and `cmd=`, keeps the `[mill-bg] HEARTBEAT ` prefix, long commands truncated with `...`.
  `test-bg-liveness.py` is not a verify target (pre-existing failures, see Constraints); liveness is unaffected because `_bg.py` never parses heartbeat text and is not modified.
- Config sync: mirror `test-ask-thread.py:229-234` — load both the hub `mill-config.yaml` and `plugins/mill/templates/mill-config.yaml` and assert `pipeline.verify_timeout_minutes` is present in each and equals `_verify_run`'s module default constant.
  Put the assertion in the new `test-verify-run.py`, not in `test-ask-thread.py`, which is already red on `main`.

## Q&A log

- **Q:** How should the pipe trap be fixed — file redirection, `MSBUILDDISABLENODEREUSE=1`, or both? **A:** [auto-pick] Both, plus `DOTNET_CLI_USE_MSBUILD_SERVER=0`, for every command. **Why:** redirection fixes mill's own wait; the env vars fix the same trap inside the verify command, which was the actual NORCE failure; both are confirmed by the reporting repo.
- **Q:** Default timeout value and scope? **A:** [auto-pick] `pipeline.verify_timeout_minutes: 20`, per command invocation, positive number required. **Why:** real suites are 2–4 minutes; 20 gives 5x headroom without sizing against a bug.
- **Q:** How is a timeout reported to mill-go? **A:** [auto-pick] Existing `stuck_type: verify` with a `[verify timed out after Ns: <label>]` reason prefix and `timed_out: true`. **Why:** keeps mill-go's routing untouched while making the cause explicit to the self-resolver.
- **Q:** Where does the durable timing record live? **A:** [auto-pick] A `## Verify log` section in `status.md`, committed by existing status commits plus `mill-merge-in` step 5. **Why:** follows the `_mill/`-on-branch convention and the existing status log sections; survives teardown via the branch and `archive/<slug>`.
- **Q:** What does "first run" key on? **A:** [auto-pick] Per worktree, via a marker in `<git_root>/.scratch/verify/`. **Why:** `.scratch/` shares the worktree's lifetime, so a resumed worktree on another machine is correctly cold.
- **Q:** Should `_done_gate` switch to bash routing? **A:** [auto-pick] No — the runner takes a `shell_mode`; `_done_gate` keeps `native` (`shell=True` semantics). **Why:** done-gate commands are written against today's shell; switching changes their meaning on Windows.
- **Q:** How is the `mill-merge-in` SKILL's bare verify replay instrumented? **A:** [auto-pick] A new `millpy-verify-run.py` CLI the SKILL calls instead of running the command bare. **Why:** otherwise that site stays blind.
