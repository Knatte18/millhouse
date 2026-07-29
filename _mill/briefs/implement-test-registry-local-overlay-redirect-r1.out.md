All 3 cards' Commit: messages match (Card 6: 17e7336a, Card 7: c0649460 + 7ce5643e combined, Card 8: 7959bf0c). 3 of 3 cards committed — all cards complete.

{"status":"success","commit_sha":"7959bf0c","session_id":"2a04d7e9-7cd4-4871-95c4-38c4e296615d","cards_done":[6,7,8]}

All 3 of 3 cards in this batch are committed (Card 6, Card 7, Card 8) and `verify:` passes. Summary of work:

- `/home/knatte/Code/millhouse/wts/mill-pipeline-silent-failure-and-report-bugs/plugins/mill/unit_tests/_test_registry.py` — Card 6: added shared `_write_registry_file(mill_dir, registry)` writer; `write_to()` now builds via `make_minimal_registry()` and writes to `mill_dir/agents.local.yaml` instead of the dead `wiki_root/agents.yaml`.
- `/home/knatte/Code/millhouse/wts/mill-pipeline-silent-failure-and-report-bugs/plugins/mill/unit_tests/_test_helpers.py` — Card 7: `write_local_overlay()` delegates to `_test_registry._write_registry_file`.
- `/home/knatte/Code/millhouse/wts/mill-pipeline-silent-failure-and-report-bugs/plugins/mill/scripts/_test_registry.py` — **deleted**, out-of-plan-scope discovery: this stale, unreferenced duplicate of the unit_tests module was silently shadowing the Card 6 redirect for `test-review-plan-flow.py`/`test-review-discussion-flow.py` (they add `plugins/mill/scripts` to `sys.path` ahead of their own directory). Per the STOP protocol, I first amended `/home/knatte/Code/millhouse/wts/mill-pipeline-silent-failure-and-report-bugs/_mill/plan/03-test-registry-local-overlay-redirect.md` (Card 7's `Deletes:`) and committed that plan edit before deleting the file.
- `/home/knatte/Code/millhouse/wts/mill-pipeline-silent-failure-and-report-bugs/plugins/mill/unit_tests/test-reviewers.py` — Card 8: added `test_write_to_round_trips_through_reviewers_load`, registered it in `main()`'s test list right after `test_load_raises_cluster_use_referencing_cluster`.

Final verify run (`PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-reviewers.py test-review-plan-flow.py test-review-discussion-flow.py`) passed: "PASS -- all 3 unit tests". Working tree is clean (`git status --porcelain --untracked-files=no` empty).

{"status":"success","commit_sha":"7959bf0c","session_id":"2a04d7e9-7cd4-4871-95c4-38c4e296615d","cards_done":[6,7,8]}
