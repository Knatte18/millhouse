# Batch: subprocess-bg-fixes

```yaml
task: '64 (A) -- Small infra fixes batch 9'
batch: subprocess-bg-fixes
number: 1
cards: 4
verify: python plugins/mill/unit_tests/test-subprocess-util.py && python plugins/mill/unit_tests/test-millpy-bg.py
depends-on: []
```

## Batch Scope

Two tightly related subprocess management fixes. Card 1 silences the unconditional
spawn/exit breadcrumbs in `_subprocess_util.run()`, emitting them only on failure.
Card 2 guarantees that `millpy-bg.py` always writes the `[mill-bg] EXIT` sentinel
even when `subprocess.run` raises an exception. Cards 3 and 4 add the corresponding
unit tests to the existing test files for each module.

## Cards

### Card 1: Buffer spawn message in `_subprocess_util.run()` — emit on failure only

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_subprocess_util.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Replace the unconditional `print(f"[subprocess] spawn argv={argv!r} timeout={timeout}", file=sys.stderr)` at line ~105 with a buffered variable:
  ```python
  _spawn_msg = f"[subprocess] spawn argv={argv!r} timeout={timeout}"
  ```
  Then apply the following conditional-emit pattern throughout `run()`:

  1. Wrap `proc = subprocess.Popen(argv, **popen_kwargs)` in a try/except. On any exception, emit `print(_spawn_msg, file=sys.stderr)` then `print(f"[subprocess] Popen raised: {exc!r}", file=sys.stderr)`, then re-raise.

  2. POSIX timeout branch (`except subprocess.TimeoutExpired`): before the existing `print(f"[subprocess] exit code=timeout duration=...")`, prepend `print(_spawn_msg, file=sys.stderr)`.

  3. Windows watchdog branch (`if os.name == "nt" and timeout is not None`): wrap the `_run_windows_watchdog(...)` call in a try/except for `subprocess.TimeoutExpired`; on catch, emit `print(_spawn_msg, file=sys.stderr)` then `print(f"[subprocess] exit code=timeout duration={time.monotonic() - start:.3f}s", file=sys.stderr)`, then re-raise.

  4. Replace the unconditional `print(f"[subprocess] exit code={proc.returncode} duration=...", file=sys.stderr)` (line ~163) with a conditional block: if `proc.returncode != 0`, emit both `_spawn_msg` and the exit line; if `proc.returncode == 0`, suppress both.

  The `popen_detached` function is NOT modified (it logs a single line per call, not a spawn+exit pair).
- **Commit:** `fix(subprocess): suppress spawn/exit logs on success, emit both on failure`

### Card 2: Add `exit_written` flag to `millpy-bg.py` worker — guarantee EXIT sentinel

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-bg.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In `_worker_main`, immediately before the `try:` block, add:
  ```python
  exit_written = False
  ```
  Inside the `with open(log_path, "w", ...) as log_f:` block, after `log_f.flush()` (the flush that follows the EXIT write), add:
  ```python
  exit_written = True
  ```
  In the outer `except Exception as exc:` branch, after writing the `[mill-bg] WORKER ERROR` line, add:
  ```python
  if not exit_written:
      try:
          with open(log_path, "a", encoding="utf-8") as _lf:
              _lf.write("[mill-bg] EXIT -1\n")
              _lf.flush()
      except Exception:
          pass
  ```
  The `return 1` at the end of the except block remains unchanged.
- **Commit:** `fix(millpy-bg): guarantee EXIT sentinel written even when subprocess.run raises`

### Card 3: Add success-silence and failure-emit tests to `test-subprocess-util.py`

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-subprocess-util.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Add two new test cases to the `main()` function, using letter labels that continue the existing sequence (next available after `m` is `n` and `o`):

  **(n) success -- no breadcrumbs:**
  ```python
  buf = io.StringIO()
  with contextlib.redirect_stderr(buf):
      run([sys.executable, "-c", "pass"])
  stderr_out = buf.getvalue()
  assert "[subprocess] spawn" not in stderr_out, f"spawn breadcrumb should be suppressed on success: {stderr_out!r}"
  assert "[subprocess] exit code=0" not in stderr_out, f"exit breadcrumb should be suppressed on success: {stderr_out!r}"
  print("PASS (n): success suppresses both spawn and exit breadcrumbs")
  ```

  **(o) non-zero exit -- both breadcrumbs present:**
  ```python
  buf = io.StringIO()
  with contextlib.redirect_stderr(buf):
      run([sys.executable, "-c", "import sys; sys.exit(7)"], check=False)
  stderr_out = buf.getvalue()
  assert "[subprocess] spawn argv=" in stderr_out, f"spawn breadcrumb missing on failure: {stderr_out!r}"
  assert "[subprocess] exit code=7" in stderr_out, f"exit breadcrumb missing on failure: {stderr_out!r}"
  print("PASS (o): non-zero exit emits both spawn and exit breadcrumbs")
  ```

  Wrap each test in a try/except AssertionError block appending to `failures`, consistent with the existing test style.
- **Commit:** `test(subprocess-util): add success-silence and failure-emit tests`

### Card 4: Add EXIT-on-raise test to `test-millpy-bg.py`

- **Context:**
  - `plugins/mill/scripts/millpy-bg.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-bg.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Add test **(o) worker FileNotFoundError writes EXIT -1** to the worker-mode section, after the existing test `(n)`:
  ```python
  # (o) worker raises FileNotFoundError -> EXIT -1 written in log
  try:
      with tempfile.TemporaryDirectory() as tmpdir:
          log_path = Path(tmpdir) / "test-raise.log"
          with unittest.mock.patch("subprocess.run", side_effect=FileNotFoundError("fake: no such file")):
              ret = _worker_main(["--log", str(log_path), "--", "fake-cmd"])
          assert ret == 1, f"expected 1, got {ret}"
          assert log_path.exists(), "log file not created"
          log_text = log_path.read_text(encoding="utf-8")
          assert "[mill-bg] EXIT -1" in log_text, f"'[mill-bg] EXIT -1' not in log: {log_text!r}"
      print("PASS (o): worker FileNotFoundError -> EXIT -1 written in log")
  except AssertionError as exc:
      failures.append(f"FAIL (o) worker-FileNotFoundError: {exc}")
  except Exception as exc:
      failures.append(f"FAIL (o) worker-FileNotFoundError ({type(exc).__name__}): {exc}")
  ```
  Note: `subprocess.run` inside `_worker_main` is the module-level `subprocess.run`, so the patch target is `"subprocess.run"` (not `"millpy_bg_worker.subprocess.run"` — the worker module already imported `subprocess` at load time; patch the canonical name the mock framework resolves to for the loaded module).
- **Commit:** `test(millpy-bg): add worker FileNotFoundError -> EXIT -1 assertion`

## Batch Tests

Cards 3 and 4 extend the two existing test files; the verify command runs both files directly:
`python plugins/mill/unit_tests/test-subprocess-util.py && python plugins/mill/unit_tests/test-millpy-bg.py`.
All existing tests in those files must continue to pass (no regressions).
