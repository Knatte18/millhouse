# Batch: bg-heartbeat-diagnosability

```yaml
task: 'millpy-implement/fix.py: stuck-type false positives and session-hygiene gaps'
batch: bg-heartbeat-diagnosability
number: 5
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-bg.py
depends-on: []
```

## Batch Scope

Fixes #955: a `millpy-implement.py --stage baseline` worker backgrounded via `millpy-bg.py` (mill-go's Step 0.5 baseline pre-flight) can die (`_bg.check_bg_status` reports `"dead"`) leaving a log with only the `[mill-bg] WORKER PID=... START` line — no `WORKER ERROR`, no `EXIT`, no diagnostic of any kind. `_worker_main`'s own `except`/`finally` handlers already cover a normal exit or an in-process exception; the observed failure means the process was killed hard enough (SIGKILL/TerminateProcess) that neither ever ran, which the module's own docstring already documents as inherently unrecoverable in-process. This batch adds a heartbeat thread that appends a timestamped line to the log every 30 seconds while the inner subprocess runs, so a hard-killed worker's log at least shows the last live timestamp before the gap, narrowing the diagnostic window without claiming to catch the unrecoverable case. Independent of batches 1-4 (different file, no shared code path) — a root batch.

## Cards

### Card 12: `millpy-bg.py` — heartbeat thread in `_worker_main`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-bg.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In the worker fast-path section (the `if "--_worker" in sys.argv:` block, which is deliberately stdlib-only — no mill imports), add `import threading` alongside the existing `import os`, `import subprocess`, `from datetime import datetime, timezone` block. Add a module-level constant `_HEARTBEAT_INTERVAL_S = 30` immediately after those imports (kept as a distinct named constant, not an inline literal, so a test can override it via `unittest.mock.patch.object`).

  `_worker_main`'s body currently reads:
  ```python
      exit_code = -1
      try:
          with open(log_path, "w", encoding="utf-8", buffering=1) as log_f:
              log_f.write(
                  f"[mill-bg] WORKER PID={os.getpid()} START "
                  f"{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}\n"
              )
              result = subprocess.run(
                  cmd,
                  stdout=log_f,
                  stderr=subprocess.STDOUT,
                  creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
              )
              exit_code = result.returncode
          return 0
  ```
  Replace it with a version that starts a heartbeat thread immediately after the START line is written (still inside the `with` block, so the thread writes through the same open `log_f` handle — it must never open a second handle on `log_path`), and stops/joins that thread immediately after `subprocess.run()` returns, still inside the `with` block (before its dedent) — never in the `finally` block below, which opens its own independent `"a"`-mode handle for the `[mill-bg] EXIT` write and runs strictly after the `with` block has already closed `log_f`:
  ```python
      exit_code = -1
      try:
          with open(log_path, "w", encoding="utf-8", buffering=1) as log_f:
              log_f.write(
                  f"[mill-bg] WORKER PID={os.getpid()} START "
                  f"{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}\n"
              )
              _heartbeat_stop = threading.Event()

              def _heartbeat() -> None:
                  while not _heartbeat_stop.wait(_HEARTBEAT_INTERVAL_S):
                      try:
                          log_f.write(
                              f"[mill-bg] HEARTBEAT "
                              f"{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}\n"
                          )
                      except Exception:
                          return

              _heartbeat_thread = threading.Thread(target=_heartbeat, daemon=True)
              _heartbeat_thread.start()
              try:
                  result = subprocess.run(
                      cmd,
                      stdout=log_f,
                      stderr=subprocess.STDOUT,
                      creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                  )
                  exit_code = result.returncode
              finally:
                  _heartbeat_stop.set()
                  _heartbeat_thread.join()
          return 0
  ```
  The inner `try`/`finally` around `subprocess.run` ensures the heartbeat thread is always stopped and joined even when `subprocess.run` itself raises (propagating to the existing outer `except Exception as exc:` handler unchanged) — the thread must never be left running past the `with` block's exit under any path. `daemon=True` is a defense-in-depth backstop only (the explicit `join()` above already guarantees the thread has stopped before the `with` block dedents); it must not be relied upon as the primary stop mechanism. The heartbeat's own per-write `try/except Exception: return` guards against a write racing the (still-open, still-owned-by-this-thread) handle during shutdown — matching this worker's existing best-effort-diagnostic posture, never raising into the main thread.
- **Commit:** `fix(bg): add heartbeat thread to worker log for post-mortem diagnosability`

### Card 13: tests — heartbeat presence, single handle, and clean join

- **Context:**
  - `plugins/mill/scripts/millpy-bg.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-bg.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add three new test cases to `plugins/mill/unit_tests/test-millpy-bg.py`, following this file's existing pattern of calling `_worker_main([...])` directly against a temp log path and asserting on the log's contents (see the existing `[mill-bg] EXIT 0`/`EXIT 3`/`EXIT -1` cases for the established fixture shape):
  1. Patch `_worker_mod._HEARTBEAT_INTERVAL_S` to a short value (e.g. `0.05`) via `unittest.mock.patch.object`, then call `_worker_main` with a command that runs long enough for at least one interval to elapse (e.g. `[sys.executable, "-c", "import time; time.sleep(0.2)"]`). Assert the resulting log text contains at least one line matching `[mill-bg] HEARTBEAT <ISO-8601 timestamp>` before the `[mill-bg] EXIT 0` line, and that the run still ends with `[mill-bg] EXIT 0` (the existing sentinel contract is unaffected).
  2. Same patched-interval setup as case 1. Patch `builtins.open` with `unittest.mock.patch("builtins.open", wraps=open)` and, after the `_worker_main` call completes, assert the mock was called with `log_path` as its first positional argument exactly twice: once for the `"w"`-mode open inside the `with` block, once for the `"a"`-mode open inside the existing `finally` block's `[mill-bg] EXIT` write — never a third time for the heartbeat thread, proving it writes through the already-open handle rather than opening its own.
  3. Same patched-interval setup as case 1. Install a `threading.excepthook` override before the call (save and restore the prior hook in a `try`/`finally`) that appends any received exception info to a list. After the `_worker_main` call completes, assert that list is empty — no exception escaped the heartbeat thread (e.g. a `ValueError: I/O operation on closed file` from a write racing the handle's closure), guarding specifically against a future edit that moves the stop/join back into the `finally` block instead of immediately after `subprocess.run()` returns.
- **Commit:** `test(bg): cover heartbeat presence, single log handle, and clean thread join`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/test-millpy-bg.py` directly, covering every case this batch adds plus the file's existing regression suite for both the worker and launcher paths.
