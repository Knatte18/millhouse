# Batch: driver

```yaml
task: Wrap claude -p via psmux to use subscription instead of API credits
batch: driver
number: 2
cards: 3
verify: python plugins/mill/unit_tests/test-psmux-driver.py
depends-on: []
```

## Batch Scope

This batch delivers the thin psmux subprocess shim
`_psmux.py` (one Python function per psmux command the wrapper uses) plus
its mock-based unit tests. The driver is a pure subprocess wrapper -- it
calls `psmux <subcommand> ...` via `_subprocess_util.run`, raises
`PsmuxError` on non-zero exit (with two documented exceptions: idempotent
teardown for `kill_session`, fallback for `set_history_limit`), and
returns parsed text where applicable. The driver has no dependency on
the parser (batch 01) and can build in parallel with it.

**External interface for batch 03:** the eight functions
`new_session`, `set_history_limit`, `send_keys`, `load_buffer`,
`paste_buffer`, `capture_pane`, `kill_session`, `list_sessions`, plus
the `PsmuxError` exception class. No other public symbols.

**Batch-local decisions:**
- Tests use `unittest.mock.patch` against `_subprocess_util.run` to
  assert the constructed argv and timeout. No real psmux binary
  required for unit tests.
- `set_history_limit` swallows `PsmuxError` and writes a documented
  fallback message; this is the only function whose tests exercise both
  the success and exception paths.
- `kill_session` ignores "no such session" (idempotent teardown);
  every other non-zero exit raises `PsmuxError`.


## Cards

### Card 5: driver skeleton, exception, constants

