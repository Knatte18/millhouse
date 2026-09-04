# Batch: bg-liveness-windows-probe

```yaml
task: 'millpy-implement/bg: Windows baseline-worktree teardown (WinError 145) and stale liveness reporting'
batch: bg-liveness-windows-probe
number: 3
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-bg-liveness.py
depends-on: []
```

## Batch Scope

`_bg._probe_liveness` uses `os.kill(pid, 0)` as a liveness probe. On Windows, CPython's `os.kill`
implementation does not special-case signal `0` — it calls `OpenProcess` + `TerminateProcess(handle,
sig)` for any non-`CTRL_C_EVENT`/`CTRL_BREAK_EVENT` signal, so `os.kill(pid, 0)` actually **kills**
the probed process (exit code 0) rather than checking it. `_probe_liveness` then reads "no exception
raised" as `"affirmative-alive"`, when it just terminated the process it meant to check. This is the
confirmed root cause of GitHub issues #940/#959 (a live `millpy-bg` worker reported `"dead"` while
its own detached child subprocess — unrelated by any Windows Job Object, per
`_subprocess_util.popen_detached` — kept running and finishing normally). This batch adds a
non-destructive, `ctypes`-based Windows liveness probe used only on `sys.platform == "win32"`; the
POSIX `os.kill(pid, 0)` path is untouched.

## Cards

### Card 5: Non-destructive Windows liveness probe in `_bg.py`

- **Context:**
  - `plugins/mill/scripts/_vscode_processes.py`
- **Edits:**
  - `plugins/mill/scripts/_bg.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add `import sys` to `_bg.py`'s existing import block (it currently imports `json`, `logging`,
  `os`, `re`, `time` but not `sys`), keeping alphabetical stdlib-import ordering.

  Add a new function `_win_pid_alive(pid: int) -> bool | None`, placed immediately before
  `_probe_liveness` in `_bg.py`. Keep its `ctypes.windll.kernel32` usage style consistent with the
  existing precedent in `_vscode_processes.py`'s `_probe_windows()` (same `ctypes`/`ctypes.wintypes`
  import-inside-function pattern, same `PROCESS_QUERY_LIMITED_INFORMATION = 0x1000` constant
  naming, same `False` literal for a Win32 `BOOL` parameter). Implementation: import `ctypes` and
  `ctypes.wintypes` inside the function (matching `_vscode_processes.py`'s own inside-function
  import placement, since these are Windows-only stdlib modules). Call
  `ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)`. If the
  returned handle is falsy (`OpenProcess` failed): call `ctypes.windll.kernel32.GetLastError()`; if
  it equals `5` (`ERROR_ACCESS_DENIED`), return `True` (the process exists but the query was denied
  — direct port of `_probe_liveness`'s existing POSIX `PermissionError` -> `"affirmative-alive"`
  branch, not a new decision axis); otherwise return `False` (process does not exist — most commonly
  `ERROR_INVALID_PARAMETER`, code `87`, for a PID that no longer exists). If the handle is truthy:
  wrap in `try`/`finally` so the handle is always closed via
  `ctypes.windll.kernel32.CloseHandle(hproc)`; inside the `try`, declare `exit_code =
  ctypes.wintypes.DWORD()` and call
  `ctypes.windll.kernel32.GetExitCodeProcess(hproc, ctypes.byref(exit_code))`; if that call itself
  returns falsy (query failed despite a valid handle), return `None` (inconclusive — the caller falls
  back to log-mtime staleness, mirroring the existing `except (OSError, SystemError):` fall-through
  for the POSIX path); otherwise return `exit_code.value == 259` (`259` is the Win32 `STILL_ACTIVE`
  sentinel — name it as a local constant `STILL_ACTIVE = 259` rather than a bare literal). Give the
  function a one-paragraph docstring stating it never sends a signal or terminates the probed
  process, unlike `os.kill(pid, 0)` on Windows, and that it returns `True` (running), `False`
  (confirmed exited or does not exist), or `None` (inconclusive — caller falls back to log-mtime
  staleness).

  In `_probe_liveness`, replace the existing:
  ```python
    try:
        os.kill(pid, 0)
        return ("affirmative-alive", pid)
    except ProcessLookupError:
        return ("dead", pid)
    except PermissionError:
        return ("affirmative-alive", pid)
    except (OSError, SystemError) as exc:
        # Unknown errno from os.kill (Windows-specific or transient) -- fall through to mtime fallback.
        _logger.debug("_probe_liveness: os.kill(%s, 0) raised %r -- falling back to log-mtime staleness", pid, exc)
        pass
  ```
  with a platform branch: when `sys.platform == "win32"`, call `_win_pid_alive(pid)` and return
  `("affirmative-alive", pid)` when it returns `True`, `("dead", pid)` when it returns `False`, and
  fall through to the existing mtime-staleness check below (log via `_logger.debug` with a message
  analogous to the existing one, e.g. `"_probe_liveness: _win_pid_alive(%s) was inconclusive --
  falling back to log-mtime staleness"`) when it returns `None`. When `sys.platform != "win32"`, keep
  the existing `try: os.kill(pid, 0) ... except ...` block exactly as it is today, byte-for-byte
  (including its docstring/comment), under an `else:` branch. Do not change `_probe_liveness`'s
  signature, its `_PID_RE`/`_EXIT_RE` handling above this block, or the mtime-staleness check below
  it — this card touches only the liveness-check branch itself.

  Update `_probe_liveness`'s docstring (`"Probes the PID via os.kill(pid, 0) with fallback to log
  mtime staleness."`) to note the platform split: `os.kill(pid, 0)` on POSIX, `_win_pid_alive` on
  Windows.
