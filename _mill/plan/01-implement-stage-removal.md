# Batch: implement-stage-removal

```yaml
task: "Drop the eager verify-baseline pre-flight"
batch: "implement-stage-removal"
number: 1
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-implement.py
depends-on: []
```

## Batch Scope

Removes `--stage baseline` and everything that serves only it from `millpy-implement.py`, and stops the finalize and full stages from reading or forwarding the cached baselines.
After this batch, `millpy-implement.py` no longer imports `_verify_baseline`, no longer calls any `_status` module-baseline function, and no longer reads or writes the `verify_baseline_failures` batch field — which is what lets batch 4 delete those.
`finalize_from_output` / `_forward_output` keep their `module_verify_baseline` / `batch_verify_baseline` parameters until batch 5; they default to `None`, so omitting them here is already strict.

## Cards

### Card 1: Remove --stage baseline from millpy-implement.py

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Delete the `import _verify_baseline` line.
  - Delete these module-level functions in full (each was confirmed by grep across `plugins/mill/scripts` to have no caller outside this baseline call chain): `_baseline_exclusion_prefixes`, `_baseline_preflight_skip_reason`, `_porcelain_snapshot`, `_warn_new_dirt`, `_module_wide_skip_or_cached_payload`, `_run_module_wide_standalone`, `_run_per_batch_baseline_standalone`, `_run_baseline_stage`.
    Re-grep the file for each name after deleting to confirm no reference survives.
  - In `main()`'s argparse setup:
    - `batch_name` becomes a plainly required positional: drop `nargs="?"` and `default=None`, and change its help to `"Batch name from the plan overview's Batch Index."`.
    - `--stage` choices become `["prepare", "finalize", "full"]`; drop the `, or baseline (compute/cache the task-scoped module-wide verify baseline)` clause from its help so it reads `"Stage of execution: prepare (render brief), finalize (process output), or full (default, unchanged behavior)."`.
    - Delete the `if args.stage != "baseline" and not args.batch_name:` block (its print and `return 1`); argparse now rejects a missing `batch_name` itself.
  - Delete the comment line beginning `# Read here -- before the batches/batch_entry resolution below` above the `overview_frontmatter = ...` read; keep the other comment lines and the `module_wide_verify_cmd, module_wide_cwd_override = _plan_dag.parse_verify_field(...)` derivation unchanged.
  - Delete the `module_verify_baseline = _status.get_module_verify_baseline(status_path)` line and its preceding `# Cached task-scoped baseline read once here ...` comment.
  - Delete the whole `if args.stage == "baseline":` block (the `pipeline.baseline_verify_timeout_minutes` read and the `_run_baseline_stage(...)` return).
  - In the `if args.stage == "finalize":` branch: delete the `batch_verify_baseline = batch_status.get("verify_baseline_failures")` line and its `# Cached, task-scoped per-batch verify baseline ...` comment, and drop the `module_verify_baseline=module_verify_baseline,` and `batch_verify_baseline=batch_verify_baseline,` keyword arguments from the `finalize_from_output(...)` call.
  - In the full-stage tail of `main()`: delete the `# Cached, task-scoped per-batch verify baseline (see batch 3/5/6), read fresh here ...` comment, the `_full_stage_batches = ...` / `_full_stage_batch_entry = ...` lookup and the `batch_verify_baseline = (...)` assignment, and drop the same two keyword arguments from the final `_forward_output(...)` call.
  - Leave the unrelated cleanliness-snapshot "baseline" comments (module docstring `--resume-incomplete` paragraph, the `snapshot_path` and housekeeping-commit comments) untouched.
  - Then apply the overview's `unused-import-check` Decision to this file.
- **Commit:** `refactor(implement): remove --stage baseline and cached-baseline forwarding`

### Card 2: Update millpy-implement tests for the removed stage

- **Context:**
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In `TestMillpyImplement`, delete every `test_baseline_stage_*` method and the fixture helpers used only by them: `_write_two_batch_fixture`, `_write_baseline_plan`, `_write_overview_with_module_wide_verify` (grep each helper name first; delete a helper only when every remaining caller is a deleted test).
  - Delete the classes `TestBaselinePreflightSkipReason` and `TestWarnNewDirt` in full.
  - Remove any remaining `unittest.mock.patch.object(millpy_implement._status, "get_module_verify_baseline", ...)` or `_baseline_preflight_skip_reason` patch in a surviving test; after this card, grep the file for `baseline_preflight`, `get_module_verify_baseline`, `verify_baseline_failures`, `_verify_baseline`, `"--stage", "baseline"` and confirm zero hits.
  - Add `test_stage_baseline_rejected_by_argparse` to `TestMillpyImplement`: `self._run_main(["test-batch", "--stage", "baseline"])` raises `SystemExit` with `code == 2` (patch `sys.stderr` with an `io.StringIO` to keep output quiet).
  - Add `test_missing_batch_name_errors_for_every_stage`: for each of `"prepare"`, `"finalize"`, `"full"` (as `subTest`), `self._run_main(["--stage", stage])` raises `SystemExit` with `code == 2`.
  - In the existing finalize-stage tests that patch `finalize_from_output` and read `mock_finalize.call_args.kwargs` (e.g. `test_overview_verify_cwd_hub_resolves_module_wide_cwd_override`), add `assertNotIn("module_verify_baseline", call_kwargs)` and `assertNotIn("batch_verify_baseline", call_kwargs)` to at least one of them.
  - In the test that patches `_forward_output` with `_fake_forward_output` (full stage), assert the captured kwargs contain neither `module_verify_baseline` nor `batch_verify_baseline`.
- **Commit:** `test(implement): drop baseline-stage tests, assert strict stage and kwargs`

## Batch Tests

`verify:` runs `test-millpy-implement.py` (green on the task branch tip before this batch).
It covers the argparse changes, the finalize/full forwarding, and confirms nothing in the file still references the deleted helpers.
