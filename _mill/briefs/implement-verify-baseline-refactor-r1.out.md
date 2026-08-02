6 of 6 cards (14-19) are committed, matching the batch's declared 6 cards exactly. All are real content commits, no `Commit: none` cards in this batch. Verify passed. Working tree is clean.

{"status":"success","commit_sha":"34599c704c10ce409a99fa45b38282a355d80b56","session_id":"978d4b3c-1da8-4e91-818f-2260bb93d97b","cards_done":[14,15,16,17,18,19]}

All 6 cards (14 through 19) of batch `verify-baseline-refactor` are committed:

- `/home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/plugins/mill/scripts/_verify_baseline.py` — extracted `_checkout_parent_branch`, `_link_dependency_dirs`, `_run_module_wide_verify_algorithm`; `_run_verify_in` now returns `tuple[int, str]`; `compute_baseline` is now a thin wrapper; added new `compute_batch_baselines`.
- `/home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/plugins/mill/unit_tests/test-verify-baseline.py` — updated existing cases for the new tuple return shape and added cases (b)-(e) covering `compute_batch_baselines`.

Verify command (`run-all.py --only test-verify-baseline.py`) passes with all 6 assertions green. I also manually ran `plugins/mill/integration_tests/test-verify-baseline.py` (the real-git end-to-end test, not part of this batch's fast verify gate) and confirmed all 6 of its cases still pass unchanged, confirming the refactor preserved `compute_baseline`'s public behavior. Working tree is clean; `git status --porcelain --untracked-files=no` shows no dirty tracked files.

{"status":"success","commit_sha":"34599c704c10ce409a99fa45b38282a355d80b56","session_id":"978d4b3c-1da8-4e91-818f-2260bb93d97b","cards_done":[14,15,16,17,18,19]}
