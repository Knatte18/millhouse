# Batch: bg-liveness

```yaml
task: '66 (A) -- Review sandbox follow-up: guard exceptions + bare-exit + sandbox argv'
batch: bg-liveness
number: 5
cards: 2
verify: python plugins/mill/unit_tests/test-bg-liveness.py
depends-on: []
```

## Batch Scope

Introduce `plugins/mill/scripts/_bg.py`, a tiny stdlib-only helper module that exposes a single public function `is_bg_worker_alive(log_path)`. The function parses the millpy-bg worker log header for `[mill-bg] WORKER PID=N START ...`, checks for the `[mill-bg] EXIT` sentinel, and probes the PID's liveness via `os.kill(pid, 0)`. Returns `(alive, pid_or_None)` so callers (mill-go's Holistic step 1 in batch 6, plus any future caller) can decide whether to wait on a live worker or re-fire a dead one.

External interface: a single new module with one function. Stdlib only -- no new dependencies. Batch 6 imports `_bg.is_bg_worker_alive` from this module; no other current caller depends on it (mill-cleanup and mill-status are future-eligible callers but not in scope for this task).

## Cards

### Card 14: create `_bg.is_bg_worker_alive` and its module

- **Context:**
  - `plugins/mill/scripts/millpy-bg.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/_bg.py`
- **Deletes:** none
- **Requirements:** Create `plugins/mill/scripts/_bg.py` exposing one public function `is_bg_worker_alive(log_path: Path) -> tuple[bool, int | None]`. The module's top-level docstring states the purpose ("Liveness probe for millpy-bg worker subprocesses; used by orchestrators after resume to decide whether to wait or re-fire."). Imports: `os`, `re`, `time`, `pathlib.Path` -- stdlib only.

  Behaviour matrix:

  | log state                                            | os.kill result                          | return                |
  | ---------------------------------------------------- | --------------------------------------- | --------------------- |
  | log file does not exist                              | (not probed)                            | `(False, None)`       |
  | log exists, no `WORKER PID=N START` line             | (not probed)                            | `(False, None)`       |
  | log has WORKER PID line AND has `[mill-bg] EXIT`     | (not probed)                            | `(False, pid)`        |
  | log has WORKER PID line, no EXIT, kill raises ESRCH  | (probed, dead)                          | `(False, pid)`        |
  | log has WORKER PID line, no EXIT, kill raises EPERM  | (probed, alive but owned by other user) | `(True, pid)`         |
  | log has WORKER PID line, no EXIT, kill returns       | (probed, alive)                         | `(True, pid)`         |
  | log has WORKER PID line, no EXIT, log mtime > 5 min  | (probe inconclusive on Windows fallback)| `(False, pid)`        |

  Implementation outline:
  ```python
  _PID_RE = re.compile(r"\[mill-bg\] WORKER PID=(\d+) START")
  _EXIT_RE = re.compile(r"\[mill-bg\] EXIT \d+")
  _STALE_LOG_SECONDS = 5 * 60

  def is_bg_worker_alive(log_path: Path) -> tuple[bool, int | None]:
      if not log_path.exists():
          return (False, None)
      text = log_path.read_text(encoding="utf-8", errors="replace")
      m = _PID_RE.search(text)
      if not m:
          return (False, None)
      pid = int(m.group(1))
      if _EXIT_RE.search(text):
          return (False, pid)
      try:
          os.kill(pid, 0)
          return (True, pid)
      except ProcessLookupError:
          return (False, pid)
      except PermissionError:
          return (True, pid)
      except OSError:
          # Unknown errno from os.kill (Windows-specific or transient) -- fall through to mtime fallback.
          pass
      mtime = log_path.stat().st_mtime
      if (time.time() - mtime) > _STALE_LOG_SECONDS:
          return (False, pid)
      return (True, pid)
  ```

  The `except OSError` block intentionally contains no errno-specific branches: Python 3.3+ promotes `OSError(errno=ESRCH)` to `ProcessLookupError` and `OSError(errno=EPERM/EACCES)` to `PermissionError`, so the typed `except` clauses above already exhaust those cases. The remaining `except OSError` catches the residual Windows-specific errnos (e.g. `EINVAL=22` for out-of-range PIDs returned by `OpenProcess(ERROR_INVALID_PARAMETER=87)`) and routes them to the mtime fallback. Since no branch references `errno.E*`, do NOT import `errno` in the module.

  Constants `_PID_RE`, `_EXIT_RE`, `_STALE_LOG_SECONDS` are module-private (underscore prefix). The function's docstring documents the full behaviour matrix exactly as the table above (use a tab-aligned text representation, not a literal markdown table). Do NOT add any other public functions or constants to this module -- one function, one purpose.
