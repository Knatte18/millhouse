# Batch: fix-finalize-strict

```yaml
task: "Drop the eager verify-baseline pre-flight"
batch: "fix-finalize-strict"
number: 2
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-fix.py test-fix-finalize.py
depends-on: []
```

## Batch Scope

Makes the holistic fixer's finalize verify replay strict: `millpy-fix.py` stops reading `module_verify_baseline` and the per-batch `verify_baseline_failures` union and stops passing both to `finalize_from_output` (discussion Decision `fix-finalize-forwarding-removed`).
The module-wide verify derivation stays.
Independent of batches 1 and 3; batch 4 depends on it because `_status.get_module_verify_baseline` goes away there.

## Cards

### Card 3: Stop forwarding cached baselines from millpy-fix.py holistic finalize

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-fix.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In `main()`'s `if args.stage == "finalize":` branch:
    - Replace the six-line comment that starts `# Module-wide verify derivation, mirroring millpy-implement.py's main(): read the` with a comment that justifies the derivation on its own terms, e.g. `# Module-wide verify derivation, mirroring millpy-implement.py's main(): the fixer's verify replay runs the overview's module-wide verify after the joined batch verify, exactly as the implementer dispatch does.` (one or two lines, semantic line breaks).
    - Keep `overview_frontmatter = ...` and the `module_wide_verify_cmd, module_wide_cwd_override = _plan_dag.parse_verify_field(...)` derivation unchanged.
    - Delete `module_verify_baseline = _status.get_module_verify_baseline(status_path)`.
    - Delete `batch_verify_baseline = None`.
    - Delete the `# Union every contributing batch's cached verify-baseline failure set, ...` comment block and the code under it through `batch_verify_baseline = sorted(_union_baseline) if _union_baseline else None` (`_all_batches_status`, `_union_baseline`, the `for _bv_name, _bv_cmd, _bv_cwd in batch_verifies:` loop).
    - Drop the `module_verify_baseline=module_verify_baseline,` and `batch_verify_baseline=batch_verify_baseline,` keyword arguments from the `finalize_from_output(...)` call.
  - Then apply the overview's `unused-import-check` Decision to this file (`_status` is still used elsewhere in `millpy-fix.py`; keep it if so).
- **Commit:** `refactor(fix): gate holistic finalize strictly, drop cached-baseline forwarding`

### Card 4: Update fixer finalize tests

- **Context:**
  - `plugins/mill/scripts/millpy-fix.py`
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-fix.py`
  - `plugins/mill/unit_tests/test-fix-finalize.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - `test-millpy-fix.py`: replace `test_holistic_finalize_baseline_union_skips_unknown_baseline_batch` with `test_holistic_finalize_forwards_no_baseline_kwargs`.
    Reuse its fixture and its `run_holistic_finalize()` helper shape, including a status.md batch entry that still carries a legacy `verify_baseline_failures` value, and assert the captured `finalize_from_output` kwargs contain neither `module_verify_baseline` nor `batch_verify_baseline` — while `module_wide_verify_cmd` and `verify_cmd` are still forwarded as before.
    Drop any `_status.set_batch_field(..., "verify_baseline_failures", ...)` call from that test: batch 4 makes it raise, so write the legacy key directly into the status.md fixture text instead.
  - `test-fix-finalize.py`: rewrite `Test 7` (the `--scope holistic forwards batch_verify_baseline as the sorted union ...` block) into a test that `--scope holistic` finalize calls `finalize_from_output` without `module_verify_baseline` / `batch_verify_baseline` kwargs.
    Remove its `mock_modules["_status"].get_module_verify_baseline = ...` stub and the `verify_baseline_failures` entries in its `read_batches` stub.
    Update its comment header and PASS/FAIL messages to match.
  - After this card, grep both files for `verify_baseline`, `get_module_verify_baseline`, `_union_baseline` and confirm the only surviving hits are the `assertNotIn`-style absence checks and the legacy-key fixture text.
- **Commit:** `test(fix): assert holistic finalize forwards no baseline kwargs`

## Batch Tests

`verify:` runs `test-millpy-fix.py` and `test-fix-finalize.py`, both green on the task branch tip before this batch.
Together they cover the finalize kwargs `millpy-fix.py` now forwards.