- **Context:**
  - `_mill/discussion.md`
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/scripts/_llm_claude.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/_psmux.py`
- **Deletes:** none
- **Requirements:** Module docstring stating this is the psmux subprocess
  driver shim used by `millpy-claude-sub.py`. Top-level constant
  `PSMUX_COMMAND_TIMEOUT_S = 30`. Define `class PsmuxError(Exception)`
  with one-line docstring. Define eight stub functions with the exact
  signatures below; each body raises `NotImplementedError("implemented
  in card 7")`:
  - `def new_session(name: str, *, cols: int = 200, rows: int = 50, shell_argv: list[str]) -> None`
  - `def set_history_limit(name: str, limit: int) -> None`
  - `def send_keys(name: str, keys: str, *, enter: bool = False) -> None`
  - `def load_buffer(name: str, buffer_name: str, file_path: "Path") -> None`
  - `def paste_buffer(name: str, buffer_name: str) -> None`
  - `def capture_pane(name: str, *, scrollback: int = 50000) -> str`
  - `def kill_session(name: str) -> None`
  - `def list_sessions() -> list[str]`
  Use `from pathlib import Path` and the standard `from __future__ import
  annotations` import. ASCII-only in print/error strings. Module imports
  cleanly with no side effects.
- **Commit:** `feat(mill): add _psmux driver skeleton`

### Card 6: driver tests with subprocess mocks

- **Context:**
  - `_mill/discussion.md`
  - `plugins/mill/scripts/_psmux.py`
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/unit_tests/test-llm-claude.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-psmux-driver.py`
- **Deletes:** none
- **Requirements:** Module docstring. Mirror the `def main() -> int`
  runner pattern from `test-llm-claude.py`. Use `unittest.mock.patch`
  on `_subprocess_util.run` (patch the symbol AS IMPORTED inside
  `_psmux`, not the module-level original; e.g.
  `@mock.patch.object(_psmux._subprocess_util, "run")` if `_psmux`
  imports it as a module, OR `@mock.patch("_psmux._subprocess_util.run")`).
  One test per driver function asserting:
  - `new_session("s1", shell_argv=["pwsh", "-NoLogo"])` -> argv list
    starts with `["psmux", "new-session", "-d", "-s", "s1", "-x", "200",
    "-y", "50", "--", "pwsh", "-NoLogo"]` and the `timeout` kwarg equals
    `PSMUX_COMMAND_TIMEOUT_S`.
  - `set_history_limit("s1", 50000)` SUCCESS path: mock returns a
    CompletedProcess-like object with returncode 0; argv starts with
    `["psmux", "set-option", "-t", "s1", "-g", "history-limit", "50000"]`;
    no exception, no fallback message on stderr.
  - `set_history_limit("s1", 50000)` FALLBACK path: mock raises
    `PsmuxError`; assert function catches it, writes the literal line
    `[psmux] history-limit unsupported, using default` to stderr (capture
    via `contextlib.redirect_stderr(io.StringIO())` per
    `test-llm-claude.py` style), and returns `None`.
  - `send_keys("s1", "claude", enter=True)` -> argv ends with
    `[..., "send-keys", "-t", "s1", "claude", "Enter"]`.
  - `send_keys("s1", "Enter", enter=False)` -> argv ends with
    `[..., "send-keys", "-t", "s1", "Enter"]` (no extra Enter token).
  - `load_buffer("s1", "buf1", Path("p.txt"))` -> argv equals
    `["psmux", "load-buffer", "-b", "buf1", "p.txt"]` (path stringified).
  - `paste_buffer("s1", "buf1")` -> argv equals
    `["psmux", "paste-buffer", "-t", "s1", "-b", "buf1"]`.
  - `capture_pane("s1")` with mock stdout `"hello"` returns the literal
    string `"hello"`; argv equals
    `["psmux", "capture-pane", "-t", "s1", "-S", "-50000", "-p"]`.
  - `kill_session("s1")` SUCCESS: argv equals
    `["psmux", "kill-session", "-t", "s1"]`. KILL_NOT_FOUND path: mock
    raises `PsmuxError` whose message contains `"no such session"`;
    assert no exception leaks (idempotent teardown).
  - `list_sessions()` mock stdout `"alpha: x\nbeta: y\n"` returns
    `["alpha", "beta"]`. Empty stdout returns `[]`. Mock raising
    `PsmuxError` containing `"no server running"` returns `[]`.
  All ASCII-only in print/error strings. `if __name__ == "__main__":
  sys.exit(main())`. Tests fail against card 5 stubs; pass after card 7.
- **Commit:** `test(mill): implement _psmux driver tests`

### Card 7: driver implementation

- **Context:**
  - `_mill/discussion.md`
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/unit_tests/test-psmux-driver.py`
- **Edits:**
  - `plugins/mill/scripts/_psmux.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Replace each `NotImplementedError` body with the real
  subprocess call.
  - All calls go through `_subprocess_util.run(argv, timeout=PSMUX_COMMAND_TIMEOUT_S)`.
    Inspect existing call shapes in `_subprocess_util.py` for the keyword
    arguments accepted (e.g. `check`, `capture`, `text` defaults).
  - On any non-zero exit code (or subprocess exception) where not
    explicitly tolerated below, raise `PsmuxError(f"psmux <cmd> failed:
    {stderr_or_stdout_excerpt}")` -- include the first 200 chars of stderr
    or stdout for diagnostics.
  - `new_session`: argv `["psmux", "new-session", "-d", "-s", name, "-x",
    str(cols), "-y", str(rows), "--", *shell_argv]`.
  - `set_history_limit`: argv `["psmux", "set-option", "-t", name, "-g",
    "history-limit", str(limit)]`. Wrap call in `try/except PsmuxError`;
    on exception, `print("[psmux] history-limit unsupported, using
    default", file=sys.stderr)` and return None.
  - `send_keys`: argv `["psmux", "send-keys", "-t", name, keys] + (["Enter"]
    if enter else [])`. If `keys == ""` and `enter=False`, raise
    `ValueError("send_keys called with no keys and enter=False")` (not a
    PsmuxError -- this is a programming bug).
  - `load_buffer`: argv `["psmux", "load-buffer", "-b", buffer_name,
    str(file_path)]`.
  - `paste_buffer`: argv `["psmux", "paste-buffer", "-t", name, "-b",
    buffer_name]`.
  - `capture_pane`: argv `["psmux", "capture-pane", "-t", name, "-S",
    f"-{scrollback}", "-p"]`. Return `result.stdout` (string).
  - `kill_session`: argv `["psmux", "kill-session", "-t", name]`. Wrap
    in `try/except PsmuxError`; if exception message contains "no such
    session" (case-insensitive), swallow and return None; otherwise
    re-raise.
  - `list_sessions`: argv `["psmux", "ls"]`. Wrap in `try/except
    PsmuxError`; if exception message contains "no server running"
    (case-insensitive), return `[]`. Otherwise on success: split
    `result.stdout` on lines, strip each, drop empty, take everything
    before the first `:` on each line, return that list. Empty stdout
    returns `[]`.
  ASCII-only in print/error strings. Card 6's tests pass in full.
- **Commit:** `feat(mill): implement _psmux driver functions`

## Batch Tests

The batch is verified by `python
plugins/mill/unit_tests/test-psmux-driver.py` (also picked up by
`run-all.py`). All tests use `unittest.mock.patch` against
`_subprocess_util.run`; no real psmux binary is invoked. Card 6 introduces
the test file; card 7 implements the driver; the per-batch verify command
must exit 0 to pass.
