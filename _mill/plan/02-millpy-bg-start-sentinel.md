# Batch: millpy-bg-start-sentinel

```yaml
task: '(A) — Subprocess handling: timeout + JSON-exit + Windows detach'
batch: millpy-bg-start-sentinel
number: 2
cards: 4
verify: python plugins/mill/unit_tests/test-millpy-bg.py
depends-on: [1]
```

## Batch Scope

This batch adds the worker start sentinel to `millpy-bg.py` — the worker writes `[mill-bg] WORKER PID=<pid> START <iso8601>\n` as the first line of the log file, before invoking the child subprocess. The sentinel is diagnostic-only in this task: callers (mill-start / mill-plan / mill-go) are explicitly OUT of scope; their poll-for-EXIT loops are unchanged. The sentinel's value here is observability — an empty log file unambiguously means "worker never ran", a START-only log means "worker ran but child has no output yet", the existing EXIT sentinel continues to mean "child finished". The launcher's `pid=<N>` print comment is updated to document the post-batch-1 pid shift (the printed pid is the cmd-shim PID, not the worker PID). One new integration test, `plugins/mill/integration_tests/test-millpy-bg-detached.py`, exercises the full end-to-end: it manufactures a job-bound parent via ctypes (`CreateJobObjectW` + `SetInformationJobObject(JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE)` + `AssignProcessToJobObject(job, GetCurrentProcess())`), spawns `millpy-bg.py` from inside that job, and asserts both the new START sentinel and the EXIT sentinel land in the log file within budget. The integration test is the only place the cross-job-object behaviour from batch 1's `popen_detached` change is actually verified end-to-end; that is the depends-on link to batch 1. Unit tests are mock-based and do not need the batch-1 change in place to pass.

## Cards

### Card 5: red-test for worker start sentinel