- **Commit:** `feat(bg): add _bg.is_bg_worker_alive PID-liveness helper`

### Card 15: unit test for `is_bg_worker_alive` against synthetic log fixtures

- **Context:**
  - `plugins/mill/scripts/_bg.py`
  - `plugins/mill/unit_tests/_test_helpers.py`
  - `plugins/mill/unit_tests/run-all.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-bg-liveness.py`
- **Deletes:** none
- **Requirements:** Create a `unittest.TestCase` test file with six cases, each writing a synthetic log file into a `tempfile.TemporaryDirectory()` and calling `_bg.is_bg_worker_alive(log_path)`:

  1. `test_log_missing` -- log_path points to a file that does not exist. Expect `(False, None)`.
  2. `test_log_no_pid_line` -- write a log file containing only `some unrelated text\n` (no WORKER PID line). Expect `(False, None)`.
  3. `test_log_with_exit` -- write a log containing `[mill-bg] WORKER PID=12345 START 2026-05-17T15:00:00Z\nsome output\n[mill-bg] EXIT 0\n`. Expect `(False, 12345)`. The PID need not be valid because the EXIT line short-circuits the probe.
  4. `test_log_live_pid` -- write a log containing `[mill-bg] WORKER PID={os.getpid()} START 2026-05-17T15:00:00Z\nsome output\n` (no EXIT line). Use `os.getpid()` -- the test's own PID is guaranteed live. Expect `(True, os.getpid())`.
  5. `test_log_dead_pid_no_exit` -- write a log containing `[mill-bg] WORKER PID=99999999 START 2026-05-17T15:00:00Z\nsome output\n` (no EXIT line). PID 99999999 is almost certainly invalid on any modern OS. **Backdate the log mtime via `os.utime(log_path, (old_ts, old_ts))` where `old_ts = time.time() - (_STALE_LOG_SECONDS + 60)`** so the function exercises the mtime fallback consistently on every platform. On Linux/macOS the `os.kill(99999999, 0)` probe raises `ProcessLookupError` and the test returns `(False, 99999999)` via the typed-except path -- the backdated mtime is irrelevant on that platform. On Windows the probe raises `OSError(errno=EINVAL=22)` (`OpenProcess(ERROR_INVALID_PARAMETER=87)` for out-of-range PIDs); the bare `except OSError` falls through to the mtime check, the backdated mtime triggers the staleness branch, and the test returns `(False, 99999999)`. Expect `(False, 99999999)` on both platforms. (Document in a one-line comment above the test method that PID 99999999 is assumed invalid; on the unlikely chance the test machine has it allocated the test would false-fail.)

  Add a sixth case `test_log_live_pid_with_stale_mtime` -- write a log with `[mill-bg] WORKER PID={os.getpid()} START ...`, no EXIT, and backdate the mtime by `_STALE_LOG_SECONDS + 60` seconds. Expect `(True, os.getpid())`: the kill probe succeeds (PID is live), so the function returns from the `try` block BEFORE reaching the mtime fallback. This guards against a regression where the mtime check is mistakenly placed inside the try-block instead of after it.

  Do not write a separate Windows-only test for the EINVAL → mtime path; case 5 above already covers that platform-specific branch via the backdated mtime, and case 6 verifies the live-PID path is not mtime-gated.

  Standalone-runnable (`python plugins/mill/unit_tests/test-bg-liveness.py`) and via `run-all.py`.
- **Commit:** `test(bg): cover is_bg_worker_alive across five log/probe cases`

## Batch Tests

`verify:` runs `test-bg-liveness.py`. The six cases cover the entire decision matrix: missing log, missing PID line, log with EXIT, live PID via the typed-except path, dead PID via the mtime fallback (case 5 -- portable across Linux/macOS/Windows by backdating mtime so the EINVAL-fall-through on Windows still resolves to `(False, pid)`), and live PID with stale mtime (regression guard that the mtime check is not inside the try-block). No other test file is affected.
