# Batch: merge-in

```yaml
task: Instrument and bound the verify runner
batch: merge-in
number: 5
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-merge-in-subagent.py test-merge-in-subagent.py test-millpy-verify-run.py test-implementer-common.py
depends-on: [3]
```

## Batch Scope

Moves the merge-in verify sites onto the runner: `millpy-merge-in-subagent.py`'s three verify runs (verify-fix prepare/full initial run, finalize re-run, full post-fix re-run) and a new `millpy-verify-run.py` CLI that `mill-merge-in` step 4 will call instead of running each batch `verify:` bare (the SKILL change is batch 6).
A timed-out merge-in verify never dispatches the verify-fix sub-agent.
Batch-local decision: a launch failure (`exit_code is None`, not timed out) is also routed straight to the stuck envelope without a fixer, since no code change can make a missing binary or cwd start; its reason is `verify gate raised: <message>`, matching `_run_verify_gate`.

## Cards

### Card 10: Merge-in sub-agent runs verify through the runner

- **Context:**
  - `plugins/mill/scripts/_verify_run.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
  - `plugins/mill/unit_tests/test-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Batch 3 added `_implementer_common._truncate_verify_output(text: str) -> str`, the 2000-character truncation with earlier-failure lines (signature inlined, no file read needed).
  In `millpy-merge-in-subagent.py`:
  - Imports: add `import _verify_run`; import `_truncate_verify_output` alongside the existing names from `_implementer_common`; remove the `from _verify_run import _posix_shell_run_args` line batch 1 added and the `subprocess` import once nothing uses it.
  - Add argparse option `--label` (default `"merge-in:verify-fix"`, help: label for the verify runner's log lines and Verify log rows; the SKILL passes `merge-in:<batch>`).
  - In `main()`, right after the second `cfg = _review_common.load_config(project_root, mill_dir)`: resolve `verify_timeout_s = _verify_run.timeout_seconds(cfg)` (on `ValueError` print the message to stderr and `return 1`) and `status_path = _verify_run.resolve_status_path(project_root, cfg)`.
  - Add `_run_merge_verify(cmd: str, label: str, project_root: Path, git_root: Path, timeout_s: float, status_path: Path | None) -> _verify_run.VerifyRun` calling `_verify_run.run_verify(cmd, cwd=project_root, label=label, git_root=git_root, timeout_s=timeout_s, shell_mode="posix", env=_generous_terminal_env(), status_path=status_path)` through the module attribute.
    It replaces all three `subprocess.run(_run_args, capture_output=True, text=True, cwd=project_root, env=_generous_terminal_env(), **_run_kwargs)` verify calls.
    Thread `git_root`, `verify_timeout_s` and `status_path` into `_run_verify_fix` as new keyword parameters.
  - Add `_verify_stuck_envelope(run) -> dict | None` returning, for a timed-out run, `{"status": "stuck", "stuck_type": "verify", "timed_out": True, "reason": _verify_run.timeout_prefix(run) + _truncate_verify_output(run.output.strip()) + _verify_run.output_suffix(run)}`; for a launch failure `{"status": "stuck", "stuck_type": "verify", "reason": f"verify gate raised: {run.output}"}`; otherwise `None`.
  - Initial verify in `_run_verify_fix` (label `args.label`): when `_verify_stuck_envelope(run)` is not `None`, print it with `verify_runs` and `return 0` before any `emit_prepare` (prepare stage) or `_implementer_claude.run` (full stage) -- the fixer is never dispatched for a timeout or launch failure.
  - Re-verify in the finalize stage and the full-stage post-fix re-verify use label `f"{args.label}:post-fix"`; a timeout or launch failure there prints the same stuck envelope shape.
  - Every success or stuck envelope this file prints after a verify run carries `"verify_runs": [r.summary() for r in runs]` for the runs made in that invocation; the plain failure envelope's reason becomes `_truncate_verify_output(run.output.strip()) + _verify_run.output_suffix(run)`, matching the overview's "every failure reason uses one shape" decision (the verify-fix brief's `VERIFY_OUTPUT` token keeps the full `run.output.strip()`, since the fixer needs the whole log).
    The two prepare-envelope helpers in `_implementer_common.py`, `emit_prepare(...)` and `emit_prepare_no_dispatch(...)`, each gain a keyword-only `verify_runs: list[dict] | None = None` parameter, added to the printed envelope as `"verify_runs"` when not `None` (docstrings updated; existing callers unchanged).
    The verify-fix prepare stage passes `verify_runs=[r.summary() for r in runs]` to both, so a prepare-stage verify that passes or leads to dispatch still reports its timing.
  Tests: in `test-millpy-merge-in-subagent.py` and `test-merge-in-subagent.py`, replace the `subprocess.run` mocks that fake verify results with `_verify_run.run_verify` patches returning canned `VerifyRun` records (keep any `subprocess.run` / `_subprocess_util.run` mocks that serve git), preserving each case's intent.
  The two `_generous_terminal_env` dispatch cases (#1068) assert the `env=` keyword on the `run_verify` call instead of on `subprocess.run`.
  New cases: a prepare-stage verify that passes prints the no-dispatch envelope with `verify_runs`; one that fails prints the dispatch envelope with `verify_runs`; prepare-stage timed-out initial verify prints a stuck envelope with `timed_out: true`, the `[verify timed out after <N>s: merge-in:...]` prefix and `verify_runs`, and `emit_prepare` is not called; full-stage timed-out initial verify never calls `_implementer_claude.run`; a finalize-stage post-fix timeout prints the stuck envelope; `--label` reaches `run_verify` and the post-fix run uses `<label>:post-fix`; a config with `pipeline.verify_timeout_minutes: 0` makes `main` return 1.
- **Commit:** `feat(verify): run merge-in verify through _verify_run, skip the fixer on timeout`

### Card 11: millpy-verify-run CLI

- **Context:**
  - `plugins/mill/scripts/_verify_run.py`
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/millpy-verify-run.py`
  - `plugins/mill/unit_tests/test-millpy-verify-run.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Create `plugins/mill/scripts/millpy-verify-run.py` with a module docstring in the style of `millpy-merge-in-subagent.py` (purpose, flags, exit codes, one-line JSON output) and `main(argv=None) -> int` behind `if __name__ == "__main__": sys.exit(main())`.
  Flags (all required): `--label`, `--cmd`, `--cwd`.
  Steps: `git_root = _paths.resolve_git_root()`, `hub_root = _paths.resolve_hub_path()`, `cfg = _config.load_config(hub_root, git_root)`; `timeout_s = _verify_run.timeout_seconds(cfg)` -- on `ValueError` print `json.dumps({"label": label, "cmd": cmd, "reason": str(exc)})` and return 1; `status_path = _verify_run.resolve_status_path(hub_root, cfg)`; `run = _verify_run.run_verify(cmd, cwd=Path(args.cwd), label=label, git_root=git_root, timeout_s=timeout_s, shell_mode="posix", status_path=status_path)`.
  Print one JSON line: `label`, `cmd`, `exit_code`, `wall_s`, `first_run`, `timed_out`, `output_path` (string or `null`), `verify_runs` (`[run.summary()]`), plus `reason` when the run did not pass -- `_verify_run.timeout_prefix(run) + _truncate_verify_output(run.output.strip()) + _verify_run.output_suffix(run)` on timeout, `f"verify gate raised: {run.output}"` on launch failure, `_truncate_verify_output(run.output.strip()) + _verify_run.output_suffix(run)` on a non-zero exit (`_truncate_verify_output` imported from `_implementer_common`, its signature inlined in card 10, no file read needed).
  Return 0 when `exit_code == 0`, else 1.
  Tests in `test-millpy-verify-run.py` (script style; in-process `main([...])` with `_paths.resolve_git_root`, `_paths.resolve_hub_path` and `_config.load_config` patched to a temp dir and fixture cfg; real short-lived children run as `"<sys.executable as posix path>" <script written to the temp dir>`): pass -> exit 0 and the JSON keys above without `reason`; non-zero -> exit 1 with `reason` ending in `[verify output: <path>]`; timeout (`pipeline.verify_timeout_minutes: 0.02`, child sleeping 30 s) -> exit 1, `timed_out: true`, reason starting `[verify timed out after 1s: <label>] `; invalid timeout -> exit 1 with `reason` naming `pipeline.verify_timeout_minutes`; a temp `_mill/status.md` gains one `## Verify log` row per run.
- **Commit:** `feat(verify): add millpy-verify-run CLI for merge-in replays`

## Batch Tests

`verify:` runs `test-millpy-merge-in-subagent.py` and `test-merge-in-subagent.py` (both pass on this branch's base and are rewritten onto the `run_verify` seam) plus the new `test-millpy-verify-run.py`, and `test-implementer-common.py` because card 10 adds a keyword parameter to `emit_prepare` / `emit_prepare_no_dispatch`.
