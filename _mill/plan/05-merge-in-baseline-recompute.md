# Batch: merge-in-baseline-recompute

```yaml
task: 'compute_baseline: use the task worktree''s own pre-edit state, not a parent-branch checkout'
batch: merge-in-baseline-recompute
number: 5
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-merge-in-subagent.py && PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/test-baseline-waiver.py
depends-on: [2]
```

## Batch Scope

This batch updates `millpy-merge-in-subagent.py --recompute-baseline` for the new `compute_baseline` signature (batch 2) and adds the unconditional per-batch `verify_baseline_failures` clearing Decision `merge-in-batch-baseline-staleness` requires, since `_corroborate_batch_failure` (deleted in batch 4) is what previously masked this staleness. This batch depends only on batch 2, not batch 4. `millpy-merge-in-subagent.py` does call `_forward_output`/`finalize_from_output` (in `_run_conflicts`'s conflicts-mode finalize branch, `:425` and `:498`) — but neither call site passes `batch_name`, `git_name`, or `git_email`, relying on those parameters' defaults, so batch 4's removal of them does not change either call site's behavior. Batch 5 has no coupling to batch 4's parameter removals for that reason, not because the file never calls these functions.

## Cards

### Card 27: Rewrite _run_recompute_baseline

- **Context:**
  - `plugins/mill/scripts/_verify_baseline.py`
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_run_recompute_baseline`, move the "clear every batch's `verify_baseline_failures`" step to run FIRST — before the `module_wide_verify_cmd is None` skip-and-return and before the two error early-returns (the `overview_frontmatter`/`parse_verify_field` `ValueError` catch, and — see below — the removed parent-branch-resolution catch) — per Decision `merge-in-batch-baseline-staleness`'s "before all of them" ordering: loop `_status.read_batches(status_path)` and call `_status.set_batch_field(status_path, name, "verify_baseline_failures", None)` for every batch entry, unconditionally, on every code path through this function (both the eventual pass and fail branch, and the no-module-wide-verify-configured case, and the malformed-verify-field error case) — per-batch staleness is independent of whether an overview-level module-wide `verify:` exists at all.
  Delete the `parent_branch = _parent_branch.resolve(status_path, interactive=False)` block and its `except Exception -> {"status": "success", "baseline": "error", ...}` early return entirely — `compute_baseline`'s new signature no longer takes a parent branch (Card 6 in batch 2), so there is nothing left for this function to resolve it for.
  Keep the existing `_status.clear_module_verify_baseline(status_path)` reset call where it is today (resets the module-wide scalar; unaffected by this card).
  Resolve the absolute verify cwd the same way `_run_verify_gate` resolves its own effective cwd (mirrored via the `cwd_override` returned by `parse_verify_field`, per the "`git_root` vs `project_root`" gotcha): `effective_cwd = cwd_override if cwd_override is not None else git_root`.
  Call the new `_verify_baseline.compute_baseline(effective_cwd, module_wide_verify_cmd, timeout_seconds=<existing timeout resolution if any, else omit for no ceiling>)`, unpack `(result, _signatures)` — discard `_signatures` explicitly (a post-merge-in tree is not pre-edit, so its signatures describe nothing usable as a baseline, per Decision `module-wide-verdict-source`).
  Map the result asymmetrically per Decision `merge-in-recompute`: `"clean"` -> `_status.set_module_verify_baseline(status_path, "clean")`, then print `{"status": "success", "baseline": "computed", "value": "clean"}`; `"pre-existing-failures"` -> do NOT call `_status.set_module_verify_baseline` at all (the earlier `clear_module_verify_baseline` call already left the field unset — leaving it unset is the strict-gating outcome), then print `{"status": "success", "baseline": "computed", "value": "pre-existing-failures"}` (unchanged wire shape from today, only the underlying mapping logic changes).
- **Commit:** `refactor(millpy-merge-in-subagent): recompute-baseline uses new compute_baseline signature, clears every batch baseline first`

### Card 28: Rewrite test-millpy-merge-in-subagent.py's recompute-baseline coverage

- **Context:**
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `test_21_recompute_baseline_mapping_verify_field`, update the `compute_baseline` mock from `return_value="clean"` to `return_value=("clean", [])`, and update the call-argument assertions to the new signature: no more `project_root`/`git_root`/`parent_branch` positional args and no `cwd_override_relative` kwarg — assert the resolved absolute cwd positional argument (the mapping-form fixture's `cwd: hub` resolves to `self.tmp_path`, mirroring the deleted assertion's own expected value but as the new direct `cwd` positional arg) and `module_wide_verify_cmd` positional argument instead. Keep `test_20_recompute_baseline_missing_status_md` and `test_22_recompute_baseline_malformed_verify_field` conceptually unchanged, but re-verify each against the rewritten early-return ordering in Card 27 (both still fail before reaching `compute_baseline`, so their assertions on the printed JSON should be unaffected — confirm by running the test, not by inspection alone).
  Add new tests, per the discussion's own Testing-section framing for this file: (a) `--recompute-baseline` leaves every batch's `verify_baseline_failures` cleared on both the `"clean"`-mapped pass branch and the `"pre-existing-failures"`-unset fail branch, given a `status.md` fixture with several batches carrying non-empty `verify_baseline_failures` beforehand; (b) the same clearing still happens in the no-module-wide-verify-configured case (overview `verify:` null, batches present) even though the module-wide half exits early with `baseline: "skipped"`; (c) the same clearing still happens in the malformed-verify-field error case (`test_22`'s own fixture); (d) a fail-then-pass sequence at the `compute_baseline` mock (`side_effect` returning a first result then a corrected one across two calls is not applicable here since this function calls `compute_baseline` once per invocation — instead, mock `compute_baseline` to return `("clean", [])` after having asserted the flakiness-guard retry itself is `compute_baseline`'s own internal concern, not this caller's) resolves to `module_verify_baseline` set to `"clean"` — a test asserting against `compute_baseline`'s own *return value* rather than a raw exit code, since a raw-exit-code-based test would pass for the wrong implementation here.
- **Commit:** `test(millpy-merge-in-subagent): rewrite recompute-baseline coverage for new signature and batch clearing`

### Card 29: Rework the integration test for the eager per-batch capture model

- **Context:**
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
- **Edits:**
  - `plugins/mill/integration_tests/test-baseline-waiver.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Keep this test's end-to-end shape (a pre-existing failure is waived, a newly-introduced one blocks) — per `_mill/discussion.md`'s own Testing-section note, this is the highest-value surviving coverage in this file and should be preserved even though its setup changes completely. Rebuild "Step 1" around the new eager per-batch pre-flight: the batch's `verify_baseline_failures` must now be captured by a `--stage baseline` CLI call made BEFORE any implementer/fixer dispatch (mirroring batch 3's eager capture), rather than the old lazy on-first-failure computation this test previously drove through `--stage finalize` alone. Keep Steps 2 and 3 (introduce a second, distinct failure -> not waived; revert to only the pre-existing failure -> waived) driving `--stage finalize` exactly as today, since the subset-diff waiver itself (in `_run_verify_gates`) is unchanged by this task — only how the baseline it compares against was obtained has changed.
- **Commit:** `test(baseline-waiver): rework fixture setup for eager per-batch capture`

## Batch Tests

`verify:` runs the unit test (`test-millpy-merge-in-subagent.py`) and the real-git integration test (`integration_tests/test-baseline-waiver.py`) via a `&&`-chained invocation — together the direct and end-to-end consumers of `_run_recompute_baseline`.
