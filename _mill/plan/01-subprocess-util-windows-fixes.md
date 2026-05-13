# Batch: subprocess-util-windows-fixes

```yaml
task: '(A) — Subprocess handling: timeout + JSON-exit + Windows detach'
batch: subprocess-util-windows-fixes
number: 1
cards: 4
verify: python plugins/mill/unit_tests/test-subprocess-util.py && python plugins/mill/integration_tests/test-subprocess-tree-kill.py
depends-on: []
```

## Batch Scope

This batch closes the two `_subprocess_util.py` regressions on Windows: `run`'s timeout deadline is now enforced by a watchdog that polls `time.monotonic()` in the main thread and kills the full process tree via `taskkill /T /F` when the deadline trips (fix for #269); `popen_detached` is rewritten on Windows to dispatch the child through `cmd /c start "" /B /MIN <argv>`, which escapes the parent's Win32 Job Object so the worker survives launcher exit under VS Code / CC Bash (fix for #271 detach mechanism). POSIX paths in both functions stay byte-identical. The companion test file `test-subprocess-util.py` gains a grandchild-kill regression test that proves #269 cannot recur, plus updated mock-based assertions for the new Windows argv shape of `popen_detached`. One new integration test, `plugins/mill/integration_tests/test-subprocess-tree-kill.py`, exercises the cross-process kill-tree on real Windows subprocesses; it is local-dev only and not in `verify:`. The next batch (millpy-bg-start-sentinel) consumes the new `popen_detached` behaviour transparently — its only direct dependency on this batch is the integration-test detached-worker scenario.

## Cards

### Card 1: red-test for cross-process timeout-kill in `_subprocess_util.run`

- **Context:**
  - `_mill/discussion.md`
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-subprocess-util.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a new test (m) named "grandchild kill tree" to `test-subprocess-util.py` BEFORE editing `_subprocess_util.py`. The test spawns a real Python parent that itself spawns a long-running grandchild and then sleeps; pseudo-code: `argv = [sys.executable, "-c", "import subprocess, sys, time; p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)']); print(p.pid, flush=True); time.sleep(120)"]`. The test invokes `run(argv, timeout=2.0)` inside `contextlib.redirect_stderr(io.StringIO())`, asserts `subprocess.TimeoutExpired` is raised within wall-time budget `2.0 + _GRACE_SECONDS + _SMALL_DELTA`, parses the grandchild PID from `exc.stdout` (which captures the parent's printed PID), then asserts both the parent PID and the grandchild PID are gone via `subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True)` returning a stdout that contains the literal `"No tasks are running which match the specified criteria."`. Skip the test on POSIX with `if os.name != "nt": print("SKIP (m): not applicable on POSIX"); ...`. Run `python plugins/mill/unit_tests/test-subprocess-util.py` after writing the new test; it MUST fail (TimeoutExpired not raised, or grandchild still alive) against unmodified `_subprocess_util.py` — record the failure mode in the implementer's run log as proof of red-state before proceeding to card 2.
- **Commit:** `test(subprocess-util): add grandchild kill-tree regression test (#269 red)`

### Card 2: Windows watchdog timeout in `_subprocess_util.run`

- **Context:**
  - `_mill/discussion.md`
  - `plugins/mill/scripts/_llm_claude.py`
- **Edits:**
  - `plugins/mill/scripts/_subprocess_util.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Inside `run(...)`, replace `proc.communicate(input=input, timeout=timeout)` on the Windows path (`os.name == "nt"`) with a watchdog loop. Add `subprocess.CREATE_NEW_PROCESS_GROUP` to `popen_kwargs["creationflags"]` on Windows so the existing `creationflags = CREATE_NO_WINDOW` becomes `creationflags = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP`. The watchdog must: (a) start a `threading.Thread(target=..., daemon=True)` to drain `proc.stdout` via `readline()` into a per-stream `list[str]` guarded by `threading.Lock()`, ONLY when `proc.stdout is not None`; same for `proc.stderr`. (b) When `input is not None`, start a third daemon thread that calls `proc.stdin.write(input)` then `proc.stdin.close()`. (c) The main thread polls `proc.poll() is None and time.monotonic() < endtime` in a `time.sleep(0.1)` loop, where `endtime = time.monotonic() + timeout`. (d) When `proc.poll()` returns non-None, the watchdog joins the reader threads with `thread.join(timeout=1.0)`, decodes/joins the per-stream lists into final `stdout_out` / `stderr_out` strings (`"".join(buf)`), and proceeds to the normal exit-breadcrumb + CompletedProcess return path. (e) When the deadline trips first, the watchdog emits `print(f"[subprocess] exit code=timeout duration={time.monotonic() - start:.3f}s", file=sys.stderr)`, runs `subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)`, calls `proc.wait(timeout=_GRACE_SECONDS)` inside a try/except (suppress `subprocess.TimeoutExpired` from this internal wait — the kill has already been issued), joins reader threads with a 1-second timeout, collects whatever stdout/stderr were captured so far from the per-stream lists, then raises `subprocess.TimeoutExpired(cmd=argv, timeout=timeout, output=collected_stdout, stderr=collected_stderr)`. POSIX path stays exactly as today (`proc.communicate(input=input, timeout=timeout)` + the existing `except subprocess.TimeoutExpired` block with `os.killpg(os.getpgid(proc.pid), signal.SIGKILL)`). The `timeout is None` short-circuit MUST be preserved on both platforms: when `timeout is None`, fall through to the simple `proc.communicate(input=input)` call with no watchdog logic. The `check=True` + non-zero-returncode path stays identical. The function's docstring gets one new paragraph documenting the Windows watchdog path; the public signature stays unchanged. After writing the production change, re-run `python plugins/mill/unit_tests/test-subprocess-util.py` and confirm every test passes including the new (m).
- **Commit:** `fix(subprocess-util): enforce Windows timeout via watchdog + taskkill /T /F (#269 green)`

### Card 3: Two-stage `cmd /c start /B` launch in `_subprocess_util.popen_detached`

- **Context:**
  - `_mill/discussion.md`
  - `plugins/mill/scripts/millpy-bg.py`
- **Edits:**
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/unit_tests/test-subprocess-util.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_subprocess_util.popen_detached`, on Windows (`os.name == "nt"`) prepend `["cmd", "/c", "start", "", "/B", "/MIN"]` to the supplied `argv` before passing it to `subprocess.Popen`. The empty `""` is the literal title argument required by Windows `start` syntax; `/B` suppresses the new console; `/MIN` belt-and-braces against console flash. The existing `creationflags = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP | _CREATE_BREAKAWAY_FROM_JOB` MUST be preserved unchanged — `BREAKAWAY_FROM_JOB` is a defensive fallback for environments where the intermediate cmd is itself in a non-breakaway job. POSIX path stays exactly as today. Update the function's docstring with a new paragraph titled "Windows: pid shift" explaining that on Windows the returned `Popen.pid` is the intermediate `cmd.exe` shim PID, which exits immediately; the authoritative worker PID is recorded by the worker itself in the new `[mill-bg] WORKER PID=<pid> START <iso8601>` log sentinel introduced in batch 2; no current caller of `popen_detached` consumes the returned pid for process management (verified by grep at plan time). In `test-subprocess-util.py`, update existing test (k) `popen_detached creationflags on Windows`: the new assertion must verify (1) that `subprocess.Popen` was called with argv prefix `["cmd", "/c", "start", "", "/B", "/MIN"]` followed by the original argv, and (2) that `creationflags` equals `CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP | 0x01000000` (unchanged). Test (l) `popen_detached start_new_session on POSIX` MUST stay unchanged and continue to pass. Test (i) `popen_detached returns Popen with pid` MUST be updated for Windows-only fallout: since the returned process is the cmd shim that exits almost immediately, the existing `proc.wait(timeout=5)` continues to work but the `assert proc.returncode == 0` may now race against the shim's `start` dispatch — if the assertion becomes flaky, replace `proc.wait(timeout=5)` + `assert proc.returncode == 0` with `proc.wait(timeout=5)` only and assert `proc.returncode is not None`. Run `python plugins/mill/unit_tests/test-subprocess-util.py` and confirm green.
- **Commit:** `fix(subprocess-util): escape parent job via cmd /c start /B in popen_detached (#271 detach)`

### Card 4: Integration test — cross-process kill-tree on real Windows subprocesses

- **Context:**
  - `_mill/discussion.md`
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/integration_tests/test-spawn.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/integration_tests/test-subprocess-tree-kill.py`
- **Deletes:** none
- **Requirements:** Create a new Windows-only integration test that exercises the watchdog kill-tree on real subprocesses. Open with the module docstring pattern from `test-spawn.py` (purpose, run-from-hub-root invocation example, Windows-only note). Skip-guard on POSIX as the FIRST executable statement (before any non-stdlib import): `if os.name != "nt": print("SKIP test-subprocess-tree-kill: Windows-only"); sys.exit(0)`. Import path setup: same `HUB = Path(__file__).resolve().parent.parent.parent.parent` + `sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))` pattern. The test body: spawn `_subprocess_util.run(argv, timeout=2.0)` where `argv = [sys.executable, "-c", "import subprocess, sys, time; p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)']); print(p.pid, flush=True); time.sleep(120)"]` inside a try/except for `subprocess.TimeoutExpired`. Capture the grandchild PID from `exc.stdout`. After the kill, sleep 1 second to let Windows reap the processes, then assert both PIDs are gone via `tasklist /FI "PID eq <pid>"` stdout containing `"No tasks are running which match the specified criteria."`. Exit 0 on PASS, 1 on any assertion failure. The test is chained into batch 1's `verify:` via `&&` — it runs as a no-op on POSIX (immediate `sys.exit(0)` from the skip-guard) and as a real cross-process test on Windows.
- **Commit:** `test(subprocess-util): integration test for grandchild kill-tree (#269)`

## Batch Tests

The `verify:` command chains the unit test and the integration test with `&&`. The unit-test phase (`python plugins/mill/unit_tests/test-subprocess-util.py`) runs the full unit-test file and must produce zero failures across tests (a)–(m): test (m) is the new grandchild-kill regression (failed red in card 1, green after card 2's watchdog); tests (k)/(l) continue to verify the creationflags / start_new_session split (test (k) updated in card 3 for the new Windows argv shape); tests (c)–(i) continue to verify normal-completion, breadcrumb format, check= behaviour, stdout/stderr overrides, and basic detach return-shape. The integration-test phase (`python plugins/mill/integration_tests/test-subprocess-tree-kill.py`) is a no-op on POSIX (exits 0 immediately via the skip-guard); on Windows it spawns a real parent + grandchild, asserts the watchdog kills both via `tasklist`, and exits 0 on pass / 1 on any assertion failure.
