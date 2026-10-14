# Batch: gate-callers

```yaml
task: Instrument and bound the verify runner
batch: gate-callers
number: 4
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-implement.py test-millpy-fix.py test-fix-finalize.py test-done-gate.py
depends-on: [3]
```

## Batch Scope

Wires the remaining in-process verify callers to the runner: `millpy-implement.py` and `millpy-fix.py` resolve the timeout once and pass it, with a label, into `finalize_from_output` / `_forward_output`; `_done_gate.run_preflight` / `run_gate` resolve config themselves and run through `_verify_run.run_verify` with `shell_mode="native"`.
Batch 6 changes the SKILL snippets that call these.
Batch-local decision: `_done_gate` calls the runner as `_verify_run.run_verify(...)` through the module attribute, so tests patch `_verify_run.run_verify`.

## Cards

### Card 8: Implementer and fixer CLIs pass timeout and label

- **Context:**
  - `plugins/mill/scripts/_verify_run.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/scripts/millpy-fix.py`
  - `plugins/mill/unit_tests/test-millpy-implement.py`
  - `plugins/mill/unit_tests/test-millpy-fix.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Batch 3 gave `finalize_from_output(...)` and `_forward_output(...)` two new keyword parameters, `verify_timeout_s: float | None = None` and `verify_label: str | None = None` (signature inlined, no file read needed).
  In both CLIs add `import _verify_run`.
  Immediately after the second `cfg = _review_common.load_config(project_root, mill_dir)` (the reload after `_paths.resolve_active_hub`), resolve `verify_timeout_s = _verify_run.timeout_seconds(cfg)` inside `try`; on `ValueError` print the message to stderr and `return 1`, before any stage-specific work, so an invalid `pipeline.verify_timeout_minutes` fails the invocation loudly.
  `millpy-implement.py`: pass `verify_timeout_s=verify_timeout_s, verify_label=args.batch_name` to its `finalize_from_output(...)` call (finalize stage) and its `_forward_output(...)` call (full stage) -- signatures inlined above, no file read needed.
  `millpy-fix.py`: pass `verify_timeout_s=holistic_timeout_s, verify_label=f"fix:{args.scope}"` to its `finalize_from_output(...)` and `_forward_output(...)` calls -- signatures inlined above, no file read needed.
  `holistic_timeout_s = verify_timeout_s * max(1, len(batch_verifies))`, computed at both sites right after the existing `batch_verifies = _plan_dag.iter_batch_verifies(...)` call: `_resolve_holistic_verify` joins every batch's command into one `" && "` chain that runs as a single runner command, so the per-command budget is scaled by the number of joined commands (see the overview's "holistic fixer replay budget" decision).
  Add a one-line comment at each site saying so.
  Tests: in `test-millpy-implement.py` and `test-millpy-fix.py`, extend the existing `finalize_from_output` / `_forward_output` capture cases (signatures inlined above, no file read needed) to assert the two new keyword arguments (1200.0 with the default config for the implementer, and 1200.0 times the number of contributing batches for the fixer; the batch name, respectively `fix:<scope>`), and add one case per CLI where the loaded config carries `pipeline.verify_timeout_minutes: 0` and the CLI returns 1 with the key named on stderr.
  Any existing case whose path now reaches `_verify_run.run_verify` with a real command patches `_verify_run.run_verify` (canned `VerifyRun`) instead of relying on `subprocess.run` mocks.
- **Commit:** `feat(verify): thread verify timeout and label from implement and fix CLIs`

### Card 9: Done gate runs through the shared runner

- **Context:**
  - `plugins/mill/scripts/_verify_run.py`
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/_done_gate.py`
  - `plugins/mill/unit_tests/test-done-gate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Change `run_preflight(gate_cmd, git_root, *, hub_root: Path | None = None) -> dict` and `run_gate(gate_cmd, git_root, *, hub_root: Path | None = None) -> dict`; positional shape and never-raise contract unchanged.
  Inside the existing `try` of each (after `run_preflight`'s `gate_cmd is None` -> `skipped` check, which stays first and untouched): `hub = hub_root if hub_root is not None else _paths.resolve_hub_path(git_root)`, `cfg = _config.load_config(hub, git_root)`, `timeout_s = _verify_run.timeout_seconds(cfg)`, `status_path = _verify_run.resolve_status_path(hub, cfg)`, then `run = _verify_run.run_verify(gate_cmd, cwd=git_root, label=<"done-gate-preflight" for run_preflight, "done-gate" for run_gate>, git_root=git_root, timeout_s=timeout_s, shell_mode="native", status_path=status_path)`.
  Any exception in that block, including the invalid-timeout `ValueError`, returns `{"result": "blocked", "reason": str(exc)}`.
  Results (each `ok`/`blocked` dict produced after a run carries `"verify_runs": [run.summary()]`; `skipped` and the exception path carry none):
  timed out -> `blocked` with reason `_verify_run.timeout_prefix(run) + _build_truncated_reason(run.output.strip()) + _verify_run.output_suffix(run)`;
  launch failure (`exit_code is None`) -> `blocked` with reason `run.output`;
  non-zero exit -> `blocked` with reason `_build_truncated_reason(run.output.strip()) + _verify_run.output_suffix(run)`;
  exit 0 -> `ok`.
  `run_gate`'s best-effort Windows `dotnet build-server shutdown` on success stays a plain `subprocess.run(["dotnet", "build-server", "shutdown"], capture_output=True, timeout=30)`, unchanged.
  Update the module docstring's Public API section and both function docstrings (runner, `hub_root`, timeout, `verify_runs`).
  Tests in `test-done-gate.py`: rewrite the cases that patch `_done_gate.subprocess.run` for the gate command to patch `_verify_run.run_verify` (canned `VerifyRun`) and `_config.load_config` (fixture cfg), keeping `_done_gate.subprocess.run` patches only to assert the dotnet shutdown call and `_done_gate.platform.system`.
  Cover: `skipped` unchanged and runner never called; `ok` with `verify_runs`; non-zero `blocked` with truncation, suffix and `verify_runs`; timeout `blocked` with the prefix; launch failure `blocked`; an invalid `pipeline.verify_timeout_minutes` (e.g. `-5`) yields `blocked` naming the key, never an exception; `shell_mode="native"` and the two labels are passed; `hub_root` is forwarded to `_config.load_config` when given; `run_gate`'s shutdown call still happens on Windows success only.
- **Commit:** `feat(verify): run the done gate through _verify_run`

## Batch Tests

`verify:` runs `test-millpy-implement.py`, `test-millpy-fix.py`, `test-fix-finalize.py` (fixer finalize end-to-end, which now carries the new keyword arguments) and `test-done-gate.py`.
All pass on this branch's base; this batch's changes are covered by the cases listed in each card.
