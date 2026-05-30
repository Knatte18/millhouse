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
adds a new `check_bg_status` helper — a **single-shot, non-blocking** status
probe (it returns immediately; it does NOT loop or sleep) with a one-time
re-read race guard. It is single-shot by design: the orchestrator keeps its
existing incremental `cat` poll loop and calls this helper once per iteration,
so no call ever blocks past the Bash 600s cap on a normal-length workload. The
external interface consumed by batch 3 (orchestrator-integration) is the new
`check_bg_status(log_path) -> tuple[str, int | None]` function, where the first
element is `"exit"` / `"running"` / `"dead"` and the second is the exit code
(for `"exit"`) or the worker pid (for `"running"` / `"dead"`, or `None` if the
log is missing). Batch 3 only edits SKILL.md prose to call it, so it must land
here first (batch 3 `depends-on: [2]`).

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

### Card 6: Add `check_bg_status` single-shot status helper

- **Context:**
  - `plugins/mill/scripts/millpy-bg.py`
- **Edits:**
  - `plugins/mill/scripts/_bg.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a new **single-shot, non-blocking** function
  `check_bg_status(log_path: Path) -> tuple[str, int | None]` to `_bg.py`. It
  must NOT loop or sleep — it performs exactly one status determination and
  returns immediately (the orchestrator owns the poll cadence). Logic: (1) read
  the log; if it contains the `[mill-bg] EXIT <code>` sentinel, parse the
  integer code with a new module-level regex `_EXIT_CODE_RE =
  re.compile(r"\[mill-bg\] EXIT (\d+)")` (do NOT reuse `_EXIT_RE`, which has no
  capture group; leave `_EXIT_RE` unchanged) and return `("exit", code)`. (2)
  Else call `is_bg_worker_alive(log_path)`; if it reports alive, return
  `("running", pid)`. (3) If it reports dead (`alive is False`), perform the
  **race guard**: re-read the log once more and re-check for the EXIT sentinel —
  if EXIT is now present return `("exit", code)`, else return `("dead", pid)`.
  If the log file is missing entirely, return `("dead", None)`. All log reads
  use `read_text(encoding="utf-8", errors="replace")` like `is_bg_worker_alive`.
  Keep any added strings ASCII.
- **Commit:** `feat(bg): add check_bg_status single-shot worker status helper`

### Card 7: Tests for `SystemError` widening and `check_bg_status`

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
  (#391 `check_bg_status`) cases — each is a single call (no sleeping, no
  looping): (a) log has `[mill-bg] EXIT 0` → `("exit", 0)`; (b) log has a WORKER
  PID line, no EXIT, `is_bg_worker_alive` patched to report alive →
  `("running", pid)`; (c) no EXIT, `is_bg_worker_alive` patched to report dead,
  re-read still has no EXIT → `("dead", pid)`; (d) **race guard** —
  `is_bg_worker_alive` patched to report dead but the log content swapped so the
  re-read now shows `[mill-bg] EXIT 0` → `("exit", 0)`, NOT dead (drive the
  swap by patching `Path.read_text` / the log read to return no-EXIT then
  with-EXIT on successive calls); (e) missing log file → `("dead", None)`. Patch
  liveness/log reads; spawn no real processes.
- **Commit:** `test(bg): cover SystemError widening and check_bg_status`

## Batch Tests

`verify` runs `test-bg-liveness.py` via `run-all.py --only`. Card 7 adds the new
cases for both fixes; the existing `is_bg_worker_alive` cases must stay green,
proving the `except` widening did not change the normal-path behavior. All
`os.kill`, log content, and `time.sleep` interactions are patched — no real
process is spawned or killed.
