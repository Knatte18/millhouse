# Batch: bg-worker-liveness

```yaml
task: Wiki-daemon + bg-worker + test-suite robustness on Windows
batch: bg-worker-liveness
number: 2
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-bg-liveness.py
depends-on: []
```

## Batch Scope

Delivers the two `_bg.py` fixes (#393, #391-helper), both in one ~80-line module
tested by `test-bg-liveness.py`. #393 broadens the `os.kill` probe's `except` so
a chained Windows `SystemError` no longer escapes `is_bg_worker_alive`. #391
adds a new `wait_for_bg_terminal` helper that encapsulates the
"poll-until-EXIT-or-dead" loop with a race guard. The external interface
consumed by batch 3 (orchestrator-integration) is the new
`wait_for_bg_terminal(log_path, *, poll_interval) -> ("exit", code) | ("dead", pid)`
function — batch 3 only edits SKILL.md prose to call it, so it must land here
first (batch 3 `depends-on: [2]`).

## Cards

### Card 5: Broaden `is_bg_worker_alive` probe to catch `SystemError`

- **Context:**
  - `plugins/mill/unit_tests/test-bg-liveness.py`
- **Edits:**
  - `plugins/mill/scripts/_bg.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_bg.py`, change the `os.kill(pid, 0)` probe handler in
  `is_bg_worker_alive` (the `except OSError as exc:` at line 48) to
  `except (OSError, SystemError) as exc:` so a chained Windows `SystemError`
  ("<built-in function kill> returned a result with an exception set") is also
  caught and falls through to the existing log-mtime staleness fallback. Do not
  alter the `ProcessLookupError` / `PermissionError` branches above it, the
  debug-log line, or the mtime fallback. `KeyboardInterrupt` / `SystemExit` must
  still propagate (they subclass neither `OSError` nor `SystemError`). Keep the
  debug-log string ASCII.
- **Commit:** `fix(bg): catch chained SystemError in is_bg_worker_alive probe`

### Card 6: Add `wait_for_bg_terminal` poll helper

- **Context:**
  - `plugins/mill/scripts/millpy-bg.py`
- **Edits:**
  - `plugins/mill/scripts/_bg.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a new function
  `wait_for_bg_terminal(log_path: Path, *, poll_interval: float = 2.0) -> tuple[str, int | None]`
  to `_bg.py` that blocks until the bg worker reaches a terminal state and
  returns either `("exit", <exit_code>)` or `("dead", <pid>)`. Loop body, each
  iteration: (1) read the log; if it contains the `[mill-bg] EXIT <code>`
  sentinel (reuse the existing `_EXIT_RE`), parse the integer code and return
  `("exit", code)`. (2) Otherwise call `is_bg_worker_alive(log_path)`; if alive,
  `time.sleep(poll_interval)` and continue. (3) If `is_bg_worker_alive` reports
  dead (`alive is False`), perform the **race guard**: re-read the log once more
  and re-check for the EXIT sentinel — if EXIT is now present return
  `("exit", code)`, else return `("dead", pid)`. Use the module's existing
  `_EXIT_RE` for EXIT detection and a new local regex (or reuse `_EXIT_RE`'s
  capture) to extract the exit code integer; if the worker log is missing
  entirely treat it as dead (`("dead", None)`). All log reads use
  `read_text(encoding="utf-8", errors="replace")` like `is_bg_worker_alive`.
  Keep any added strings ASCII.
- **Commit:** `feat(bg): add wait_for_bg_terminal poll-until-exit-or-dead helper`

### Card 7: Tests for `SystemError` widening and `wait_for_bg_terminal`

- **Context:**
  - `plugins/mill/scripts/_bg.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-bg-liveness.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Extend `test-bg-liveness.py` (follow its existing
  `unittest.TestCase` style and `tempfile` log fixtures) with: (#393) patch
  `os.kill` to raise a chained `SystemError`, assert `is_bg_worker_alive` returns
  via the mtime fallback without propagating — fresh-mtime log → `(True, pid)`,
  stale-mtime log → `(False, pid)`; existing cases (EXIT present,
  `ProcessLookupError`, `PermissionError`, unknown `OSError`) must remain green.
  (#391 `wait_for_bg_terminal`) cases: (a) log already has `EXIT 0` →
  `("exit", 0)`; (b) worker alive then EXIT appears on a later poll → `("exit",
  code)` (patch `is_bg_worker_alive` and/or rewrite the log between polls; patch
  `_bg.time.sleep` so the test does not really sleep); (c) probe reports dead and
  re-read still has no EXIT → `("dead", pid)`; (d) **race guard** — probe reports
  dead but the re-read now shows `EXIT 0` → `("exit", 0)`, NOT dead; (e) missing
  log file → `("dead", None)`. Patch liveness/log reads; spawn no real
  processes.
- **Commit:** `test(bg): cover SystemError widening and wait_for_bg_terminal`

## Batch Tests

`verify` runs `test-bg-liveness.py` via `run-all.py --only`. Card 7 adds the new
cases for both fixes; the existing `is_bg_worker_alive` cases must stay green,
proving the `except` widening did not change the normal-path behavior. All
`os.kill`, log content, and `time.sleep` interactions are patched — no real
process is spawned or killed.
