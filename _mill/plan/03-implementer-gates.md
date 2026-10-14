# Batch: implementer-gates

```yaml
task: Instrument and bound the verify runner
batch: implementer-gates
number: 3
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-verify-run.py
depends-on: [1, 2]
```

## Batch Scope

Switches `_implementer_common.py`'s verify gates onto `_verify_run.run_verify`, adds the timeout verdict, threads timeout/label/status path through `_forward_output` and `finalize_from_output`, adds `verify_runs` to every envelope at one chokepoint, and excludes `_mill/status.md` from the module's own dirty-tree checks.
Batch 4 (CLIs) and batch 5 (merge-in) consume the new keyword arguments and `_truncate_verify_output`.
Batch-local decision: `_implementer_common` calls the runner as `_verify_run.run_verify(...)` through the module attribute (never `from _verify_run import run_verify`), so patching `_verify_run.run_verify` in tests intercepts every call.

## Cards

### Card 6: Verify gates run through the shared runner

- **Context:**
  - `plugins/mill/scripts/_verify_run.py`
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `_implementer_common.py` add `import _verify_run` and drop the `from _verify_run import _posix_shell_run_args` line batch 1 added (no remaining use after this card).
  - Extract the 2000-character truncation block of `_run_verify_gate` (the `output_stripped` / `tail` / `omitted` / `fail_lines` / `marker` logic) into `_truncate_verify_output(text: str) -> str`, behaviour unchanged, with a docstring; `_run_verify_gate` calls it.
  - `_run_verify_gate(project_root, verify_cmd, *, git_root=None, cwd_override=None, timeout_s: float | None = None, status_path: Path | None = None, label: str = "verify", runs: list | None = None) -> dict | None`.
    `timeout_s=None` means `_verify_run.DEFAULT_TIMEOUT_MINUTES * 60`.
    Replace both `subprocess.run(run_args, capture_output=True, text=True, ...)` verify calls with `_verify_run.run_verify(verify_cmd, cwd=effective_cwd, label=..., git_root=git_root if git_root is not None else project_root, timeout_s=..., shell_mode="posix", status_path=status_path)`; append every returned `VerifyRun` to `runs` when `runs` is not `None`.
    The output to scan and report is `run.output` (combined stream).
    Order of handling for a run: timed out -> return `{"status": "stuck", "stuck_type": "verify", "reason": _verify_run.timeout_prefix(run) + _truncate_verify_output(run.output.strip()) + _verify_run.output_suffix(run), "timed_out": True}`, never calling `_is_benign_windows_cleanup` or the lock-race retry;
    launch failure (`exit_code is None`) -> `{"status": "stuck", "stuck_type": "verify", "reason": f"verify gate raised: {run.output}"}`;
    exit 0 -> `None`;
    otherwise today's benign-cleanup check and lock-race retry, the retry being a second `_verify_run.run_verify` call with `label=f"{label}:retry"` and its own full `timeout_s`, whose timeout returns the timed-out dict built from the retry run.
    A failure reason is `retry_marker + _truncate_verify_output(output.strip()) + _verify_run.output_suffix(<the run that produced output>)`.
    The `dotnet build-server shutdown` call stays a plain `subprocess.run(["dotnet", "build-server", "shutdown"], capture_output=True, timeout=30)` in the same position (after the first run, on win32 when the command mentions dotnet), unchanged.
    Keep the outer `try`/`except Exception` returning `verify gate raised: {e}`.
    Update the docstring: runner, timeout verdict, `runs`, `label`.
  - `_run_verify_gates(...)` gains the same `timeout_s`, `status_path`, `label`, `runs` keyword parameters; the batch gate gets `label`, the module-wide gate `f"{label}:module-wide"`; both get `timeout_s`, `status_path`, `runs`.
    The `[module-wide verify]` prefix stays and is prepended before any timeout prefix; a module-wide timed-out dict keeps `timed_out: True`.
  Tests in `test-implementer-common.py`:
  - Install one default fake for the whole test run in `main()`: `unittest.mock.patch("_verify_run.run_verify", side_effect=_fake_run_verify)`, where `_fake_run_verify(cmd, **kw)` maps a command of the form `exit <N>` to a `VerifyRun` with `exit_code=N`, empty `output`, `output_path=None`, `first_run=False`, `timed_out=False`, `wall_s=0.0`, `timeout_s=kw["timeout_s"]`, records the call, and for any other command (including `should-not-be-called`) appends it to an `unexpected_commands` list before raising `AssertionError`. Because `_run_verify_gate`'s outer `except Exception` turns that raise into a stuck result, `main()` asserts `unexpected_commands == []` after all cases ran and fails the run when it is not, so an unexpected verify call always fails loudly. Cases needing specific output or a timeout patch locally over it.
    That includes every existing case that today runs a real shell command as its verify (for example the `echo '--- FAIL: TestNew (0.00s)' && exit 1` cases and cases 78-80): give each a local `_verify_run.run_verify` patch returning a `VerifyRun` whose `output` is the echoed text and whose `exit_code` is the command's exit code, preserving the case's assertions.
  - Rewrite every case that patches `_implementer_common.subprocess.run` to drive verify results through a local `_verify_run.run_verify` patch (canned `VerifyRun` records) while asserting the `dotnet build-server shutdown` call through `_implementer_common.subprocess.run`; preserve each case's original intent (pass, fail, benign Windows cleanup, lock-race retry pass and fail, truncation with earlier-failure lines, module-wide prefix).
  - New cases: a timed-out batch gate returns the stuck dict with `timed_out: True` and the `[verify timed out after <N>s: <label>] ` prefix; a timed-out run never triggers the lock-race retry even when its output matches the lock-race signature; the retry run is called with label `<label>:retry`; the module-wide run with `<label>:module-wide`; `runs` collects every run in order; a failure reason ends with the `[verify output: <path>]` suffix; `_truncate_verify_output` matches the old truncation on a >2000-character input.
