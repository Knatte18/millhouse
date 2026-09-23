{"status":"success","commit_sha":"ba01a04b8504dbcd1852230dd14e1da3b527128c","session_id":"6a3adc3b-3ce3-451c-b9e6-a0a250769e9e"}

Summary:

1. Applied the review's [NIT:consistency] finding — `_run_module_wide_standalone` in `plugins/mill/scripts/millpy-implement.py` now takes the after-snapshot and calls `_warn_new_dirt` on the `except Exception` (error) path too, matching the per-batch half's unconditional warning coverage. Committed as `ae4a10bf`.

2. During verify (batch 03's `test-millpy-implement.py`), found `test_16_stage_finalize_accepts_round_flag` failing with `AssertionError: None != 'abc1234'`. Root-caused: this is unrelated to the review fix (confirmed by temporarily swapping in the pre-fix file content, which reproduced the identical failure). The real cause is a plan-scope gap: batch 04 Card 22 removed the `git_name`/`git_email`/`batch_name` kwargs from `finalize_from_output`, and Card 25 updated the matching `#954` assertion block in `test-fix-finalize.py`, but an identical stale assertion block in `test-millpy-implement.py`'s `test_16` (a different file, not in Card 25's edit list) was missed. Fixed by mirroring Card 25's exact treatment: deleted the stale `git_name`/`git_email` assertions and their explanatory comment in `plugins/mill/unit_tests/test-millpy-implement.py`. Committed as `ba01a04b`.

3. Ran every non-null `verify:` command from all 7 batch plan files (01 through 07; 07 is null) in order — all passed. Ruff findings surfaced on both touched files are pre-existing (confirmed via diff against the prior committed content) and unrelated to these two edits.

Files touched:
- `/home/hanf/Code/millhouse/wts/baseline-uses-worktree-not-checkout/plugins/mill/scripts/millpy-implement.py`
- `/home/hanf/Code/millhouse/wts/baseline-uses-worktree-not-checkout/plugins/mill/unit_tests/test-millpy-implement.py`
