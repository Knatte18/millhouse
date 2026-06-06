# Discussion: Fix millpy-bg EXIT marker missing on wrapper crash

```yaml
task: Fix millpy-bg EXIT marker missing on wrapper crash
slug: mill-bg-exit-marker
status: discussing
parent: main
```

## Problem

`millpy-bg.py` launches a detached worker that runs a mill CLI (review, implement, fix,
plan-validator-fix), redirects its stdout/stderr to a `.scratch/bg-*.log`, and is supposed
to append `[mill-bg] EXIT <code>` when the worker exits. Orchestrators (`mill-go`,
`mill-plan`, `mill-start`) poll the log via `_bg.check_bg_status(log_path)` and branch on
`("running" | "exit" | "dead", …)`.

GitHub issues #420 and #424 reported that the `EXIT` line was frequently **never written** —
the worker's JSON summary was present in the log, the produced review/result file existed on
disk, but no `[mill-bg] EXIT`. The probable cause is psmux session teardown (or logout)
**hard-killing the worker process** after it finished its work but before it could append
`EXIT`. With no `EXIT` marker, `check_bg_status` returned `("dead", pid)`, which orchestrators
interpret as "worker died — halt/escalate." Operators had to manually confirm the result was
actually complete.

**Why now / current state.** The brief proposed two fixes: (1) wrap the EXIT-write in
`try/finally`, and (2) add a detection-side fallback — if the worker is dead but a valid JSON
result is in the log, treat it as success. **Both already landed** in commit `18ea1ff9`
("Fix millpy-bg EXIT marker and implementer reliability", 2026-06-06):

- `millpy-bg.py:78-84` — worker writes `[mill-bg] EXIT <code>` inside a `finally`.
- `_bg.py:17-33,112-113` — `_has_valid_json_result()` + a fallback branch in
  `check_bg_status`: dead PID + parseable trailing JSON line ⇒ `("exit", 0)`.

That work **eliminated the false-`dead` failures** but left a real residual defect this task
must close: a worker that finished and was then hard-killed is now reported `("running", pid)`
for up to **five minutes** before completion is recognized — because the liveness probe's
mtime heuristic shadows the JSON-completion fallback (see Decisions → `json-completion-ordering`).
Across a full mill-go run (#424 saw this on every bg invocation — 6 batches + 2 holistic
rounds), that is ~8× five-minute stalls of wasted polling.

This task is **hardening + correctness of completion detection**, not a from-scratch fix. The
literal try/finally + JSON fallback are done; the ordering defect, the unenforced trailing-JSON
contract, and the misleading "the finally is the fix" framing are not.

## Scope

**In:**

- Fix the completion-detection **ordering defect** in `_bg.check_bg_status` so a finished
  worker that was hard-killed (valid trailing JSON, no `EXIT`, PID not affirmatively alive) is
  reported `("exit", 0)` on the **next poll**, not after the 5-minute staleness window.
- Distinguish **affirmatively-alive** (the kill-probe positively confirms the process is
  running) from **assumed-alive-via-mtime** (the kill-probe was inconclusive — the Windows
  norm — and we fell back to log-mtime freshness). The JSON-completion sentinel overrides the
  latter but never the former.
- Make the **trailing-JSON completion contract explicit**: document in `_bg.py` and
  `millpy-bg.py` that completion of a hard-killable bg worker is detected via a single
  parseable JSON line emitted as the worker's final stdout, and that every CLI dispatched
  through `millpy-bg` MUST emit one. Add a guard test asserting each currently-dispatched CLI's
  success path emits a trailing JSON summary line.
- Add a regression test reproducing the exact #420/#424 shape (`WORKER PID` + JSON summary +
  no `EXIT` + dead PID + **fresh** mtime) and asserting `check_bg_status → ("exit", 0)`.
- Correct the comments/docstrings that imply the `try/finally` is the fix: it handles only the
  clean-exit and in-process-exception paths; the kill-resilient backstop is the JSON sentinel,
  and the structural resolution is agent-mode dispatch (no detached worker at all).

**Out:**

- **Agent-mode dispatch** (`dispatch: agent`, the default since `7ddc1e28`). It runs the
  reviewer/implementer in-process via the Agent SDK — there is no detached worker, no log, no
  EXIT marker, and no `check_bg_status` call. This task touches only the `subprocess`/`psmux`
  fallback paths that still use `millpy-bg`. Do not modify agent-mode code or behavior.
