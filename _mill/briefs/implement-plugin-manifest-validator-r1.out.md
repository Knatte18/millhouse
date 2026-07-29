{"status":"success","commit_sha":"6b765dd9a0f0c4521a3d4c24b916bad327decd2a","session_id":"3d0c8b15-02c0-4ef4-b7d1-f8e72e117441","cards_done":[17,18,19,20]}

All 4 of 4 cards committed and verified. Summary of changes:

- `/home/knatte/Code/millhouse/wts/mill-review-verdict-and-counting-gaps/plugins/mill/scripts/_plan_validate.py` — added `_parse_context_only()` helper (Card 17) and `_check_plugin_manifest_context_missing()` wired into `run()`, plus docstring updates (Card 18).
- `/home/knatte/Code/millhouse/wts/mill-review-verdict-and-counting-gaps/plugins/mill/skills/mill-plan/SKILL.md` — added the `plugin-manifest-context-missing` fix-table row (Card 19).
- `/home/knatte/Code/millhouse/wts/mill-review-verdict-and-counting-gaps/plugins/mill/unit_tests/test-plan-validate.py` — added 5 new test functions covering the new check and registered them in `main()`'s `tests` list (Card 20).

Verify command `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-plan-validate.py` passed (all tests, including the 5 new ones, PASS). Working tree is clean; all 4 commits pushed to `hanf/mill-review-verdict-and-counting-gaps`.

{"status":"success","commit_sha":"6b765dd9a0f0c4521a3d4c24b916bad327decd2a","session_id":"3d0c8b15-02c0-4ef4-b7d1-f8e72e117441","cards_done":[17,18,19,20]}