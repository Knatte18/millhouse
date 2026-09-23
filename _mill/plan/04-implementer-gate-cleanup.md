# Batch: implementer-gate-cleanup

```yaml
task: 'compute_baseline: use the task worktree''s own pre-edit state, not a parent-branch checkout'
batch: implementer-gate-cleanup
number: 4
cards: 8
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-fix-finalize.py test-millpy-fix.py test-status.py
depends-on: [3]
```

## Batch Scope

This batch deletes the lazy on-demand per-batch baseline path (#1102) and the `start_sha`-checkout corroboration fallback from `_implementer_common.py`, per Decision `delete-corroboration` and `remove-all-three-checkouts` — both are made obsolete by batch 3's eager per-batch capture, since every batch now has a real pre-edit baseline captured before batch 1 ever dispatches. Deleting both empties out `start_sha`/`status_path`/`batch_name`/`git_name`/`git_email` as dead parameters of `_run_verify_gates`, and `batch_name`/`git_name`/`git_email` as dead parameters of `_forward_output`/`finalize_from_output` (per Decision `start-sha-parameter`'s "same treatment for the other parameters this task strands"), which this batch also removes, together with every call site across `millpy-implement.py` and `millpy-fix.py` that still passes them. This batch is ordered after batch 3 because it edits `millpy-implement.py` in different call sites than batch 3 does (the finalize/full-stage branches here, vs. the `--stage baseline` branch there) — sequencing avoids two batches touching one file without a dependency edge between them.
This batch also deletes `_status.get_baseline_parent_sha`/`set_baseline_parent_sha` (Card 26) — batch 1 deliberately leaves that accessor pair in place, since its only reader (the on-demand prelude Card 20 deletes) calls it with no surrounding `try`/`except`; deleting the accessor before its last caller is gone would crash any batch verify replay run in the window between batch 1 and this one. Card 26 lands after Card 20 in this same batch, so the caller is already gone by the time the accessor itself goes.

## Cards

### Card 19: Delete _corroborate_batch_failure

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Delete `_corroborate_batch_failure` in full (docstring and body, including its inline `import _verify_baseline` / `import _worktree` and its calls to `_verify_baseline._checkout_parent_branch` / `_verify_baseline._link_dependency_dirs` / `_worktree.remove_safe` / `_run_verify_gate`). Its only caller is the corroboration branch inside `_run_verify_gates`, deleted in Card 20 of this same batch.
- **Commit:** `refactor(_implementer_common): delete _corroborate_batch_failure`

### Card 20: Rewrite _run_verify_gates to drop the on-demand and corroboration branches

- **Context:**
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_run_verify_gates`, delete the on-demand-compute prelude block in its entirety (the `if (not batch_verify_baseline and replay_signatures and status_path is not None and verify_cmd is not None): ... baseline_parent_sha = _status.get_baseline_parent_sha(status_path) ...` block, including its inline `import _verify_baseline`, its call to `_verify_baseline.compute_batch_baseline_on_demand`, and its persist-and-commit side effect via `_status.set_batch_field` plus the `git add`/`git_commit` pair guarded by `git_name is not None and git_email is not None`).
  Delete the corroboration branch in its entirety (the `elif start_sha is None: pass` / `else: control_result = _corroborate_batch_failure(...)` block that follows the subset-diff-waiver `if normalized_replay.issubset(normalized_baseline):` check, including its own persist-and-commit side effect).
  Keep the subset-diff waiver itself unchanged: `if batch_verify_baseline and replay_signatures: normalized_replay = ...; normalized_baseline = ...; if normalized_replay.issubset(normalized_baseline): batch_result = None` — this is the surviving, real waiver logic Decision `delete-corroboration`'s rationale explicitly preserves.
  Remove `start_sha`, `status_path`, `batch_name`, `git_name`, `git_email` from `_run_verify_gates`'s signature entirely — every remaining reference to them inside this function was in one of the two deleted blocks. Keep `project_root`, `verify_cmd`, `module_wide_verify_cmd`, `git_root`, `module_verify_baseline`, `cwd_override`, `module_wide_cwd_override`, `batch_verify_baseline` unchanged.
  Rewrite the docstring: delete the `start_sha:`, `status_path:`, `batch_name:`, `git_name:`, `git_email:` `Args:` entries and every paragraph describing the on-demand compute or the corroboration/self-healing persist (the paragraphs beginning "When this parameter arrives empty/None and a batch failure occurs, this function now attempts an on-demand computation..." and the `start_sha`/`status_path`/`batch_name`/`git_name`/`git_email` `Args:` prose blocks).
- **Commit:** `refactor(_implementer_common): _run_verify_gates drops on-demand and corroboration branches`

### Card 21: Update the four internal _run_verify_gates call sites

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** At every one of the four `_run_verify_gates(...)` call sites inside `_forward_output` (the explicit-JSON-success path, the formatter-drift-inference path, the clean-tree-inference path, and the dirty-then-clean-inference path), drop the `start_sha=start_sha,`, `status_path=status_path,`, `batch_name=batch_name,`, `git_name=git_name,`, `git_email=git_email,` keyword arguments from each call — `_run_verify_gates` no longer accepts them (Card 20). Keep `git_root=`, `module_verify_baseline=`, `cwd_override=`, `module_wide_cwd_override=`, `batch_verify_baseline=` unchanged at every one of the four call sites.
- **Commit:** `refactor(_implementer_common): drop removed kwargs from internal _run_verify_gates calls`

### Card 22: Remove batch_name/git_name/git_email from _forward_output and finalize_from_output

- **Context:**
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Remove `batch_name`, `git_name`, `git_email` from `_forward_output`'s signature entirely — once Card 21 lands, nothing inside `_forward_output`'s own body reads them (they were forwarded only into the four now-updated `_run_verify_gates` calls). Keep `status_path` and `start_sha` in `_forward_output`'s signature unchanged — both are still read directly inside `_forward_output`'s own body for the nits-fixed marker (`status_path`) and the no-content-commit/completeness/build-tag gates (`start_sha`), independent of `_run_verify_gates`.
  Remove the same three parameters from `finalize_from_output`'s signature, and drop `batch_name=batch_name, git_name=git_name, git_email=git_email,` from its own forwarding call into `_forward_output`.
  Update both functions' docstrings: delete the `batch_name:`, `git_name:`, `git_email:` `Args:` entries and every sentence describing them as "forwarded unchanged to `_forward_output`'s `_run_verify_gates` calls" (that mechanism no longer exists).
- **Commit:** `refactor(_implementer_common): drop batch_name/git_name/git_email from _forward_output and finalize_from_output`

### Card 23: Update millpy-implement.py's finalize and full-stage call sites

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `main()`'s `--stage finalize` branch, drop `batch_name=args.batch_name,`, `git_name=git_name,`, `git_email=git_email,` from the `finalize_from_output(...)` call. In the `--stage full` (default) branch, drop the same three keyword arguments from the `_forward_output(...)` call. Do not remove the `git_name`/`git_email` local variables from `main()` itself — they remain read elsewhere in this same file (the "mill-go: start batch" housekeeping commit in the fresh-mint dispatch branch) and are unaffected by this card; only these two specific call-site kwargs are dropped. Batch 3's own `--stage baseline` branch never called either function and needs no change here.
- **Commit:** `refactor(millpy-implement): drop removed kwargs from finalize/full-stage call sites`

### Card 24: Update millpy-fix.py's two call sites

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-fix.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Drop `git_name=git_name,`, `git_email=git_email,`, `batch_name=args.batch_name,` from the `finalize_from_output(...)` call in the `--stage finalize` branch. Drop `git_name=git_name,`, `git_email=git_email,` from the `_forward_output(...)` call in the full-stage (holistic scope) branch (this second call site never passed `batch_name`). Do not remove the `git_name`/`git_email` local variables from `main()` itself — they remain read elsewhere in this same file (the "mill-go: fixing batch..." housekeeping commit) and are unaffected by this card.
- **Commit:** `refactor(millpy-fix): drop removed kwargs from finalize/forward call sites`

### Card 25: Update the unit tests for the deleted gate branches

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-implementer-common.py`
  - `plugins/mill/unit_tests/test-fix-finalize.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `test-implementer-common.py`: delete Case 72f, 72g, 72h in full (corroboration — `_corroborate_batch_failure` no longer exists) and Case 83a, 83b, 83c in full (on-demand compute — the prelude Card 20 deletes, which read `_verify_baseline.compute_batch_baseline_on_demand` and `_status.get_baseline_parent_sha`; the accessor itself is deleted later in this same batch by Card 26). Rewrite Cases 78, 79, 80 (persist-commit side effects via `git_name`/`git_email`/`status_path`/`batch_name` through `_forward_output`) to assert the *absence* of that behavior instead — call `_forward_output` with the same fixtures but without those now-removed kwargs, and assert a batch gate failure with no cached baseline gates strictly (blocks) and performs no checkout, since the corroboration-waiver path these three cases exercised no longer exists. Keep Cases 72a-72e (the pure subset-diff waiver, which never pass `start_sha`/`status_path`/`batch_name`) completely unchanged. Update every remaining direct `_run_verify_gates(...)` call site in this file that still passes `start_sha=`/`status_path=`/`batch_name=`/`git_name=`/`git_email=` to drop those keywords — a `TypeError: unexpected keyword argument` on any missed call site is the regression signal. Remove `_corroborate_batch_failure` from any import/patch-target string still naming it.
  In `test-fix-finalize.py`, at the call-argument assertion around the comment "main()'s already-resolved git_name/git_email locals... must be forwarded into finalize_from_output -- the #954 corroboration-commit git-identity fix; a future edit that silently drops these kwargs must fail this test" (the one block asserting `call_args.kwargs.get("batch_name")`, `call_args.kwargs.get("git_name")`, `call_args.kwargs.get("git_email")`), delete those three assertions and their explanatory comment — this is precisely the #954 mechanism this batch removes, so the guard is now testing for the absence, not the presence, of these kwargs. Keep the surrounding `batch_verify_baseline`, `module_wide_verify_cmd`, `module_wide_cwd_override`, `module_verify_baseline` assertions in the same block unchanged.
- **Commit:** `test(_implementer_common): drop corroboration/on-demand coverage, update kwarg-forwarding guard`

### Card 26: Delete the baseline_parent_sha scalar accessor pair and its tests

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/unit_tests/test-status.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Delete the `get_baseline_parent_sha` and `set_baseline_parent_sha` functions from `_status.py` in full (both functions, including their docstrings). Remove their two lines from the module's top `Public API:` docstring block (`get_baseline_parent_sha(status_path) -> str | None` and `set_baseline_parent_sha(status_path, value) -> None`). By this point in the batch, Card 20 has already deleted the only reader that called either function without a guarding `try`/`except` — this card runs last (after Card 20, Card 25) specifically so the accessor's last caller is confirmed gone before the accessor itself goes, closing the crash window described in this batch's own Batch Scope note.
  In `test-status.py`, delete the "--- baseline_parent_sha tests ---" block in full (the block covering `get_baseline_parent_sha`/`set_baseline_parent_sha`: None-on-fresh-file, insert-then-round-trip, in-place-rewrite-on-second-set, and empty-string-value-rejects). Remove `get_baseline_parent_sha` and `set_baseline_parent_sha` from the `from _status import (...)` block at the top of the file.
- **Commit:** `refactor(_status): delete get/set_baseline_parent_sha now that its last caller is gone`

## Batch Tests

`verify:` runs `test-implementer-common.py` (the direct unit test for every function this batch edits), `test-fix-finalize.py` (the one test elsewhere in the suite asserting on the exact kwargs Card 22 removes from `finalize_from_output`), `test-millpy-fix.py` (re-run for safety since Card 24 edits `millpy-fix.py`, even though no test in that file references the removed kwargs by name), and `test-status.py` (re-run since Card 26 edits it, removing the `baseline_parent_sha` coverage batch 1 deliberately left in place).