- **Commit:** `feat(verify): run implementer verify gates through _verify_run`

### Card 7: Thread timeout and label, emit verify_runs, ignore status.md dirt

- **Context:**
  - `plugins/mill/scripts/_verify_run.py`
  - `plugins/mill/scripts/_cleanliness.py`
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Threading: `_forward_output` and `finalize_from_output` gain keyword parameters `verify_timeout_s: float | None = None` and `verify_label: str | None = None`; `finalize_from_output` forwards both.
    Every `_run_verify_gates` call inside `_forward_output` (the explicit-success path and the three no-JSON inference paths) passes `timeout_s=verify_timeout_s`, `status_path=status_path` (the existing parameter), `label=verify_label or "verify"` and the `runs` accumulator below.
    `_fixer_logic_ancestor_override` gains `timeout_s`, `status_path`, `label`, `runs` keyword parameters forwarded to its own `_run_verify_gates` call, and `_forward_output` passes them.
    Document the new parameters in each docstring.
  - Timeout routing: at each of the four `gate_result = _reclassify_verify_failure(...)` sites, skip the reclassification when `gate_result.get("timed_out")` is true, so a timed-out gate always surfaces as `stuck_type: verify` (mill-go's verify self-resolve route), never as `incomplete`/`transient`/`logic`.
  - `verify_runs` chokepoint: rename the current body of `_forward_output` to `_forward_output_body` (same parameters plus a required keyword `verify_runs: list`), unchanged except for the threading above.
    The new `_forward_output` keeps today's public signature (plus the two new parameters), creates `verify_runs = []`, runs `_forward_output_body(...)` inside `contextlib.redirect_stdout(io.StringIO())`, and in a `finally` writes the captured text to the real `sys.stdout` via `_attach_verify_runs(text, verify_runs)`.
    `_attach_verify_runs(text: str, runs: list) -> str`: returns `text` unchanged when `runs` is empty; otherwise, for each line that parses as a JSON object containing a `status` key, adds `"verify_runs": [r.summary() for r in runs]` and re-serialises it with `json.dumps`; other lines pass through unchanged; trailing newlines preserved.
    Envelopes from runs where no verify ran carry no `verify_runs` key.
  - status.md dirt (see the overview's "status.md is excluded from every dirty-tree gate" decision), using `_cleanliness.is_status_md_path` from batch 2:
    `_in_scope_dirty_stuck` drops status.md paths from `owned_paths` (next to the `_is_brief_path` exclusion);
    add `_porcelain_dirt(stdout: str) -> list[str]` returning the non-empty porcelain lines whose path (`line[3:]`) is not status.md, and use `bool(_porcelain_dirt(...stdout))` in place of the `.stdout.strip()` truthiness test at `_fixer_logic_ancestor_override`'s porcelain check and at the inference paths' `result_full` and `result_check` porcelain checks in `_forward_output_body`;
    `_is_formatter_drift_only`'s two `git diff` calls append the pathspec `["--", ":/", ":(top,exclude,glob)**/_mill/status.md"]` so a dirty status.md neither hides nor fakes whitespace drift.
  Tests in `test-implementer-common.py`:
  - `_forward_output` with a passing verify prints an envelope with `verify_runs` holding one entry with the six summary keys; a failing verify's stuck envelope also carries `verify_runs`; a batch plus module-wide pass carries two entries in order; a call with `verify_cmd=None` and `module_wide_verify_cmd=None` prints no `verify_runs` key.
  - `finalize_from_output` forwards `verify_timeout_s` and `verify_label` (the fake sees `timeout_s` and `label`).
  - A timed-out gate on a run where `_reclassify_verify_failure` would otherwise reclassify (partial-batch fixture) still emits `stuck_type: verify` with `timed_out: True`.
  - With a real-git fixture (the file's existing pattern), a dirty `_mill/status.md` alone does not trip `_in_scope_dirty_stuck`, does not stop the snapshot-absent inference path from emitting inferred success, and does not stop `_fixer_logic_ancestor_override` from overriding; `_is_formatter_drift_only` returns true for whitespace-only drift next to a dirty `_mill/status.md`.
  - Existing cases 73-80 and 84a-84e keep passing; where case 79/80 assert "status.md untouched", that remains true because the fake runner writes no row.
- **Commit:** `feat(verify): emit verify_runs and route timeouts in finalize`

## Batch Tests

`verify:` runs `test-implementer-common.py` (all `_implementer_common` behaviour, rewritten onto the `run_verify` seam) and `test-verify-run.py` (the runner it now depends on).
Both pass on this branch once batches 1 and 2 land.