- **Removing or deprecating** subprocess/psmux dispatch or `millpy-bg` itself. They remain live
  (e.g. `mill-plan`'s `plan-validator-fix`). Retirement is a separate, larger task.
- **OS-level signal handlers / atexit hooks** to write `EXIT` on kill. On Windows a psmux
  teardown is a `TerminateProcess`, which is uncatchable; a handler cannot help. Detection-side
  is the only robust path. Do not add signal/atexit machinery.
- The **launcher-never-spawned-worker** case (worker process fails to start ⇒ no log file at
  all ⇒ `("dead", None)`). That is correct behavior and a distinct failure class; leave as-is.
- Lowering `_STALE_LOG_SECONDS` or otherwise retuning the staleness window for the
  genuinely-incomplete (no-JSON) case. The staleness fallback stays as the backstop for workers
  killed *before* emitting their JSON summary.

## Decisions

### json-completion-ordering

- Decision: In `_bg.check_bg_status`, consult the trailing-JSON completion sentinel **before**
  accepting an mtime-assumed "alive" verdict. Concretely, the resolution order becomes:
  (1) `EXIT` present → `("exit", code)`; (2) process is **affirmatively alive** (kill-probe
  positively confirms) → `("running", pid)`; (3) valid trailing JSON present → `("exit", 0)`;
  (4) otherwise apply the existing mtime-staleness logic → `("running", pid)` while fresh,
  `("dead", pid)` once stale. The net change: a finished-then-hard-killed worker (JSON present,
  kill-probe inconclusive, fresh mtime) resolves to `("exit", 0)` immediately instead of
  sitting in `("running", pid)` for `_STALE_LOG_SECONDS`.
- Rationale: mtime-freshness is a weak liveness signal; a parseable terminal JSON summary is a
  strong completion signal. When the OS cannot confirm the process is alive (the Windows norm,
  where `os.kill(pid, 0)` raises and we fall back to mtime), the completion signal should win.
  This is exactly the #420/#424 scenario and the only thing standing between the current
  behavior and prompt recognition.
- Rejected:
  - *Lower `_STALE_LOG_SECONDS`* — shrinks the stall but does not remove it, and weakens the
    backstop for workers killed before emitting JSON.
  - *Treat any JSON-present log as done regardless of liveness* — would false-complete a worker
    that legitimately emits a JSON line and keeps running. Gating on "not affirmatively alive"
    preserves correctness for genuinely-running workers (and for the current CLIs JSON is the
    terminal line anyway).
  - *Have the launcher poll and write EXIT* — the launcher exits immediately after detaching
    the worker (it only returns `pid=… log=…`); it is not around to observe completion.

### affirmative-vs-assumed-liveness

- Decision: Expose the distinction between "kill-probe positively confirmed alive" and
  "kill-probe inconclusive, assumed alive via fresh mtime." `is_bg_worker_alive` currently
  collapses both into `alive=True`. Refactor so `check_bg_status` can tell them apart — e.g. a
  small internal helper returning a tri-state / a reason flag, or `check_bg_status` performing
  its own ordered probe. mill-plan picks the cleanest shape; the only hard requirement is that
  the affirmative case keep returning `("running", pid)` and the assumed case yield to a present
  JSON sentinel.
- Rationale: Required to implement `json-completion-ordering` without regressing the
  genuinely-running case. Today there is no way for a caller to know *why* `is_bg_worker_alive`
  said alive.
- Rejected: *Keep the boolean and infer from a second os.kill in check_bg_status* — duplicates
  the probe and its platform-specific exception handling; better to compute the distinction once.

### keep-finally-clarify-framing

- Decision: Keep the worker's `try/finally` `EXIT`-write. Update the surrounding comments in
  `millpy-bg.py` and the module docstring in `_bg.py` to state plainly: the `finally` covers the
  clean-exit and in-process-exception paths (and makes detection instant when it survives); it
  does **not** survive a hard process kill; the kill-resilient backstop is the trailing-JSON
  sentinel; and agent-mode dispatch is the structural resolution (no worker at all).
- Rationale: The `finally` is correct and cheap and gives instant detection in the common case.
  The only problem is the *narrative* that it "fixes" #420/#424 — it does not, and the next
  maintainer must not believe it does.
- Rejected: *Remove the finally* — would lose instant detection on every clean exit and force
  even successful runs through the JSON fallback.

### trailing-json-contract

- Decision: Treat "every CLI dispatched through `millpy-bg` emits exactly one parseable JSON
  line as its final stdout" as an enforced contract. Document it where the worker is defined and
  where the fallback consumes it, and add a guard test that, for each currently-dispatched CLI
  (`millpy-review-discussion`, `millpy-review-plan`, `millpy-review-code`, `millpy-implement`,
  `millpy-fix`), asserts the success path's final stdout line parses as JSON.
- Rationale: The completion fallback's correctness depends entirely on this invariant. It is
  currently implicit; a future CLI added to the millpy-bg path that does not emit trailing JSON
  would silently reintroduce false-`dead`/`running` behavior. Making it explicit + tested
  prevents the regression.
- Rejected: *Leave it implicit* — that is the latent footgun this task exists to remove.

## Technical context

Relevant files (all under `plugins/mill/scripts/` unless noted):

- **`millpy-bg.py`** — launcher + worker. Worker mode (`--_worker`, stdlib-only fast path,
  lines 27-93): opens the log, writes `[mill-bg] WORKER PID=<pid> START …`, runs the inner cmd
  via `subprocess.run(stdout=log_f, stderr=STDOUT)`, captures the exit code, and writes
  `[mill-bg] EXIT <code>` in a `finally`. The `finally` only runs if the Python worker process
  itself is not hard-killed. Launcher mode (lines 95-195) validates cwd is a task worktree,
  creates the log path, and spawns the worker detached via `_subprocess_util.popen_detached`.
- **`_bg.py`** — the liveness/completion probe consumed by all orchestrators.
  - `is_bg_worker_alive(log_path) -> (alive, pid|None)` (lines 36-76): finds `WORKER PID`,
    short-circuits dead on `EXIT`, else probes `os.kill(pid, 0)`. On Windows `os.kill` with
    sig 0 typically raises `OSError`/`SystemError`; that path falls back to log-mtime staleness
    (`_STALE_LOG_SECONDS = 5*60`). **This is where mtime-freshness masquerades as liveness.**
  - `check_bg_status(log_path) -> (status, pid_or_code)` (lines 79-114): the current order is
    EXIT → `is_bg_worker_alive` (returns `"running"` when alive) → re-read EXIT →
    `_has_valid_json_result` → `"dead"`. The JSON fallback at line 112 sits **after** the
    liveness check, so an mtime-assumed-alive verdict prevents it from ever firing until the log
    goes stale. The fix re-orders these per `json-completion-ordering`.
  - `_has_valid_json_result(text)` (lines 17-33): scans lines in reverse for the first
    `{`-prefixed line and returns whether it `json.loads`-es. Reuse as-is.
- **Dispatch selection**: `_agent_dispatch.resolve_dispatch_mode(cfg)` reads
  `cfg["llm"]["claude"]["dispatch"]` ∈ `{subprocess, psmux, agent}`. The template default is
  `agent` (`plugins/mill/templates/mill-config.yaml:105`). Only `subprocess`/`psmux` reach
  `millpy-bg`; `agent` runs in-process and never touches this code.
- **Worker JSON outputs** (the sentinel the fallback keys on):
  - review CLIs emit a one-line summary `{"type": …, "round": …, "verdict": …, "reviews": […]}`.
  - `millpy-implement.py` / `millpy-fix.py` emit `{"status": …, …}` (incl. `stuck` variants) as
    their final stdout line. These are the success/stuck terminal lines the contract guards.
- **Consumers of `check_bg_status`** (do not change their contract): `mill-go/SKILL.md` (many
  poll sites; `"dead" → stuck_type: infrastructure` escalation, `"running" → keep polling`),
  `mill-plan/SKILL.md` (`plan-validator-fix`), `mill-start/SKILL.md` (discussion-review),
  `mill-pause/SKILL.md` (let an in-flight poll finish). The fix only changes *when* `"exit"` vs
  `"running"` is returned for the finished-but-killed case; the string contract and all three
  branch labels stay identical, so no SKILL edits are required (a one-line doc note in the
  poll-branch explanation is optional, not load-bearing).

Gotchas:

- `os.kill(pid, 0)` semantics differ by platform; the existing tests
  (`test_log_oserror_fallback_to_mtime`, `test_systemerror_fallback_to_mtime`) monkeypatch
  `os.kill` to exercise the fallback deterministically. Reuse that mocking style — do not rely on
  real process liveness in unit tests.
- Tests must be fully in-memory/tempfile with no real git/LLM (unit-test rule). Backdate mtime
  with `os.utime` to drive the staleness branch, exactly as `test_log_dead_pid_no_exit` does.
- ASCII-only stdout in any `print`/`_log` (Windows cp1252).

## Constraints

- No `CONSTRAINTS.md` at the hub root (checked — absent).
- Worker fast-path in `millpy-bg.py` is **stdlib-only by design** (no mill imports before the
  `--_worker` branch resolves) so it can run in a bare detached process. Any worker-side change
  must preserve that — keep new logic in `_bg.py` (consumer side), not in the worker fast-path.
- Preserve the existing `check_bg_status` / `is_bg_worker_alive` public return shapes and string
  labels; orchestrator skills depend on them verbatim.
- Unit tests only (`plugins/mill/unit_tests/test-*.py`, run via `run-all.py`); no real
  git/LLM/subprocess. ASCII-only diagnostics.

## Testing

TDD candidate — this is a pure-logic change with a precise, reproducible failing case. Write the
regression test first; it fails against current `check_bg_status` (returns `("running", pid)`)
and passes after the re-order.

Module `test-bg-liveness.py` (extend existing):

- **#420/#424 regression (the core test):** log with `WORKER PID=<dead>` + a valid trailing JSON
  summary line + **no** `EXIT` + **fresh** mtime, with `os.kill` monkeypatched to raise
  `OSError(22)` (Windows-shape inconclusive probe). Assert `check_bg_status → ("exit", 0)`.
  Reference #420/#424 in the docstring. (This currently returns `("running", pid)`.)
- **Affirmatively-alive worker is never false-completed:** log with `WORKER PID=<current>` + a
  mid-stream JSON-looking line + no `EXIT`, `os.kill` succeeding (real current pid or mocked
  success). Assert `check_bg_status → ("running", pid)` — the JSON sentinel must NOT override a
  positively-confirmed live process.
- **Killed before emitting JSON still degrades correctly:** dead PID + no `EXIT` + no parseable
  JSON + fresh mtime → `("running", pid)`; same with stale mtime → `("dead", pid)`. Confirms the
  staleness backstop is intact for genuinely-incomplete workers.
- **EXIT present still wins** over everything (existing `test_check_bg_status_exit_found`
  behavior preserved).
- Keep all existing `test-bg-liveness.py` cases green; the affirmative-alive and EXIT paths must
  not regress.

Trailing-JSON contract guard (new test, lightweight): for each CLI on the millpy-bg dispatch
path (`millpy-review-discussion/plan/code`, `millpy-implement`, `millpy-fix`), assert its
success/stuck terminal stdout is a single JSON line. Prefer asserting on a captured-output unit
seam over launching real subprocesses; if a given CLI has no such seam, assert structurally
(e.g. the final `print(...)` in the success path is `json.dumps(...)`) rather than adding a real
run. Keep it in-memory.

## Q&A log

- **Q:** The brief's literal fix (try/finally + JSON fallback) is already in `main` via
  `18ea1ff9`. What should this task actually deliver? **A:** Harden the real remaining gap and
  lock it with regression tests, then close — the operator delegated the scope call ("do what
  you feel is best") and option 1 (surgical hardening) was the recommendation.
- **Q:** What *is* the real remaining gap, given both halves of the brief are implemented?
  **A:** The JSON-completion fallback in `check_bg_status` is ordered *after* the liveness probe,
  whose Windows mtime-freshness heuristic reports a freshly-killed-but-finished worker as alive —
  so completion is recognized only after the 5-minute staleness window, not on the next poll.
- **Q:** Should we also delete/deprecate subprocess+psmux now that agent mode is the default?
  **A:** No — out of scope; they remain live (e.g. `plan-validator-fix`). Retirement is a
  separate, larger task with cross-skill blast radius.
- **Q:** Add signal/atexit handlers so the worker writes EXIT even when killed? **A:** No — on
  Windows the psmux teardown is an uncatchable `TerminateProcess`; detection-side (JSON sentinel)
  is the only robust path.
- **Q:** Keep the `try/finally` EXIT-write? **A:** Yes — it gives instant detection on clean
  exits and exception paths; only the comments that imply it "fixes" the hard-kill case get
  corrected.
