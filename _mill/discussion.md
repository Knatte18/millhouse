# Discussion: Wiki-daemon + bg-worker + test-suite robustness on Windows

```yaml
task: Wiki-daemon + bg-worker + test-suite robustness on Windows
slug: infra-robustness-windows
status: discussing
parent: main
```

## Problem

Four cross-cutting infrastructure bugs surfaced after the V3 wiki daemon went
live and `millpy-bg` became the standard implementer/review launcher. All four
sit on the **client / harness / test-infra** side of the daemon-or-worker
boundary — the daemon and worker themselves are healthy, but consumers don't
degrade gracefully when the OS or other concurrent work disturbs them. They were
hit during real concurrent `mill-go` runs and Windows session edges (logout,
RDP disconnect, sleep).

**Why now:** concurrent mill-go runs are now routine, so the rare-race failures
(daemon busy under two simultaneous writers; worker killed by logout) have
become recurring interruptions that crash skills or hang the orchestrator
indefinitely. Two of the four issues were partially mitigated by earlier work
(see Scope/Out), so this task closes the remaining gaps rather than starting
from the proposal's original premises.

Exploration changed two of the four premises — both recorded under Decisions and
Q&A so mill-plan does not re-derive a fix for something already done:

- **#395** (test-fold flaky): `test-fold.py` now runs entirely in-process
  (`WIKI_DAEMON_INPROCESS=1`), so it no longer spawns a real daemon and the
  original "daemon did not start within timeout" flake cannot originate there.
  This task hardens the production spawn path, not the (already-fixed) test.
- **#391** (logout kills workers): `popen_detached` already launches via
  `cmd /c start "" /B /MIN` + `CREATE_BREAKAWAY_FROM_JOB`, so the proposal's
  "optional" prevention is already in place. A full Windows session logout
  cannot be survived by an ordinary user process regardless, so the real
  deliverable is **detect + recover**, not prevention.

## Scope

**In:**

- **#400 — `_client` recv-timeout retry + `WikiBusyError`.** Wrap the per-op
  `_connect_send_recv` call in a bounded retry (3 attempts, 2s/4s/8s backoff)
  on `TimeoutError`/`socket.timeout`; on exhaustion raise a new
  `WikiBusyError(WikiError)` instead of a bare `TimeoutError`. Lower the
  per-attempt recv timeout to ~3s so retries are meaningful. The health-probe
  path stays single-shot and fast.
- **#393 — `_bg.is_bg_worker_alive` chained `SystemError`.** Broaden the
  `os.kill(pid, 0)` probe's `except` to catch `SystemError` alongside `OSError`
  and fall through to the mtime fallback (treat as ambiguous).
- **#395 — daemon-spawn robustness (hardening, not live-bug).** Extract the
  existing `_ensure_daemon` socket-poll into a shared `wait_for_socket_reachable`
  helper; bump `SPAWN_TIMEOUT` on Windows (10 → ~20s); add a regression test for
  the helper; document that the original flake was resolved by the in-process
  test conversion. Close #395 with that note.
- **#391 — in-session bg-worker liveness detection + recovery.** Add a liveness
  check to the in-session "poll log until `[mill-bg] EXIT`" loop so a worker
  that dies without writing EXIT (logout) is detected instead of hung on
  forever. Introduce `stuck_type: infrastructure`. Recovery reuses the existing
  crash-recovery re-fire path: a plain **fresh re-fire** of the CLI (no
  `--resume`) — the killed session is dead and cannot be re-attached, exactly as
  the existing `running`-state Resume path documents. Encapsulate the poll loop
  in a tested `_bg` helper.

**Out:**

- **Preventing logout death** of bg workers — not achievable for an ordinary
  user-session process; `CREATE_BREAKAWAY_FROM_JOB` (already present) only
  escapes Job Objects, not session logoff. No service/session-0 work.
- **Per-skill retry wrappers around `set_phase`** — internal retry +
  `WikiBusyError` fixes the reported crash; skills simply let `WikiBusyError`
  propagate (distinguishable from "daemon dead"). No retry-at-every-callsite.
- **No new `mill-go resume --from-killed` CLI flag** — recovery routes through
  the existing crash-recovery / Resume machinery; no new entry point.
- **Reworking `test-fold.py`** — it is already in-process and correct.
- **The daemon and worker internals** (`wiki/_server.py`, worker fast-path) —
  untouched; all fixes are client/harness/test-infra side.

## Decisions

### 400-retry-placement

