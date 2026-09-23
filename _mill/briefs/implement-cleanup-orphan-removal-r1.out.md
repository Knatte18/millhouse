Batch cleanup-orphan-removal (06-cleanup-orphan-removal.md) fully implemented: 4 of 4 cards committed.

Cards done:
- Card 30: deleted `_scan_orphan_baseline_dirs` from `plugins/mill/scripts/millpy-cleanup.py`
- Card 31: removed `orphan_baseline_dirs` field from `CleanupPlan` and its population in `build_plan`
- Card 32: deleted `_apply_orphan_baseline_dir` and its call sites in `_print_plan` / `apply_plan`
- Card 33: updated `plugins/mill/unit_tests/test-cleanup.py` — removed `test_scan_orphan_baseline_dirs` and `test_apply_orphan_baseline_dir` (and their `main()` invocations), added `test_cleanup_plan_has_no_orphan_baseline_dirs_field` asserting the field is gone (via `hasattr` check and a `TypeError` on passing it as a kwarg). Also dropped a fully-unused duplicate `import _worktree` at module scope that the deleted tests had been the last consumer of.

Verify: `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-cleanup.py` — PASS (all tests green).

Working tree is clean (git status --porcelain --untracked-files=no returns nothing). All commits pushed to `hanf/baseline-uses-worktree-not-checkout`.

Files touched: plugins/mill/scripts/millpy-cleanup.py, plugins/mill/unit_tests/test-cleanup.py

{"status":"success","commit_sha":"64959ed98d9d414a354a036479c25c7a041a1764","session_id":"bced0a23-fb81-41c6-9b6c-54f810504e74","cards_done":[30,31,32,33]}
