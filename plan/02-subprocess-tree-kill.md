# Batch: subprocess-tree-kill

```yaml
task: 'review-subsystem-fixes — Review subsystem: deleted-refs + execution infrastructure'
batch: subprocess-tree-kill
cards: 2
verify: uv run --project "${CLAUDE_PLUGIN_ROOT}" python "${CLAUDE_PLUGIN_ROOT}/unit_tests/run-all.py"
depends-on: []
```

## Batch Scope

Replaces `subprocess.run(timeout=)` inside `_subprocess_util.run` with a `Popen`-based loop that, on timeout, walks the entire process tree (`taskkill /T /F` on Windows, `os.killpg(SIGKILL)` on POSIX) after a 5-second grace period. Closes #86. Independent of every other batch — only `_subprocess_util.py` and its unit test change. The contract preserved: same `subprocess.CompletedProcess[str]` return, same `subprocess.TimeoutExpired` exception, same `[subprocess]` breadcrumb format on stderr, same UTF-8 / `errors=replace` decoding.

## Cards

### Card 8: Rewrite `_subprocess_util.run` with Popen + tree kill

- **Reads:**
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/unit_tests/test-subprocess-util.py`
- **Modifies:**
  - `plugins/mill/scripts/_subprocess_util.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Rewrite the body of `run(...)`: keep the existing signature, the spawn breadcrumb, and the UTF-8 child-env injection. Replace `subprocess.run(...)` with `subprocess.Popen(...)` in text mode (`encoding="utf-8"`, `errors="replace"`, `text=True`), with `stdin=subprocess.PIPE` if `input` is set else default, `stdout=subprocess.PIPE`, `stderr=subprocess.PIPE`, `cwd=cwd`, `env=child_env`, and `start_new_session=True` on POSIX (no flag on Windows — `taskkill /T` walks the tree without it). Use `proc.communicate(input=input, timeout=timeout)` to get stdout/stderr. On `subprocess.TimeoutExpired`: print the existing `[subprocess] exit code=timeout duration=...s` breadcrumb; call `proc.terminate()`; wait `_GRACE_SECONDS = 5` via `proc.wait(timeout=_GRACE_SECONDS)`; if that raises `TimeoutExpired` again (process still alive after grace), call `subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)` on Windows (`os.name == "nt"`) or `os.killpg(os.getpgid(proc.pid), signal.SIGKILL)` on POSIX, then `proc.wait()` to reap. Inside the timeout handler, capture the partial output from the caught exception via `collected_stdout = exc.stdout` and `collected_stderr = exc.stderr` (both may be `None` or `bytes` — preserve as-is to match `subprocess.run`'s behaviour on timeout). Re-raise `subprocess.TimeoutExpired(cmd=argv, timeout=timeout, output=collected_stdout, stderr=collected_stderr)` from the outer handler so callers see the same exception type as today. On normal completion: print the existing `[subprocess] exit code=... duration=...s` breadcrumb, then enforce `check`: if `check and proc.returncode != 0`, raise `subprocess.CalledProcessError(proc.returncode, argv, output=stdout, stderr=stderr)` BEFORE returning, preserving the documented `check=True` behaviour of `subprocess.run`. Otherwise return `subprocess.CompletedProcess(args=argv, returncode=proc.returncode, stdout=stdout, stderr=stderr)`. Add the imports (`os`, `signal`) at module top; do NOT import on POSIX-only path conditionally — keep the import block cross-platform (signal is available on Windows too; `os.killpg` is wrapped behind `os.name == "posix"`).
- **Commit:** `fix(subprocess): kill child process tree on timeout (#86)`

### Card 9: Test `_subprocess_util.run` timeout path

- **Reads:**
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/unit_tests/test-subprocess-util.py`
- **Modifies:**
  - `plugins/mill/unit_tests/test-subprocess-util.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Keep the existing `git --version` happy-path test. Import `_GRACE_SECONDS` alongside `run` from `_subprocess_util` so test (a)'s wall-time assertion can use the constant directly: `from _subprocess_util import run, _GRACE_SECONDS`. Add: (a) timeout-fires test — invoke the wrapper with argv `[sys.executable, "-c", "import time; time.sleep(60)"]` and `timeout=2.0`; assert `subprocess.TimeoutExpired` is raised within `2.0 + _GRACE_SECONDS + small_delta` seconds (use `time.monotonic()` deltas; `small_delta = 5` for slow CI). (b) breadcrumb format — capture stderr (use `contextlib.redirect_stderr` with an `io.StringIO`, OR run the wrapper as a subprocess and inspect its stderr); assert it contains `[subprocess] spawn argv=` and `[subprocess] exit code=timeout duration=`. (c) normal-completion regression — re-confirm `git --version` returns `CompletedProcess[str]` with `returncode == 0` and the right stdout. (d) `check=True` regression — invoke `[sys.executable, "-c", "import sys; sys.exit(7)"]` with `check=True`; assert `subprocess.CalledProcessError` is raised with `.returncode == 7`. (e) `check=False` regression — same argv with `check=False`; assert it returns a `CompletedProcess` with `returncode == 7` (no exception). Skip the live tree-kill assertion (the parent PID may be reaped before the test can probe it — that's an integration-test concern). Add a single-line comment at the top of the new test block referencing the integration-tests suite for the deeper kill verification.
- **Commit:** `test(subprocess): cover timeout-kill path`

## Batch Tests

`uv run --project "${CLAUDE_PLUGIN_ROOT}" python "${CLAUDE_PLUGIN_ROOT}/unit_tests/run-all.py"` — runs `test-subprocess-util.py` (covers Cards 8–9) plus every other test in the suite. Must be green at end of batch.

The deeper integration assertion (parent + child both gone after grace+kill) is deliberately deferred — it lives outside `unit_tests/` and is not part of this batch's `verify:`.