- **Commit:** `fix(bg): replace destructive os.kill(pid, 0) probe with a non-destructive Windows check`

### Card 6: Unit tests for `_win_pid_alive` and the platform-gated probe

- **Context:**
  - `plugins/mill/scripts/_bg.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-bg-liveness.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add new test cases to `test-bg-liveness.py`, following this file's existing
  `unittest.TestCase`/`unittest.mock` style (matching e.g. `test_log_with_exit`'s fixture shape: a
  `tempfile.TemporaryDirectory()` with a hand-written `[mill-bg] WORKER PID=...` log file).

  **Mocking mechanism (mandatory — read before writing any case below).** Card 5's `_win_pid_alive`
  does `import ctypes` and `import ctypes.wintypes` **inside its own function body** (matching
  `_vscode_processes.py`'s existing inside-function-import convention). This means `patch("_bg.ctypes...
  ")`/`patch("ctypes.windll...")`-style attribute patching CANNOT work here: `_bg` has no
  module-level `ctypes` name to patch (the import is local to the function, re-executed on every
  call), and on this Linux test host `ctypes.windll` does not exist as a real attribute at all — it
  is conditionally defined only under `if sys.platform.startswith("win")` inside `ctypes/__init__.py`
  itself, so any `patch()` call whose target string tries to resolve through `ctypes.windll` raises
  `AttributeError` before a mock is ever installed, regardless of where `ctypes` is imported.

  Instead, install fake modules into `sys.modules` before calling `_win_pid_alive` — because the
  `import` statements are function-local, they re-resolve against `sys.modules` on every call, so
  `unittest.mock.patch.dict(sys.modules, {...})` swaps what those `import` statements bind to for
  the duration of the `with` block:
  ```python
  import types
  import unittest.mock

  def _make_fake_ctypes(kernel32):
      fake_windll = types.SimpleNamespace(kernel32=kernel32)
      fake_ctypes = types.ModuleType("ctypes")
      fake_ctypes.windll = fake_windll
      fake_ctypes.byref = lambda x: x  # identity: pass the DWORD object straight through
      fake_wintypes = types.ModuleType("ctypes.wintypes")

      class _FakeDWORD:
          def __init__(self):
              self.value = 0

      fake_wintypes.DWORD = _FakeDWORD
      fake_ctypes.wintypes = fake_wintypes  # set explicitly; do not rely on import-machinery auto-set for a synthetic module
      return fake_ctypes, fake_wintypes
  ```
  Each case below wraps its call to `_bg._win_pid_alive(1234)` in:
  ```python
  kernel32 = unittest.mock.MagicMock()
  # ... configure kernel32.OpenProcess / .GetExitCodeProcess / .GetLastError / .CloseHandle here ...
  fake_ctypes, fake_wintypes = _make_fake_ctypes(kernel32)
  with unittest.mock.patch.dict(
      sys.modules, {"ctypes": fake_ctypes, "ctypes.wintypes": fake_wintypes}
  ):
      result = _bg._win_pid_alive(1234)
  ```
  (place `_make_fake_ctypes` as a module-level helper in the test file, or a `staticmethod`/local
  helper on the test class — match whichever this file's existing convention prefers for shared
  fixture helpers.)

  New test class `TestWinPidAlive` (or new methods on the existing `TestBgLiveness` class — match
  whichever grouping convention the rest of this file already uses for helper-function-level tests
  as opposed to `is_bg_worker_alive`-level tests), using the mocking mechanism above for every case:
  1. `kernel32.OpenProcess.return_value = 12345` (nonzero handle) and
     `kernel32.GetExitCodeProcess.side_effect = <callable that sets its 2nd positional arg's
     `.value` to `259` (STILL_ACTIVE) and returns 1>` — assert `_bg._win_pid_alive(1234)` returns
     `True`. Because `fake_ctypes.byref` is the identity function above, the `exit_code` `_FakeDWORD`
     instance itself is passed as `GetExitCodeProcess`'s 2nd positional argument, so the side_effect
     callable can mutate `args[1].value` directly.
  2. Same `OpenProcess` mock, but the `GetExitCodeProcess` side_effect sets `.value` to a non-`259`
     value (e.g. `0`) and returns `1` — assert `_bg._win_pid_alive(1234)` returns `False`.
  3. `kernel32.OpenProcess.return_value = 0` (falsy) and `kernel32.GetLastError.return_value = 5`
     (`ERROR_ACCESS_DENIED`) — assert `_bg._win_pid_alive(1234)` returns `True`.
  4. `kernel32.OpenProcess.return_value = 0` and `kernel32.GetLastError.return_value = 87`
     (`ERROR_INVALID_PARAMETER`) — assert `_bg._win_pid_alive(1234)` returns `False`.
  5. `kernel32.OpenProcess.return_value = 12345` and `kernel32.GetExitCodeProcess.return_value = 0`
     (falsy — the call itself failed) — assert `_bg._win_pid_alive(1234)` returns `None`.
  6. Assert `kernel32.CloseHandle` is called exactly once in every one of cases 1, 2, and 5 above (the
     handle is always closed when `OpenProcess` succeeded), and never called in cases 3/4 (no handle
     was ever opened).

  New test(s) for the platform-gated branch in `_probe_liveness`: patch `_bg.sys.platform = "win32"`
  (via `unittest.mock.patch.object(_bg.sys, "platform", "win32")` or equivalent) together with a
  patched `_bg._win_pid_alive` returning `True`/`False`/`None` in turn, and assert
  `_bg._probe_liveness(log_path)` (given a log file with a `WORKER PID=...` line and no `EXIT` line)
  returns `("affirmative-alive", pid)`, `("dead", pid)`, and falls through to the existing
  mtime-staleness check (i.e. `"assumed-alive"` for a fresh log, `"dead"` for a stale one — reuse
  this file's existing mtime-staleness test fixtures/helpers) respectively. Also add a regression
  test confirming that when `_bg.sys.platform` is patched to a non-`"win32"` value (e.g. `"linux"`),
  `_probe_liveness` still calls `os.kill` (patch `_bg.os.kill`) and never calls `_win_pid_alive` —
  confirming the POSIX path is genuinely untouched by this batch.
- **Commit:** `test(bg): cover the Windows-native liveness probe and platform gate`

## Batch Tests

`verify:` runs `test-bg-liveness.py` directly (single file, matches this batch's sole edited
module). Card 6's new cases exercise both `_win_pid_alive` in isolation (via mocked
`ctypes.windll.kernel32` calls — no real Windows process, no real `ctypes.windll` access, which does
not even exist on this Linux dev host) and `_probe_liveness`'s platform-gated branch (via patched
`sys.platform` and `_win_pid_alive`), plus a regression test that the untouched POSIX path still
calls `os.kill`.
