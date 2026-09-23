Batch implementer-gate-cleanup (batch 4) complete: 8 of 8 cards committed (Cards 19-26), verify passed.

Files touched:
- /home/hanf/Code/millhouse/wts/baseline-uses-worktree-not-checkout/plugins/mill/scripts/_implementer_common.py
- /home/hanf/Code/millhouse/wts/baseline-uses-worktree-not-checkout/plugins/mill/scripts/millpy-implement.py
- /home/hanf/Code/millhouse/wts/baseline-uses-worktree-not-checkout/plugins/mill/scripts/millpy-fix.py
- /home/hanf/Code/millhouse/wts/baseline-uses-worktree-not-checkout/plugins/mill/scripts/_status.py
- /home/hanf/Code/millhouse/wts/baseline-uses-worktree-not-checkout/plugins/mill/unit_tests/test-implementer-common.py
- /home/hanf/Code/millhouse/wts/baseline-uses-worktree-not-checkout/plugins/mill/unit_tests/test-fix-finalize.py
- /home/hanf/Code/millhouse/wts/baseline-uses-worktree-not-checkout/plugins/mill/unit_tests/test-status.py

Summary of work:
- Deleted `_corroborate_batch_failure` (start_sha-checkout corroboration fallback).
- Rewrote `_run_verify_gates` to drop the on-demand compute prelude and the corroboration branch, and removed `start_sha`/`status_path`/`batch_name`/`git_name`/`git_email` from its signature.
- Updated all 4 internal `_run_verify_gates` call sites inside `_forward_output`.
- Removed `batch_name`/`git_name`/`git_email` from `_forward_output` and `finalize_from_output` signatures/docstrings/forwarding call.
- Updated `millpy-implement.py`'s finalize and full-stage call sites, and `millpy-fix.py`'s two call sites, to stop passing the removed kwargs (kept the local `git_name`/`git_email` variables themselves, since they're read elsewhere in both files).
- Updated unit tests: deleted Cases 72f/72g/72h (corroboration) and 83a/83b/83c (on-demand compute) from test-implementer-common.py; rewrote Cases 78/79/80 to assert strict blocking now that the corroboration-waiver path is gone; removed the #954 batch_name/git_name/git_email kwarg-forwarding assertions from test-fix-finalize.py.
- Deleted `get_baseline_parent_sha`/`set_baseline_parent_sha` from `_status.py` (and their Public API doc lines) plus their test block in test-status.py, now that Card 20 removed the last caller.

Verify command (`PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-fix-finalize.py test-millpy-fix.py test-status.py`) passed: all 4 unit test files green.

Pre-report self-check: `git status --porcelain --untracked-files=no` is clean (no uncommitted tracked changes).

Card-count self-check: `git log 8cbab7af..HEAD --oneline` shows exactly 8 commits, one per declared card (19-26), matching the batch's declared card count 1:1.

{"status":"success","commit_sha":"608795c3700ba247520f51bcdfc77e55fe34b8f9","session_id":"8661aaed-f434-4d3a-99b4-fac415bc57ea","cards_done":[19,20,21,22,23,24,25,26]}