- Decision: Centralize the busy-retry in the client **dispatch** path — wrap the
  op's `_connect_send_recv` (the call inside `_dispatch`, `_client.py:118`), not
  the health probe inside `_ensure_daemon`. Retry 3 attempts with 2s/4s/8s
  backoff on `TimeoutError`/`socket.timeout`; raise `WikiBusyError` on
  exhaustion. Lower the per-op recv timeout to ~3s (worst case ~23s before
  `WikiBusyError`).
- Rationale: All read+write ops benefit uniformly; the health-check path in
  `_ensure_daemon` (which catches `OSError` and respawns) must stay fast and
  single-shot, so it is deliberately excluded. A 3s per-attempt timeout catches
  a stalled-but-alive daemon without a 10s-per-attempt worst case.
- Rejected: (a) wrapping only write ops — reads can stall under load too;
  (b) wrapping inside `_connect_send_recv` for every caller including health
  probes — would slow respawn detection; (c) flat 10s per attempt — ~44s
  worst-case hang before raising.

### 400-busy-error-propagation

- Decision: `WikiBusyError` is a new `WikiError` subclass exported from
  `wiki/__init__.py` and imported in `_client.py`. Skills consuming `set_phase`
  et al. let it propagate; no per-callsite retry is added.
- Rationale: The internal 3-attempt retry already absorbs the transient
  busy-window that caused the reported crash. `WikiBusyError` is the clean
  exhaustion signal that lets a caller distinguish "daemon busy" from "daemon
  dead" — adding retry at every skill callsite is unneeded surface (YAGNI).
- Rejected: single retry at the highest-traffic callsite (mill-go Handoff);
  retry-once wrapper used by all callsites. Both add surface for a window the
  internal retry already covers.

### 393-catch-broadening

- Decision: Change `_bg.py:48` `except OSError as exc:` to
  `except (OSError, SystemError) as exc:`. Any unexpected probe exception is
  treated as ambiguous and falls through to the log-mtime staleness fallback.