- **Context:**
  - `_mill/discussion.md`
  - `plugins/mill/scripts/millpy-bg.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-bg.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a new test (n) named "worker writes START sentinel" to `test-millpy-bg.py` BEFORE editing `millpy-bg.py`. The test reuses the existing tempfile + `_worker_main` pattern from test (h): call `_worker_main(["--log", str(log_path), "--", sys.executable, "-c", "print('hello')"])`, read the log file, assert that the FIRST line of the log matches a regex like `r"^\[mill-bg\] WORKER PID=\d+ START \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z\n"` (ISO 8601 UTC; trailing `Z` required). Assert the rest of the log still contains `"hello"` (the child's stdout, unchanged from test (h)) and ends with `"[mill-bg] EXIT 0"` (unchanged from test (i)). Run `python plugins/mill/unit_tests/test-millpy-bg.py` and confirm test (n) fails against unmodified `millpy-bg.py` — the START sentinel is absent so the regex match fails.
- **Commit:** `test(millpy-bg): add worker START sentinel red test (#271)`

### Card 6: Worker start sentinel write in `millpy-bg.py`

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/scripts/millpy-bg.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In the worker fast-path of `millpy-bg.py`, inside the `with open(log_path, "w", encoding="utf-8", buffering=1) as log_f:` block (around line 48), write the start sentinel as the FIRST action inside the `with` block, BEFORE the `subprocess.run(cmd, stdout=log_f, ...)` call. Use stdlib-only imports — the worker fast-path is documented as `# worker fast-path — stdlib only, no mill imports` (line 22 comment) and must stay that way. Acceptable form: `import os` (already imported via `sys`? No — add `import os` at the top of the worker fast-path block alongside `import subprocess`), `from datetime import datetime, timezone` (already imported in the launcher path but the worker path runs before the launcher imports happen because of the `if "--_worker" in sys.argv:` guard — add `from datetime import datetime, timezone` inside the worker fast-path block), then `log_f.write(f"[mill-bg] WORKER PID={os.getpid()} START {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}\n")`. Line buffering (`buffering=1`) flushes on the newline. The sentinel string is pure ASCII per the shared decision. Run `python plugins/mill/unit_tests/test-millpy-bg.py` after the edit and confirm test (n) plus tests (h)–(l) all pass.
- **Commit:** `feat(millpy-bg): write WORKER START sentinel as first log line (#271)`

### Card 7: Document pid shift in launcher comment

- **Context:**
  - `_mill/discussion.md`
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-bg.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Update the launcher fast-path's `print(f"pid={proc.pid} log={log_path}")` line (around line 128 in `_launcher_main`) with a one-line `# NOTE:` comment immediately above the print, stating that on Windows after the batch-1 `popen_detached` change, `proc.pid` is the cmd-shim PID (which exits almost immediately) — the authoritative worker PID is in the `[mill-bg] WORKER PID=...` sentinel inside the log file. The comment is informational only; no behaviour change. The `print` line itself stays exactly as today — every existing caller consumes only `log=<path>` and not the printed pid. Also update the launcher mode's module docstring at the top of the file: the existing line `printed: pid=<N> log=<path>` (or equivalent) gets a parenthetical noting "(on Windows the pid is the cmd-shim launcher PID; the worker PID is logged inside the file as `[mill-bg] WORKER PID=...`)". No test changes; this is documentation-only. Re-run the unit tests to confirm nothing regresses.
- **Commit:** `docs(millpy-bg): document pid-shift in launcher comment + docstring`

### Card 8: Integration test — detached worker survives job-bound parent

- **Context:**
  - `_mill/discussion.md`
  - `plugins/mill/scripts/millpy-bg.py`
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/integration_tests/test-spawn.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/integration_tests/test-millpy-bg-detached.py`
- **Deletes:** none
- **Requirements:** Create a new local-dev-only integration test that proves the two-stage `cmd /c start /B` launch (batch 1) plus the start-sentinel (cards 5–6) survive a job-bound parent. Open with the module docstring pattern from `test-spawn.py` (purpose, invocation example, "local-dev only", "Windows-only"). Skip-guard: `if os.name != "nt": print("SKIP test-millpy-bg-detached: Windows-only"); sys.exit(0)`. Use ctypes to create the job-bound parent condition inside the test process itself: load `kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)`; declare the required structs (`JOBOBJECT_BASIC_LIMIT_INFORMATION` with at least `PerProcessUserTimeLimit`, `PerJobUserTimeLimit`, `LimitFlags`, `MinimumWorkingSetSize`, `MaximumWorkingSetSize`, `ActiveProcessLimit`, `Affinity`, `PriorityClass`, `SchedulingClass`); set `LimitFlags = 0x2000` (`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`); call `kernel32.CreateJobObjectW(None, None)`, `kernel32.SetInformationJobObject(job, 2, ctypes.byref(info), ctypes.sizeof(info))` (info-class `2` is `JobObjectBasicLimitInformation`), `kernel32.AssignProcessToJobObject(job, kernel32.GetCurrentProcess())`. Then in the same test process spawn `millpy-bg.py` via `subprocess.Popen([sys.executable, str(HUB / "plugins" / "mill" / "scripts" / "millpy-bg.py"), "--slug", "it-detach", "--", sys.executable, "-c", "print('hi')"])`, read the `pid=<N> log=<path>` line from its stdout (the launcher prints it before exiting), parse out the log path, then poll the log file for up to 10 seconds in 0.5-second intervals: the START sentinel must appear within the first 5 seconds, the EXIT sentinel within 10. The test process exits naturally at the end (or via `sys.exit(0)`); even though `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` is set on the job, the worker is outside the job (escape via cmd /c start) so it survives. After the polling phase confirms both sentinels, the test asserts `subprocess.run(["tasklist", "/FI", f"PID eq {worker_pid_from_sentinel}"], ...)` returns the worker is gone (it finished and emitted EXIT). Note: parse `worker_pid_from_sentinel` out of the START sentinel line via a regex match for `PID=(\d+)`. Cleanup: close the job handle via `kernel32.CloseHandle(job)`. Exit 0 on PASS. The test is not invoked by `verify:`.
- **Commit:** `test(millpy-bg): integration test for detached worker from job-bound parent (#271)`

## Batch Tests

The `verify:` command `python plugins/mill/unit_tests/test-millpy-bg.py` runs the full launcher + worker unit-test file. After the implementer's changes it must produce zero failures across tests (a)–(n). Tests (a)–(g) (launcher path / arg parsing) and (m) (utcnow) are unaffected — they pass against unmodified code, and the new card-7 docstring edit does not change their behaviour. Tests (h)–(j) (worker output + EXIT sentinel) continue to pass after card 6's start-sentinel write because the assertion shapes (`"hello" in log_text` / `"[mill-bg] EXIT 0" in log_text`) are unchanged by the new first line. Test (k)/(l) (missing-flag returns 1) are unchanged. Test (n) is the new card-5 regression: it failed against the un-fixed worker, passes after card 6 lands. The new integration test `test-millpy-bg-detached.py` is exercised manually on Windows.
