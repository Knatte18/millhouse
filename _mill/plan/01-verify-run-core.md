# Batch: verify-run-core

```yaml
task: Instrument and bound the verify runner
batch: verify-run-core
number: 1
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-verify-run.py test-status.py test-merge-in-subagent.py test-millpy-merge-in-subagent.py test-millpy-bg.py test-implementer-common.py
depends-on: []
```

## Batch Scope

Delivers the shared verify runner (`plugins/mill/scripts/_verify_run.py`), the `## Verify log` helpers in `_status.py`, the `pipeline.verify_timeout_minutes` config key, and the `millpy-bg.py` heartbeat change.
No verify site is switched over yet; batches 3-5 consume `_verify_run.run_verify` and its helpers by the names fixed in the overview's "shared names every batch uses" decision.
`_posix_shell_run_args` moves into `_verify_run.py` here, and its two current importers are repointed in the same card so nothing breaks between batches.

## Cards

### Card 1: Verify-log section helpers in status.md

- **Context:**
  - `plugins/mill/scripts/_yaml_writer.py`
- **Edits:**
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/unit_tests/test-status.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add a `## Verify log` section to `_status.py`, following the existing `append_recovery_log` / `_find_recovery_log_block` pattern (heading, blank line, `_TIMELINE_FENCE` fenced block, lazily created at the end of the file on first append, rows inserted before the closing fence).
  - Add constant `_VERIFY_LOG_HEADING = "## Verify log"` next to `_RECOVERY_LOG_HEADING`, and `_find_verify_log_block(lines)` with the same return shape and `ValueError` cases as `_find_recovery_log_block`.
  - Add public `normalize_log_field(text: str, max_len: int | None = None) -> str`: collapse every whitespace run (including newlines) to one space and strip the ends, replace every backtick with `'`, replace every non-ASCII character with `?`, and when `max_len` is given and the result is longer, cut it to `max_len` characters and append `...`.
  - Add `append_verify_log(status_path, *, timestamp: str, label: str, exit: int | str, wall_s: float, first_run: bool, cmd: str) -> None` (keyword-only after `status_path`; `exit` is the exit code, or the string `timeout` / `launch-error`).
    The row is `f"{quote_scalar(timestamp)}  {label}  exit={exit}  wall={wall_s:.1f}s  first_run={'true' if first_run else 'false'}  cmd={cmd}"` where `label` is `normalize_log_field(label)` and `cmd` is `normalize_log_field(cmd, 300)`.
  - Add `read_verify_log_rows(status_path) -> list[str]`: the row lines inside the section's fenced block, verbatim and in order; `[]` when the section is absent.
  - Add `restore_verify_log_rows(status_path, rows: list[str]) -> int`: append each row not already present in the block (exact line text), in order, creating the section when it is absent and at least one row needs adding; return the number appended; return 0 without writing the file when nothing needs adding.
  - Each new public function gets a docstring in the style of `append_recovery_log`'s.
  Tests in `test-status.py`: section created on first append; rows appended in order; other sections (Timeline, `## Tracked-file recovery log`) untouched; a multi-line `cmd` containing a triple backtick and a non-ASCII character yields one single-line, backtick-free, ASCII row and `_find_verify_log_block` still parses the section afterwards; a 400-character `cmd` is cut to 300 plus `...`; `read_verify_log_rows` returns rows verbatim and `[]` without the section; `restore_verify_log_rows` creates the section in a file without it, skips rows already present, and returns the count appended.
- **Commit:** `feat(status): add Verify log section helpers`

### Card 2: Shared verify runner module

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_timestamp.py`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/millpy-bg.py`
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
  - `plugins/mill/unit_tests/test-merge-in-subagent.py`
