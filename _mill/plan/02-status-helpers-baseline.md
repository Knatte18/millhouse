# Batch: status-helpers-baseline

```yaml
task: "mill-go-base: orchestration robustness gaps"
batch: status-helpers-baseline
number: 2
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-status.py test-verify-baseline.py
depends-on: [1]
```

## Batch Scope

Adds the two pure-Python primitives batch 3 (fixing #1031) needs: a small `status.md` persistence trio (`set_baseline_preflight_log`/`get_baseline_preflight_log`/`clear_baseline_preflight_log`) in `_status.py`, and a `--module-wide-only` flag on `millpy-implement.py --stage baseline` that skips the per-batch substage entirely. Grouped into one batch (rather than two) because both serve the same downstream fix (#1031) and together stay well under the context cap: card 3 costs ≈33,830 tokens (`_status.py` + `test-status.py`), card 4 costs ≈16,175 tokens (`millpy-implement.py` + `test-verify-baseline.py`), total ≈50,005. `depends-on: [1]` is not a real feature dependency (this batch's cards are independent of batch 1's) — it exists purely to serialize the two batches, since both edit `_status.py` and `test-status.py`; the validator's `parallel-modifies-overlap` check requires an explicit edge whenever two DAG-parallel-eligible batches touch the same file.

## Cards

### Card 3: `baseline_preflight_log` persistence helpers

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/unit_tests/test-status.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add three functions to `_status.py`, mirroring the existing `set_module_verify_baseline`/`get_module_verify_baseline` pair (same file) as the direct template for shape and mechanics:
  - `set_baseline_preflight_log(status_path: Path, log_path: str) -> None` — writes a `baseline_preflight_log:` row in the top yaml block (value quoted via the same `quote_scalar` helper `set_module_verify_baseline` already uses). If the row already exists, rewrite it in place; otherwise insert a new row immediately after the `parent:` row — reuse `set_module_verify_baseline`'s existing insert-in-place-or-after-`parent:` scan logic as the template, adapted to the new field name. Unlike `set_module_verify_baseline`, this function takes no restricted-value-set check — `log_path` is an arbitrary path string, not a two-state enum.
  - `get_baseline_preflight_log(status_path: Path) -> str | None` — reads the `baseline_preflight_log:` row back (quotes stripped), returning `None` if the row is absent. Mirror `get_module_verify_baseline`'s existing read pattern.
  - `clear_baseline_preflight_log(status_path: Path) -> None` — deletes the `baseline_preflight_log:` row from the top yaml block if present; a no-op (no exception) if the row is already absent. Mirror `append_phase`'s existing `blocked_reason:`-row-deletion scan (same file), adapted to always delete this row rather than deleting conditionally on the new phase value.
  Add docstrings for all three modeled on `set_module_verify_baseline`/`get_module_verify_baseline`'s existing docstring shape and level of detail, noting these persist the log path of a speculatively-launched "0.5. Baseline pre-flight" job across a `/mill-go` session restart (see batch 3's edit to `mill-go-base/SKILL.md`'s "Entry-gate wait for upstream mill-plan" section).
  Add two test functions to `plugins/mill/unit_tests/test-status.py`, reusing that file's existing fixture conventions for `set_module_verify_baseline`/`get_module_verify_baseline`'s own tests (locate and reuse the same fixture-building helpers):
  - `test_set_baseline_preflight_log_insert_and_overwrite`: call `set_baseline_preflight_log` on a fixture with no existing row; assert `get_baseline_preflight_log` returns the written value. Call `set_baseline_preflight_log` again with a different value on the same fixture; assert the row was overwritten in place (still exactly one `baseline_preflight_log:` row in the file, not two).
  - `test_clear_baseline_preflight_log_removes_row`: set a value, call `clear_baseline_preflight_log`, assert `get_baseline_preflight_log` now returns `None`. Call `clear_baseline_preflight_log` again on the now-absent row and assert no exception is raised.
- **Commit:** `status: add baseline_preflight_log persistence helpers`

### Card 4: `--module-wide-only` flag for `--stage baseline`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/unit_tests/test-verify-baseline.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a `--module-wide-only` boolean CLI flag (argparse `action="store_true"`, default `False`) to `millpy-implement.py`'s `--stage baseline` argument handling. Inside `_run_baseline_stage`, when this flag is set, the per-batch loop (`for name, command, cwd in batches_needing_computation:`, currently the block that calls `_verify_baseline.compute_batch_baselines(...)` then `_status.set_batch_field(status_path, name, "verify_baseline_failures", failures)` per batch, each iteration wrapped in its own `try/except` that records failures into an `errored` dict) must be skipped entirely — no iteration, no `_status.set_batch_field` call of any kind, no per-batch verify replay of any kind. The module-wide substage (the `if module_wide_needs_computation:` block immediately above the per-batch loop, which calls `_verify_baseline._run_module_wide_verify_algorithm` and `_status.set_module_verify_baseline`) must still run exactly as it does today, completely unaffected by this flag.
  This matters because at the point `--module-wide-only` is actually used (a speculative early launch during mill-go's entry-gate wait, before `## Prepare` has ever run `_status.init_batches`), `status.md` has no `## Batches` section on disk yet — `_status.set_batch_field` unconditionally raises `ValueError: Batch {name!r} not present in ## Batches` when the named batch isn't found, so running the per-batch loop at that point would silently discard the (potentially slow) verify-replay work into every batch's `errored` dict for zero caching benefit. Skipping the loop entirely (rather than letting it run and fail) avoids paying that verify-replay cost at all when it's known in advance to be useless.
  The existing per-batch JSON summary line (currently printed with shape `{"stage": "baseline", "substage": "per_batch", "computed": [...], "cached": [...], "errored": {...}}`) must still print exactly once when `--module-wide-only` is set, with `"computed": [], "cached": [], "errored": {}` — all three lists/dicts empty — so any downstream consumer parsing the documented two-JSON-line-per-invocation contract does not break on a missing second line. This is a distinct, empty-but-present line, not an omitted one.
  Add `test_stage_baseline_module_wide_only_skips_per_batch_loop` to `plugins/mill/unit_tests/test-verify-baseline.py` — first read the existing test functions in that file to identify its fixture conventions for invoking `--stage baseline` (config, worktree, status.md fixtures) and match them. The new test invokes the baseline stage with `--module-wide-only` against a fixture `status.md` that has NO `## Batches` section at all (simulating the pre-`## Prepare` scenario) and asserts: (a) the call completes without raising; (b) the printed per-batch JSON line has `computed: []`, `cached: []`, `errored: {}`; (c) when the fixture's config declares a module-wide verify command, the module-wide substage's own result is still written to `status.md`'s `module_verify_baseline:` field (confirming the module-wide half is genuinely unaffected by the flag).
- **Commit:** `implement: add --module-wide-only flag to --stage baseline`

## Batch Tests

`verify:` runs `run-all.py --only test-status.py test-verify-baseline.py` — the two files this batch's cards touch (card 3 adds tests to `test-status.py`; card 4 adds a test to `test-verify-baseline.py`), scoped per the "Multiple files" `--only` pattern rather than the unbounded full suite.
