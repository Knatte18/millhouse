# Batch: baseline-short-circuit

```yaml
task: "_plan_validate and baseline verify gate gaps"
batch: "baseline-short-circuit"
number: 2
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-verify-baseline.py test-millpy-implement.py test-millpy-fix.py
depends-on: []
```

## Batch Scope

Treat a short-circuited compound (`&&`) per-batch verify baseline as "unknown" (#1144): detect it in `_verify_baseline.py`, propagate `None` through `compute_batch_baselines`, and make the `--stage baseline` driver in `millpy-implement.py` leave `verify_baseline_failures` unset for that batch so downstream gates fall back to the strict path.
The downstream holistic union in `millpy-fix.py` already skips falsy values, so it needs no source change, only a regression test.
One batch because the three cards form one behavior chain (detector, driver, downstream union).

## Cards

### Card 3: short-circuit detector and None propagation in _verify_baseline

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_verify_baseline.py`
  - `plugins/mill/unit_tests/test-verify-baseline.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Add `_is_short_circuit_baseline(command: str, signatures: list[str]) -> bool` (signature inlined) to `_verify_baseline.py`: True exactly when the substring `&&` appears in `command`, `signatures` is non-empty, and every entry of `signatures` starts with `NONZERO_EXIT:`; no shell parsing.
  - `_signatures_for_pair` return type becomes `list[str] | None`: after its run loop, return `None` when `_is_short_circuit_baseline(command, signatures)` is True, else `signatures`; update its docstring's Returns section.
  - `compute_batch_baselines`: widen the `pair_cache` parameter annotation to `dict[tuple[str, Path], list[str] | None] | None` and the return annotation to `dict[str, list[str] | None]`; keep the `pair not in by_pair` test so a cached `None` is not recomputed; replace `results[name] = list(by_pair[pair])` with a version that passes `None` through unchanged and copies a list.
  - Update the module docstring's Public API entry and the function docstring's Args and Returns text to describe the `None` "unknown" value.
  - In `test-verify-baseline.py`, case (o)'s first half uses the compound command `go vet ./... && go test ./...` and expects a synthetic signature list; with the new detection that input yields `None`.
  - Change that first half to the non-compound command `go vet ./...` (same output, same expected list) and update the case's docstring and the module header line describing case (o) to say so.
  - Add a new case (p), registered in `main()`, using `patch("_verify_baseline._run_verify_in", ...)` like the neighbouring cases.
  - Case (p) sub-cases: a compound `a && b` returning `(1, "")` on both runs yields `None`; the same compound with output containing a real marker line (`--- FAIL: TestX (0.01s)`) yields the unchanged list; a non-compound failing command yields the unchanged `NONZERO_EXIT` list; a green compound (`(0, "ok\n")`) yields `[]`; `_is_short_circuit_baseline` truth table (no `&&`, empty list, mixed synthetic and marker entries, all synthetic with `&&`, `&&` inside a quoted `sh -c "..."` body); a caller-owned `pair_cache` holding `None` for a pair is honoured on a second `compute_batch_baselines` call (the fake `_run_verify_in` is not called again) and two names sharing the pair both map to `None`.
- **Commit:** fix(verify-baseline): treat short-circuited compound per-batch baseline as unknown

### Card 4: baseline driver skips unknown batches and guards seeding

- **Context:**
  - `plugins/mill/scripts/_verify_baseline.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/unit_tests/test-millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In `_run_per_batch_baseline_standalone`, widen the local `pair_cache` annotation to `dict[tuple[str, Path], list[str] | None]`.
  - Step 5 seeding: only seed `pair_cache[(seed_cmd, seed_cwd)]` when `not _verify_baseline._is_short_circuit_baseline(seed_cmd, seed_signatures)`; otherwise skip the seed so the batch computes its own result.
  - Step 6 driver: after `compute_batch_baselines` returns, when `batch_result[name] is None`, print an ASCII stderr line `[millpy-implement] per-batch baseline for <name!r> left unset: compound verify short-circuited` and `continue` without calling `_status.set_batch_field` and without incrementing `captured_count`; a written `None` would count as captured for the key-presence idempotence check, so the key must stay absent.
  - Update the step 5 and step 6 comments and the function docstring to state the "unknown -> key stays absent -> retried next invocation, strict gate meanwhile" behavior.
  - Add unittest methods to `TestMillpyImplement` in `test-millpy-implement.py`, mirroring the fixture style of `test_baseline_stage_per_batch_capture_driver_isolates_timeout` (overview plus per-batch files, batch-status seeding, patched `_baseline_preflight_skip_reason` and `_verify_baseline._run_verify_in`, `_run_main(["--stage", "baseline"])`).
  - Test 1: two batches, one with verify `false && true` whose fake run returns `(1, "")` and one with a plain green verify; assert the compound batch has no `verify_baseline_failures` key, the plain batch has `[]`, and the per_batch JSON line's `value` is 1.
  - Test 2 (seed guard): module-wide verify and one batch verify are the identical compound string; patch `millpy_implement._verify_baseline.compute_baseline` to return `("pre-existing-failures", ["NONZERO_EXIT: exit 1: (no output)"])` and `_run_verify_in` to return `(1, "")`; assert the batch's key stays absent and `_run_verify_in` was called for the batch command (the seed was not used).
  - Test 3 (seed still used): same setup but a non-compound identical command and a seed of `["--- FAIL: TestX (0.01s)"]`; assert `_run_verify_in` is not called for the batch and the batch's key equals the seed list.
  - Run the whole of `test-millpy-implement.py` and confirm the existing baseline tests still pass.
- **Commit:** fix(implement): leave short-circuited compound baseline unset and do not seed it

### Card 5: holistic union regression test for a None-baseline batch

- **Context:**
  - `plugins/mill/scripts/millpy-fix.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-fix.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - No source change: the holistic branch of `millpy-fix.py` already builds `_union_baseline` from only truthy `verify_baseline_failures` values and passes `batch_verify_baseline=sorted(...)` to `finalize_from_output`.
  - Add a `TestMillpyFix` method mirroring `test_holistic_finalize_status_path_filters_pending_batch_and_logs_skip` (same overview layout, patched `finalize_from_output` capturing kwargs, `--scope holistic --stage finalize`), but with both batches approved via `set_batch_field(..., "state", "approved")`.
  - Give `batch1` a recorded `verify_baseline_failures` list (`["--- FAIL: TestA (0.01s)"]`) via `_status.set_batch_field` and leave `batch2` with the key absent (the "unknown" state card 4 produces).
  - Assert the captured `batch_verify_baseline` kwarg equals exactly `["--- FAIL: TestA (0.01s)"]`.
  - Add a second assertion in the same method or a sibling method: when neither batch has the key, `batch_verify_baseline` is `None`.
- **Commit:** test(fix): cover holistic baseline union with an unknown-baseline batch

## Batch Tests

`verify:` runs `run-all.py --only` over `test-verify-baseline.py` (card 3), `test-millpy-implement.py` (card 4) and `test-millpy-fix.py` (card 5), the three files this batch edits.
`test-millpy-implement.py` is large, but every test file in the scope is one a card here edits, so nothing broader is justified.