- **Creates:**
  - `plugins/mill/scripts/_verify_run.py`
  - `plugins/mill/unit_tests/test-verify-run.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Create `plugins/mill/scripts/_verify_run.py` (module docstring stating its purpose and public API, ASCII-only output), test-first: write the pipe-trap regression in `test-verify-run.py` before the implementation.
  It imports only stdlib plus `_paths`, `_status` and `_timestamp`; it must never import `_implementer_common`.
  - Constants: `DEFAULT_TIMEOUT_MINUTES = 20`, `HEARTBEAT_INTERVAL_S = 30` (tests patch it), `CMD_FIELD_MAX = 300`.
  - `VerifyRun` dataclass with fields `label: str`, `cmd: str`, `cwd: Path`, `exit_code: int | None`, `wall_s: float`, `first_run: bool`, `timed_out: bool`, `output: str`, `output_path: Path | None`, `timeout_s: float`, and method `summary() -> dict` returning `label`, `cmd`, `exit_code`, `wall_s` (rounded to 0.1), `first_run`, `timed_out`.
  - Move `_posix_shell_run_args` out of `_implementer_common.py` into `_verify_run.py` unchanged (same body, same docstring, now using `_verify_run`'s own `os`/`shutil` imports).
    In `_implementer_common.py` delete the definition and add `from _verify_run import _posix_shell_run_args` so `_run_verify_gate` keeps working until batch 3.
    In `millpy-merge-in-subagent.py` drop `_posix_shell_run_args` from the `from _implementer_common import ...` line and add `from _verify_run import _posix_shell_run_args`.
    Move the three `_posix_shell_run_args` cases (Windows with bash, Windows without bash, POSIX) out of `test-merge-in-subagent.py` into `test-verify-run.py`, patching `_verify_run.os` / `_verify_run.shutil` instead of `_implementer_common.os` / `_implementer_common.shutil`.
  - `timeout_seconds(cfg: dict) -> float`: read `(cfg.get("pipeline") or {})` key `verify_timeout_minutes`; absent key -> `DEFAULT_TIMEOUT_MINUTES * 60`; present value must be an `int` or `float` (not `bool`) greater than 0, returned times 60; anything else (including `None`) raises `ValueError` whose message names `pipeline.verify_timeout_minutes` and the bad value.
  - `resolve_status_path(hub_root: Path, cfg: dict) -> Path | None`: `_paths.status_path(hub_root, cfg)` when that file exists, else `None`; a `KeyError` from a cfg without `paths.status_md` also yields `None`.
  - `timeout_prefix(run) -> str` returns `f"[verify timed out after {int(run.timeout_s)}s: {run.label}] "`; `output_suffix(run) -> str` returns `f"\n[verify output: {run.output_path}]"` (empty string when `output_path` is `None`).
  - `run_verify(cmd: str, *, cwd: Path, label: str, git_root: Path, timeout_s: float, shell_mode: str, env: dict | None = None, status_path: Path | None = None) -> VerifyRun`.
    Raises `ValueError` only for programmer errors: `cwd is None`, or `shell_mode` not in `{"posix", "native"}`.
    Never raises for command failure, timeout or launch failure.
    Behaviour, in order:
    1. `verify_dir = git_root / ".scratch" / "verify"` (created with parents). `first_run = not (verify_dir / "first-run.done").exists()`.
    2. Output file `verify_dir / f"{_timestamp.now_utc_compact()}-{_paths.sanitize_filename_component(label)}.out"`; when that name already exists, append `-2`, `-3`, ... before `.out`.
    3. Child env: copy of `env` (or `os.environ`), then set `PYTHONIOENCODING=utf-8`, `MSBUILDDISABLENODEREUSE=1`, `DOTNET_CLI_USE_MSBUILD_SERVER=0` for every command.
    4. Argv: `"posix"` -> `_posix_shell_run_args(cmd)` passed to `Popen` as-is; `"native"` -> `Popen(cmd, shell=True)`.
       `Popen` gets `cwd=cwd`, `stdin=subprocess.DEVNULL`, `stdout=<output file opened "wb">`, `stderr=subprocess.STDOUT`, and its own process group: `creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW` when `os.name == "nt"`, else `start_new_session=True`.
    5. Write `START <label> first_run=<true|false> timeout=<int>s cwd=<cwd> cmd=<cmd>`; start a daemon heartbeat thread writing `HEARTBEAT <label> elapsed=<int>s cmd=<cmd>` every `HEARTBEAT_INTERVAL_S`, stopped and joined in a `finally` (mirror `millpy-bg.py`'s `_heartbeat` Event pattern).
    6. `proc.wait(timeout=timeout_s)`; on `subprocess.TimeoutExpired` kill the tree with no terminate step -- `subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)` on Windows, `os.killpg(proc.pid, signal.SIGKILL)` on POSIX (ignore `ProcessLookupError`) -- then `proc.wait(timeout=10)` ignoring a second `TimeoutExpired`; set `timed_out=True`, `exit_code=None`.
    7. Close the file, then read it back with `read_bytes().decode("utf-8", errors="replace")` into `output`.
    8. A launch failure (`OSError` from `Popen`, e.g. missing cwd or binary) yields `exit_code=None`, `timed_out=False`, `output=str(exc)`; the output file may be empty.
    9. Write `END <label> exit=<rc|timeout|launch-error> wall=<N.N>s output=<output_path>`.
    10. Create `first-run.done` (touch) whatever the outcome.
    11. When `status_path` is not `None`, call `_status.append_verify_log(status_path, timestamp=_timestamp.now_utc_iso(), label=label, exit=<rc|"timeout"|"launch-error">, wall_s=wall_s, first_run=first_run, cmd=cmd)` inside `try`; on any exception print one `[verify] could not write Verify log row: <exc>` line to stderr.
        When `status_path` is `None`, print one `[verify] no status.md -- Verify log row skipped for <label>` line to stderr.
    Every marker line is prefixed `[verify] <_timestamp.now_utc_iso()> `, uses `_status.normalize_log_field(cmd, CMD_FIELD_MAX)` for `cmd=` and `_status.normalize_log_field` for `label` and `cwd`, is written to `sys.stderr` (flushed), and is appended to `verify_dir / "verify.log"` (opened in append mode per line, flushed); a failure writing `verify.log` is swallowed so it never changes the verdict.
    `wall_s` is measured with `time.monotonic()` from just before `Popen` to just after the wait.
  Tests in `test-verify-run.py` (script style like the sibling test files, each case printing `PASS:`/`FAIL:`, exit non-zero on any failure; children are `sys.executable` scripts written to a temp dir; `git_root` is a temp dir; no git, no LLM):
  - Pipe trap (write first): the command's child starts a grandchild that inherits stdout and sleeps 30 s, then exits 0; `run_verify` returns within 10 s with `exit_code == 0`; the test kills the grandchild afterwards (it writes its pid to a file).
  - Timeout: a child that starts a non-detaching grandchild (pid written to a file) and sleeps 60 s, with `timeout_s=1`; result has `timed_out=True`, `exit_code is None`, and the grandchild is gone afterwards (POSIX: `os.kill(pid, 0)` raises; Windows: `tasklist /FI "PID eq <pid>"` output lacks the pid).
  - First-run marker: first call `first_run=True`, second call in the same `git_root` `False`; the marker exists after a failing run and after a timeout.
  - START/HEARTBEAT/END: with `HEARTBEAT_INTERVAL_S` patched to 0.05 and a child sleeping 0.3 s, all three line kinds appear in captured stderr and in `.scratch/verify/verify.log`, and every line is ASCII.
  - Env: the child echoes `MSBUILDDISABLENODEREUSE`, `DOTNET_CLI_USE_MSBUILD_SERVER` and a caller-supplied `env` key into its output; all three are present.
  - Output: stdout and stderr of the child both appear in `output`, and `output_path` exists.
  - Decoding: a child writing invalid UTF-8 bytes yields `output` containing `�`, no exception.
  - Launch failure: a nonexistent `cwd` returns a `VerifyRun` with `exit_code is None`, `timed_out is False`.
  - Status row: with a temp status file, one `## Verify log` row is appended per run; with `status_path=None` no file is written and stderr carries the skip note.
  - Shell mode: the three moved `_posix_shell_run_args` cases, plus `"native"` building a `shell=True` call (patch `_verify_run.subprocess.Popen` and inspect its call args).
  - `timeout_seconds`: absent key -> 1200.0; `{"verify_timeout_minutes": 5}` -> 300.0; `0`, `-1`, `"x"`, `None` and `True` each raise `ValueError` naming the key.
  - `resolve_status_path`: existing file -> path; missing file or missing `paths` key -> `None`.
