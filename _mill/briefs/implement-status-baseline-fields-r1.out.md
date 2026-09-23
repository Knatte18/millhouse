Both cards in batch 01-status-baseline-fields committed (2 of 2 cards committed):

- Card 1 (commit 595454be): added `get_module_verify_baseline_signatures`/`set_module_verify_baseline_signatures` to `plugins/mill/scripts/_status.py`, mirroring the existing scalar `module_verify_baseline` accessor pair's insert-in-place-or-append pattern but serializing via `yaml.safe_dump(value, default_flow_style=True, width=10**9).strip()` for a single-physical-line flow sequence. Updated `clear_module_verify_baseline` to also remove `module_verify_baseline_signatures` in the same call, and updated the module's `Public API:` docstring block. Left `get_baseline_parent_sha`/`set_baseline_parent_sha` untouched per the batch's scope note (deleted in batch 4, not here).
- Card 2 (commit 6a6f242e): added round-trip, empty-list-survives, in-place-rewrite, long-value-single-physical-line, and clear-clears-both-fields coverage to `plugins/mill/unit_tests/test-status.py`, plus the two new accessor imports. Left the existing `baseline_parent_sha` test block untouched.

Ruff check on the two changed files surfaced 6 pre-existing findings in `_status.py` (import ordering, TRY203, RUF059, TRY004) — confirmed identical on `git show main:plugins/mill/scripts/_status.py`, so none were introduced by this batch; left as-is per pre-existing-debt convention. `test-status.py` is clean under ruff.

Verify command `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-status.py` passes (all _status unit tests green, including the new Tests 7-11). Working tree is clean (`git status --porcelain --untracked-files=no` empty). Both commits pushed to `hanf/baseline-uses-worktree-not-checkout`.

Files touched: `/home/hanf/Code/millhouse/wts/baseline-uses-worktree-not-checkout/plugins/mill/scripts/_status.py`, `/home/hanf/Code/millhouse/wts/baseline-uses-worktree-not-checkout/plugins/mill/unit_tests/test-status.py`.

{"status":"success","commit_sha":"6a6f242ec8843123abd91203a763b2cb7639366b","session_id":"c8c7da89-2adf-480e-8cd8-c48ff7365335","cards_done":[1,2]}
