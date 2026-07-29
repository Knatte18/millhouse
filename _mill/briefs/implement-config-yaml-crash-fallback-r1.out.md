All 5 cards are committed and verified. Summary of work:

**Card 1+2** (combined commit `d3f334f8` — combined because both cards necessarily touch the same file `_config.py`; named per Card 2's message per the combined-commit rule): Added `try/except yaml.YAMLError` guards around both the repo-layer read (line 239) and the cache-lag template-augmentation read (line 229) in `plugins/mill/scripts/_config.py`'s `load_config`. Repo-layer failure sets `repo_cfg = {}` and skips the merge while still setting `source_label`; cache-lag failure `continue`s the loop instead of crashing or `break`ing.

**Card 3** (`949f1a24`): Added `test_load_config_repo_layer_yaml_crash_falls_back` and `test_load_config_repo_layer_clean_yaml_unaffected` to `plugins/mill/unit_tests/test-config.py`.

**Card 4** (`dffba304`): Added `test_worktree_template_crash_falls_through_to_hub_template`, using distinct `hub_root`/`worktree_root` directories and a probe key also written to the repo-layer config to make the no-unknown-key-warning assertion falsifiable. I verified this test actually fails against the pre-fix code (temporarily reverted the Card 2 fix, confirmed the test raises `ScannerError`, then restored the fix) before committing.

**Card 5** (`f6ee5329`): Added `test_review_common_load_config_unparseable_repo_layer_does_not_raise` — regression-only, no production edit to `_review_common.py`.

Verify command `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-config.py` passes with exit code 0 (46 tests, all PASS). Working tree is clean (no uncommitted tracked changes).

Card-count self-check: range start `f665a4e9` (batch-start commit), 4 commits in range, matching Cards 2/3/4/5's `Commit:` messages exactly (Card 1 folded into the Card 2 commit per the combined-commit allowance). All 5 of 5 declared cards committed/addressed this turn.

Relevant files:
- `/home/knatte/Code/millhouse/wts/mill-merge-conflict-robustness-gaps/plugins/mill/scripts/_config.py`
- `/home/knatte/Code/millhouse/wts/mill-merge-conflict-robustness-gaps/plugins/mill/unit_tests/test-config.py`

{"status":"success","commit_sha":"f6ee5329","session_id":"ea07e3fe-fba3-4e3d-be34-24c7d0822486","cards_done":[1,2,3,4,5]}