- **Commit:** `feat(verify): add shared verify runner module`

### Card 3: verify_timeout_minutes config key

- **Context:**
  - `plugins/mill/scripts/_verify_run.py`
  - `plugins/mill/unit_tests/test-ask-thread.py`
- **Edits:**
  - `plugins/mill/templates/mill-config.yaml`
  - `mill-config.yaml`
  - `plugins/mill/unit_tests/test-verify-run.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  This is the plan's bootstrap card for the hub `mill-config.yaml` edit: the key is additive, `_verify_run.timeout_seconds` returns the same 20-minute default when it is absent, and this task's own mill-go runs from the deployed plugin copy that has no reader for it, so adding it mid-flight changes nothing for the running task.
  In both `plugins/mill/templates/mill-config.yaml` and the hub `mill-config.yaml`, add `verify_timeout_minutes: 20` inside the `pipeline:` block directly after `done_gate_baseline_preflight`, with the trailing comment `# Per-command bound (minutes) on every verify command run via _verify_run.run_verify: batch and module-wide gates, finalize replays, done gate, merge-in replays. Must be a positive number; a timeout fails the gate loudly.`
  Add a config-sync case to `test-verify-run.py`, mirroring the hub/template loop at the end of `test-ask-thread.py` (load each file with `yaml.safe_load`, `HUB` resolved from the test file's location the same way), asserting `data["pipeline"]["verify_timeout_minutes"] == _verify_run.DEFAULT_TIMEOUT_MINUTES` for both files.
  Do not edit `test-ask-thread.py`; it is red on `main`.
- **Commit:** `feat(config): add pipeline.verify_timeout_minutes`

### Card 4: millpy-bg heartbeat names its command

- **Context:**
  - `plugins/mill/scripts/_bg.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-bg.py`
  - `plugins/mill/unit_tests/test-millpy-bg.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `millpy-bg.py`'s worker fast path (stdlib only, no mill imports), change the `_heartbeat` line to `f"[mill-bg] HEARTBEAT {<UTC ts, same strftime as today>} elapsed={int(time.monotonic() - started)}s cmd={cmd_text}\n"`.
  `started` is `time.monotonic()` captured just before the heartbeat thread starts; `cmd_text` is `" ".join(cmd)` and, when longer than a new module constant `_HEARTBEAT_CMD_MAX = 200`, its first 200 characters followed by `...`.
  Add `import time` to the fast-path imports.
  `_bg.py` never parses heartbeat text and is not modified.
  In `test-millpy-bg.py`, update the existing heartbeat-format assertion (the regex currently anchored as `^\[mill-bg\] HEARTBEAT <ts>Z$`) to the new shape, and add cases: the line keeps the `[mill-bg] HEARTBEAT ` prefix and contains `elapsed=<digits>s` and `cmd=` followed by the inner command; a command longer than 200 characters appears cut to 200 characters plus `...`.
- **Commit:** `feat(bg): name the inner command and elapsed time in heartbeats`

## Batch Tests

`verify:` runs `test-verify-run.py` (new), `test-status.py` (card 1), `test-merge-in-subagent.py` (moved cases), `test-millpy-merge-in-subagent.py` (import change), `test-millpy-bg.py` (card 4) and `test-implementer-common.py` (import change in `_implementer_common.py`).
All named pre-existing files pass on this branch's base.
