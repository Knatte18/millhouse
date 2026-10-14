{"status":"success","commit_sha":"b5b28b3c3cd96bb1b078dc507830957a1016c6a3","session_id":"c0dc2aa7-a2ec-4571-8a7b-7efac97023c8","cards_done":[1,2]}

Both cards are committed (2 of 2). The batch verify passed (70 tests, OK) and the tracked tree is clean.

- **Card 1:** `--stage baseline` and the baseline-only helpers are gone from `plugins/mill/scripts/millpy-implement.py`. The finalize and full stages no longer read or pass the cached baselines. `batch_name` is now a plainly required positional.
- **Card 2:** `plugins/mill/unit_tests/test-millpy-implement.py` lost all `test_baseline_stage_*` tests, the helpers used only by them, and the classes `TestBaselinePreflightSkipReason` and `TestWarnNewDirt`. I added the two argparse tests (`--stage baseline` rejected, missing `batch_name` for every stage). The finalize and full-stage tests now assert the two baseline kwargs are absent. A grep for the deleted names in that file finds no hits.
- **Lint:** the `F401,F841,F811` ruff check on `millpy-implement.py` is clean. In the test file, deleting the baseline tests left `contextlib` and `yaml` imports unused, so I removed them.

I did not add `assertNotIn` for the baseline kwargs to the other finalize tests.

{"status":"success","commit_sha":"b5b28b3c3cd96bb1b078dc507830957a1016c6a3","session_id":"c0dc2aa7-a2ec-4571-8a7b-7efac97023c8","cards_done":[1,2]}