- Rationale: On Windows, `os.kill(pid, 0)` against a recycled/over-privileged
  PID can raise a chained `SystemError` ("returned a result with an exception
  set") in addition to the `OSError`; the narrow `except OSError` lets it escape
  and crash the orchestrator. Explicit `(OSError, SystemError)` is the smallest
  correct widening; `KeyboardInterrupt`/`SystemExit` are not subclasses of
  either, so they are not swallowed.
- Rejected: bare `except Exception` with explicit re-raise of
  `KeyboardInterrupt`/`SystemExit` — broader than needed and easier to misread.

### 395-hardening-not-live-bug

- Decision: Treat #395 as robustness hardening of the **production** spawn path,
  not a fix to `test-fold.py`. Extract the inline `socket.create_connection`
  poll in `_ensure_daemon` (`_client.py:521-533`) into a reusable
  `wait_for_socket_reachable(host, port, *, timeout, interval)` helper; have
  `_ensure_daemon` call it. Bump `SPAWN_TIMEOUT` to ~20s on Windows only (keep
  10s elsewhere, or unconditional 20s if simpler — mill-plan's call). Close
  #395 noting the original flake was resolved by the in-process conversion.
- Rationale: The only real-daemon spawn is production `_ensure_daemon`, which
  already polls the socket; the flake's test-side cause is gone. Extracting the
  poll gives one tested helper and a documented, longer Windows budget for cold
  cache + CPU load.
- Rejected: hunting for a current real-daemon repro before acting (the in-process
  conversion already removed the test-side cause); dropping #395 entirely
  (the production spawn path still benefits from the longer budget + shared
  helper, and the issue should be closed with a rationale, not silently).

### 391-detect-and-recover

- Decision: Add a liveness check to the in-session poll loop. Define a `_bg`
  helper, e.g. `wait_for_bg_terminal(log_path, *, poll_interval) -> ("exit",
  code) | ("dead", pid)`, that loops: check for `[mill-bg] EXIT` first; if
  absent, call `is_bg_worker_alive`; if the worker is dead **and** EXIT is still
  absent, **re-read the log once** to close the EXIT-write-in-flight window, and
  only then return `("dead", pid)`. The orchestrator treats `("dead", …)` as a
  new `stuck_type: infrastructure`. Recovery reuses the existing crash-recovery
  re-fire path: a plain **fresh re-fire** of the CLI — no `--resume`, no
  warm-session re-attach. The killed session is dead and cannot be re-attached;
  the CLI re-initialises `state -> running`, captures a new snapshot, and spawns
  a fresh implementer session. This is byte-identical to the existing
  `running`-state Resume recovery (`mill-go/SKILL.md:318`).
- Rationale: The in-session loop ("`cat` until EXIT", repeated ~6× across
  mill-go/mill-start) has no liveness check and hangs forever when a worker is
  killed by logout. `is_bg_worker_alive` already short-circuits to `(False, pid)`
  when EXIT is present, so the only extra race guard needed is one re-read.
  Centralizing in a helper means the new logic is written and tested once.
  `millpy-implement.py` hardcodes `resume=False` (`:186`) and has no `--resume`
  flag, and the documented design treats an interrupted session as dead — so a
  fresh re-fire is both the simplest and the only consistent recovery.
- Rejected: detection-only with immediate halt (no auto-recovery); adding a
  dedicated `mill-go resume --from-killed` CLI flag (the existing Resume / branch
  (c) machinery already re-fires on a dead worker); building a new warm-session
  `--resume-session <id>` mechanism on `millpy-implement.py` (contradicts the
  "session is dead" design and is unneeded surface).

### 391-infrastructure-stuck-policy

- Decision: On detected infrastructure death — **interactive mode:** surface to
  the user with re-fire (fresh) / block options. **`autonomous_mode`:**
  auto-retry **once** with a fresh re-fire; if the re-fire also dies, block with
  `blocked_reason: "infrastructure: bg worker died (logout?)"`.
- Rationale: Logout is a transient external event, so one silent fresh re-fire
  is the right reflex under autonomous mode;
  bounding it at one retry prevents an unbounded re-fire loop if the machine is
  genuinely down. Interactive mode keeps the "never guess when stuck — surface
  options" principle.
- Rejected: always block immediately even in autonomous mode (wastes a cheap,
  recoverable re-fire when the machine is back); unbounded auto-retry (spins if
  the machine stays down).

## Technical context

Files mill-plan will touch (paths relative to repo root; operational scripts
live under `plugins/mill/scripts/`):

- `plugins/mill/scripts/wiki/_client.py`
  - `_dispatch` (`:91`) calls `_connect_send_recv(host, port, req)` (`:118`) —
    wrap this call in the busy-retry.
  - `_connect_send_recv` (`:569`) — single socket timeout covers `recv`; lower
    the per-op default and/or thread a shorter timeout from the retry wrapper.
  - `_ensure_daemon` (`:465`) — its health probe uses
    `_connect_send_recv(..., timeout=1.0)` and catches `OSError`; **do not** add
    busy-retry here. The inline spawn poll (`:521-533`) is the code to extract
    into `wait_for_socket_reachable`. `SPAWN_TIMEOUT` is the module constant at
    `:39`.
    - **Loop-shape caveat (mill-plan's call):** the current poll reads the
      state file *inside* the loop to discover `host`/`port` (the daemon writes
      `.wiki-daemon.json` on startup), so a `wait_for_socket_reachable(host,
      port, ...)` helper that assumes host/port are known up front cannot be
      mechanically split out. mill-plan must either (a) keep the state-file read
      in an outer loop and call the helper once host/port are known, or (b) give
      the helper a state-file-aware signature. Either is acceptable; this is a
      deliberate design choice for the plan writer, not a mechanical extraction.
- `plugins/mill/scripts/wiki/__init__.py` — error hierarchy at `:45-75`
  (`WikiError` base, then `WikiNotFoundError`, `WikiConflictError`,
  `WikiPushError`, `WikiProtocolError`, `WikiStartupError`, `WikiPathError`).
  Add `WikiBusyError(WikiError)`; export it (and add to `_client.py`'s import
  block at `:13-37`).
- `plugins/mill/scripts/_bg.py` — `is_bg_worker_alive` (`:15`); broaden the
  `except` at `:48`. Add the new `wait_for_bg_terminal` helper here (it already
  owns `_PID_RE`, `_EXIT_RE`, `_STALE_LOG_SECONDS`).
- `plugins/mill/scripts/_subprocess_util.py` — `popen_detached` (`:296`) already
  uses `start /B` + `CREATE_BREAKAWAY_FROM_JOB` (`:334-339`); **no change** for
  prevention. Reference only.
- `plugins/mill/scripts/millpy-implement.py` — the recovery target. Accepts only
  a positional `batch_name` and hardcodes `resume=False` (`:186`); it has **no**
  `--resume` flag and the documented design treats an interrupted session as
  dead. The `infrastructure`-death recovery therefore re-fires it exactly as the
  existing `running`-state Resume does (`millpy-bg ... millpy-implement.py
  <batch_name>`, no resume flag). **No change to this CLI** — referenced so
  mill-plan does not invent a warm-resume flag.
- `plugins/mill/skills/mill-go/SKILL.md` — the in-session poll instruction
  ("Poll the log file with `cat <log-path>` until `[mill-bg] EXIT` appears")
  appears at `:167`, `:239`, `:250`, `:262`, `:279`, `:445`. Crash-recovery
  branch (c) at `:385-418` already probes `is_bg_worker_alive` at resume —
  mirror its Dead→re-fire logic for the in-session case. Stuck escalation is at
  `:287-305` (autonomous_mode at `:287`) and the holistic variants at
  `:491-492`; add the `infrastructure` `stuck_type` handling there.
- `plugins/mill/skills/mill-start/SKILL.md` — also contains the "`cat` until
  EXIT" poll pattern (Discussion Review step 2) and should adopt the helper /
  liveness check for consistency. **Dead-worker recovery policy:** mill-start is
  always interactive and has no `stuck_type` / autonomous machinery, so on
  `wait_for_bg_terminal` returning `("dead", pid)` it surfaces a clear message
  to the operator ("discussion-review worker died (logout?); re-run the
  discussion-review step") and **halts** — no auto-re-fire. The operator
  re-invokes the step. This differs from mill-go, which has the
  `infrastructure` `stuck_type` + autonomous one-retry path.
- Existing `stuck_type` values are `transient` / `verify` / `logic`
  (`_implementer_common.py:53,59`, `millpy-fix.py:291`, `millpy-implement.py`).
  `infrastructure` is the new fourth value — keep the JSON envelope shape
  `{"status":"stuck","stuck_type":"infrastructure","reason":...}`.

Concurrency / platform notes:

- `socket.timeout` is an alias of `TimeoutError` since Python 3.10; catch
  `TimeoutError` (covers both). The repo runs on Python 3.13.
- ASCII-only stdout (`—`→` -- `, `->`→` -> `) — Windows cp1252 crashes on
  non-ASCII (`print`/`_log`).
- Unit tests run in-process (`WIKI_DAEMON_INPROCESS=1`, set in
  `_test_helpers.py:39` and `test-fold.py:17`); no test spawns a real daemon.

## Constraints

- No `CONSTRAINTS.md` at the hub root (checked; absent).
- ASCII-only stdout in `print`/`_log` output (cp1252).
- Operational script calls go through the cache (`${CLAUDE_PLUGIN_ROOT}`), never
  the source tree, except unit tests (`uv run --project plugins/mill`).
- `verify:` commands in plan files MUST start with a literal empty
  `PYTHONPATH=` prefix (the `verify-not-isolated` check) so the test subprocess
  uses worktree code, not V2-cache modules.
- Daemon/worker internals are off-limits; stay on the client/harness/test side.
- Helpers with path args must not consult cwd for config — thread explicit paths.

## Testing

All tests are in-process unit tests under `plugins/mill/unit_tests/`
(`test-<name>.py`, run via `run-all.py`; in-memory/tempfile fixtures, no real
git/LLM). TDD candidates are the pure helpers (#400 retry, #393 widening,
`wait_for_socket_reachable`, `wait_for_bg_terminal`).

- **#400 retry + `WikiBusyError`** (`test-wiki-daemon.py`, extend): mock
  `wiki._client.socket.create_connection` / the recv path to raise
  `TimeoutError` N times. Assert: (a) success after a transient timeout that
  clears within the retry budget; (b) exactly 3 attempts then `WikiBusyError` on
  persistent timeout; (c) backoff sequence is 2s/4s/8s (patch `time.sleep` and
  record call args — do not actually sleep); (d) the health-probe path in
  `_ensure_daemon` is NOT wrapped (single attempt). Assert `WikiBusyError` is a
  `WikiError` subclass and is exported.
- **#393 `SystemError` widening** (`test-bg-liveness.py`, extend): patch
  `os.kill` to raise a chained `SystemError`; assert `is_bg_worker_alive` returns
  via the mtime fallback (no propagation) — fresh-log → `(True, pid)`, stale-log
  → `(False, pid)`. Existing cases (EXIT present, ProcessLookupError,
  PermissionError, unknown OSError) must stay green.
- **#395 `wait_for_socket_reachable`** (new or `test-wiki-daemon.py`): a bound
  listening socket → returns reachable quickly; an unbound/closed port →
  honours the timeout and signals failure without raising past the budget.
  Assert `_ensure_daemon` calls it (behavioural, via mock) and the Windows
  `SPAWN_TIMEOUT` bump is in effect.
- **#391 `wait_for_bg_terminal`** (`test-bg-liveness.py`, extend): (a) EXIT
  present → `("exit", code)`; (b) worker alive, no EXIT → keeps polling (bound
  the test with a small max-iterations / patched probe); (c) worker dead, no
  EXIT, re-read still shows no EXIT → `("dead", pid)`; (d) **race guard** —
  probe reports dead but the re-read now shows EXIT → `("exit", code)`, NOT
  dead. Patch the liveness probe and log reads; do not spawn real processes.
- **Un-automatable parts** — document a manual verification checklist in the
  task result rather than gating on OS events: (i) actual Windows logout/login
  with a mill-go batch running → orchestrator surfaces `infrastructure` stuck
  and a fresh re-fire recovers; (ii) the #395 "10 consecutive green runs" loop
  under
  cold cache + CPU load. No integration test that spawns+kills a real daemon
  (rejected as heavier than the value here).

## Q&A log

- **Q:** #395 — test-fold is already in-process and can't reproduce the flake;
  how to handle it? **A:** Treat as robustness hardening, not a live-bug fix —
  extract `wait_for_socket_reachable`, bump Windows `SPAWN_TIMEOUT` 10→~20s,
  regression-test the helper, close #395 noting the in-process conversion
  resolved the original flake.
- **Q:** #391 — prevention (`CREATE_BREAKAWAY_FROM_JOB`) is already done and
  logout is unpreventable; what's the deliverable? **A:** Detect + recover via
  existing machinery — add a liveness check to the in-session poll loop, surface
  a new `stuck_type: infrastructure`, route recovery through the existing
  crash-recovery re-fire path — a plain fresh re-fire (no `--resume`; the killed
  session is dead, matching the existing `running`-state Resume). No new CLI flag.
- **Q:** #400 — where does the busy-retry live? **A:** Centralize in the client
  dispatch path (wrap the op's `_connect_send_recv`, not the health probe);
  3 attempts at 2s/4s/8s; raise `WikiBusyError(WikiError)` on exhaustion.
- **Q:** #400 — should skill callsites retry on `WikiBusyError`? **A:** Out of
  scope — internal retry fixes the crash; skills let `WikiBusyError` propagate.
- **Q:** A shared in-session poll helper, or inline prose in ~6 places? **A:**
  Add a small `_bg` helper (`wait_for_bg_terminal`) that encapsulates
  poll-until-EXIT-or-dead, called from each site.
- **Q:** `infrastructure` stuck behaviour under `autonomous_mode`? **A:**
  Auto-retry once via a fresh re-fire, then block if still dead; interactive mode
  surfaces retry/block options.
- **Q:** #400 per-attempt timeout budget? **A:** Lower per-attempt recv timeout
  to ~3s and keep 2s/4s/8s backoff (worst case ~23s before `WikiBusyError`).
- **Q:** Liveness-probe race (worker dies just after writing EXIT)? **A:** Check
  EXIT first, then liveness; on dead-without-EXIT do one more log re-read before
  declaring infrastructure death — `is_bg_worker_alive` already short-circuits
  on EXIT, so one re-read closes the write-in-flight window.
- **Q:** How to verify #391/#395 given un-automatable OS events? **A:**
  Unit-test the mechanisms; document a manual checklist for the logout repro and
  the 10× green-run loop. No real-daemon kill integration test.
- **Q:** (review r1 gap) How does `infrastructure`-death recovery re-fire — warm
  `--resume` or fresh start? **A:** Fresh re-fire, no `--resume`. `millpy-implement.py`
  has no `--resume` flag (`resume=False` hardcoded at `:186`) and the documented
  `running`-state Resume already treats an interrupted session as dead; warm
  re-attach would contradict that design. All `--resume`/warm-session language
  removed from the #391 decisions.
- **Q:** (review r1 note) Can `wait_for_socket_reachable(host, port, ...)` be
  mechanically extracted from `_ensure_daemon`'s spawn poll? **A:** No — the loop
  reads host/port from the state file *inside* the loop, so extraction needs a
  design choice (outer state-file read, or a state-file-aware helper signature).
  Flagged as mill-plan's call in Technical context.
- **Q:** (review r2 gap) What does mill-start do when `wait_for_bg_terminal`
  returns `("dead", pid)` for a discussion-review worker? **A:** Surface a clear
  error and halt — no auto-re-fire. mill-start is always interactive with no
  `stuck_type`/autonomous machinery; the operator re-runs the discussion-review
  step. (mill-go, by contrast, has the `infrastructure` stuck + one-retry path.)
