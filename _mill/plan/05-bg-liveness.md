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
- **Requirements:** Create `plugins/mill/scripts/_bg.py` exposing one public function `is_bg_worker_alive(log_path: Path) -> tuple[bool, int | None]`. The module's top-level docstring states the purpose ("Liveness probe for millpy-bg worker subprocesses; used by orchestrators after resume to decide whether to wait or re-fire."). Imports: `os`, `re`, `errno`, `time`, `pathlib.Path` -- stdlib only.

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
      except OSError as exc:
          if exc.errno == errno.EPERM:
              return (True, pid)
          if exc.errno == errno.ESRCH:
              return (False, pid)
          # Inconclusive (Windows specific or transient). Fall through to mtime fallback.
      mtime = log_path.stat().st_mtime
      if (time.time() - mtime) > _STALE_LOG_SECONDS:
          return (False, pid)
      return (True, pid)
  ```

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
- **Requirements:** Create a `unittest.TestCase` test file with four cases, each writing a synthetic log file into a `tempfile.TemporaryDirectory()` and calling `_bg.is_bg_worker_alive(log_path)`:

  1. `test_log_missing` -- log_path points to a file that does not exist. Expect `(False, None)`.
  2. `test_log_no_pid_line` -- write a log file containing only `some unrelated text\n` (no WORKER PID line). Expect `(False, None)`.
  3. `test_log_with_exit` -- write a log containing `[mill-bg] WORKER PID=12345 START 2026-05-17T15:00:00Z\nsome output\n[mill-bg] EXIT 0\n`. Expect `(False, 12345)`. The PID need not be valid because the EXIT line short-circuits the probe.
  4. `test_log_live_pid` -- write a log containing `[mill-bg] WORKER PID={os.getpid()} START 2026-05-17T15:00:00Z\nsome output\n` (no EXIT line). Use `os.getpid()` -- the test's own PID is guaranteed live. Expect `(True, os.getpid())`.
  5. `test_log_dead_pid_no_exit` -- write a log containing `[mill-bg] WORKER PID=99999999 START 2026-05-17T15:00:00Z\nsome output\n` (no EXIT line). PID 99999999 is almost certainly invalid on any modern OS. Expect `(False, 99999999)`. (If the test machine happens to have that PID assigned the test would false-fail; this is acceptable since the probability is negligible. Document the caveat in a one-line comment above the test method.)

  Do NOT test the mtime-fallback Windows path -- exercising it requires either a real Windows-only condition or backdating a file's mtime, which is platform-specific and brittle. The Card 14 implementation guarantees the fallback is defensive (returns `(True, pid)` for fresh logs even if the kill probe is inconclusive); manual operator observation will catch regressions there.

  Standalone-runnable (`python plugins/mill/unit_tests/test-bg-liveness.py`) and via `run-all.py`.
- **Commit:** `test(bg): cover is_bg_worker_alive across five log/probe cases`

## Batch Tests

`verify:` runs `test-bg-liveness.py`. The five cases cover the entire decision matrix except the Windows-only mtime fallback (intentionally excluded -- see Card 15 Requirements). No other test file is affected.
