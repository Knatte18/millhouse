# Batch: nits-only-no-op-success

```yaml
task: Fix discussion review round-cap, daemon cold-start, and nits-only no-op in finalize
batch: nits-only-no-op-success
number: 3
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-millpy-fix.py
depends-on: []
```

## Batch Scope

This batch closes GitHub issue #582: a `--nits-only` fixer pass that legitimately pushes back on every NIT finding (per the `mill-receiving-review` decision tree, the correct outcome — zero commits expected) is misclassified by `_implementer_common.finalize_from_output()` as `stuck_type: "logic"` ("no content commit") instead of success, and the `nits-fixed-<scope>` timeline marker is never written — which then blocks the Handoff nit-enforcement gate (`_nit_gate.compute_unfixed_nits`). The fix is a single-condition change: skip the no-content-commit demotion only when `nits_only=True`, leaving every other gate (completeness, in-scope dirty-tree) and the existing `nits_only` marker block unchanged. Per discussion (round 3 review correction), this batch does NOT thread `task_dir`/`parent_branch` through `millpy-fix.py`'s CLI to make the in-process dirty-tree gate reachable there — that gate is already, and remains, a no-op on the fixer's real call path; the actual backstop for stray-uncommitted-residue is mill-go's unrelated, unmodified Handoff-time terminal cleanliness gate.

## Cards

### Card 5: Skip the no-content-commit demotion when `nits_only=True`

- **Context:**
  - `plugins/mill/scripts/millpy-fix.py`
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In `_forward_output()`, change the existing guard `if start_sha is not None:` (the block that contains both the `HEAD == start_sha` demotion and the `_is_only_start_batch_commit` demotion, each emitting `stuck_type: "logic"`) to `if start_sha is not None and not nits_only:`. This is the single surgical condition that skips both no-content-commit demotions when `nits_only=True`, while leaving the same block fully active (unchanged) when `nits_only=False`. Do not touch the two `print(json.dumps(...))` / `return 0` bodies inside the block.
  - Do not change the completeness gate (`_batch_completeness_stuck`), the in-scope dirty-tree gate (`_in_scope_dirty_stuck`), or the `nits_only` marker block (`if nits_only and status_path and nits_scope: parsed["nits_applied"] = True; _status.append_phase(...)`) — all three already run unconditionally after the now-conditional block and require no edit.
  - Update `_forward_output()`'s docstring (the paragraph beginning "When nits_only is True and status_path and nits_scope are not None, on the parsed-success emit path...") to add one sentence noting that when `nits_only` is `True`, the no-content-commit gate (`HEAD == start_sha` / only-batch-start-commit) is also skipped, since a `--nits-only` pass that correctly pushes back on every finding is expected to produce zero commits.
- **Commit:** `fix(_implementer_common): treat nits-only zero-commit pushback as success, not stuck/logic`

### Card 6: Unit test coverage for the nits-only no-op success path

- **Context:**
  - `plugins/mill/scripts/millpy-fix.py`
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/unit_tests/test-implementer-common.py`
  - `plugins/mill/unit_tests/test-millpy-fix.py`

  Note: `_implementer_common.py` is listed here only because it must also be imported by the new tests (already an existing import in `test-implementer-common.py`); Card 5 is its only source edit.
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In `test-implementer-common.py` (function-style "Case N" tests calling `_forward_output()` directly via the `_capture_stdout` helper, matching the existing "Case 27" pattern at the `#500 regression` test — `_setup_fixture(project_root)` for a base commit, `_cleanliness.capture_snapshot(...)`, `verify_cmd = "exit 0"`, an `agent_output` JSON string with `"status":"success"`, no new commit so `HEAD == base_sha`), add a new case: write an initial status.md fixture: create the `project_root / "_mill"` directory, write `_status.render_initial(task_title="t", task_description="d", timestamp=<iso ts>, parent_branch="main", slug="test-slug", branch="test-branch")`'s returned text to `status_path = project_root / "_mill" / "status.md"` (mirroring `test-millpy-fix.py`'s `status_path = self.tmp_path / "_mill" / "status.md"` pattern), then call `_forward_output(agent_output, project_root, start_sha=base_sha, snapshot_path=snapshot_path, verify_cmd=verify_cmd, nits_only=True, status_path=status_path, nits_scope="holistic")` with no new commit since `base_sha`. Assert the parsed JSON has `status == "success"` (not `"stuck"`), `nits_applied is True`, and that `_status.read_full(status_path)["timeline"]` contains an entry starting with `nits-fixed-holistic` (same assertion shape as `test-millpy-fix.py`'s existing `test_nits_only_flag_appends_marker_and_flag`).
  - Add a second new case with the same `nits_only=True` setup but additionally passing `task_dir`/`parent_branch` (non-`None`, pointing at a fixture in-scope dirty tracked file) so `_in_scope_dirty_stuck()` is actually exercised (it is a no-op when either is `None`, per its own docstring) — assert the result is still `stuck_type: "logic"` (the dirty-tree gate, not the no-content-commit gate, fires), proving the dirty-tree gate's own behavior is unaffected by the Card 5 change. Do not assert this against `millpy-fix.py`'s actual CLI invocation, which never passes `task_dir`/`parent_branch` (see Batch Scope) — this case is a direct-API test of `_forward_output()` proving the *gate's own logic* still works when its inputs are supplied, independent of whether `millpy-fix.py` supplies them today.
  - Add a third new case with `nits_only=False` (the default) and the same zero-commit setup, asserting the existing pre-Card-5 behavior is unchanged: `status == "stuck"`, `stuck_type == "logic"`, "no content commit" in the reason — a regression guard proving the `not nits_only` condition does not affect the non-nits-only path.
  - In `test-millpy-fix.py`, locate the existing `test_nits_only_flag_appends_marker_and_flag` test (around line 767-826). That test's `mock_subprocess_run` returns a DIFFERENT `git rev-parse` SHA on the second call than the first (`"abc1234"` then `"def5678"`), simulating a real commit being made. Add a sibling test, e.g. `test_nits_only_all_pushback_zero_commit_is_success_not_stuck()`, copying the same `self._run_main([...,  "--nits-only"])` / `mock_subprocess_run` / `mock_run` structure, but with `mock_subprocess_run` returning the SAME `git rev-parse HEAD` SHA on every call (simulating the all-pushback, zero-commit case — HEAD never moves from `start_sha`) while `mock_run`'s fake implementer output still reports `"status":"success"`. Assert the resulting envelope has `data["status"] == "success"` (not `"stuck"` / no `"stuck_type": "logic"`) and `data.get("nits_applied")` is `True`, and assert (same pattern as the existing test, via `millpy_fix._status.read_full(status_path)["timeline"]`) that a `nits-fixed-test-batch` row was still appended.
- **Commit:** `test(_implementer_common,millpy-fix): cover nits-only zero-commit success and dirty-tree gate regression`

## Batch Tests

`verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-millpy-fix.py` covers both the direct-API unit tests of the reordered gate logic (`test-implementer-common.py`) and the end-to-end CLI regression test (`test-millpy-fix.py`). Scoped to the two files this batch's behavior change is reachable from — `_implementer_common.finalize_from_output()`/`_forward_output()` is also used by `millpy-implement.py`, but that caller never sets `nits_only=True` (confirmed: only `millpy-fix.py` passes `nits_only=args.nits_only`), so `test-millpy-implement.py` needs no new case from this batch and is intentionally left out of this batch's verify scope (it is covered by Batch 2's verify scope for its own, unrelated change).
