All 5 of 5 cards from `## Cards` are committed (matching each `Commit:` message in the batch file exactly), and verify passed.

Summary of work:
- Card 1 (`445b5d30`): added `_TIER_RANK`/`_EFFORT_RANK` maps plus `tier_rank()` and `fixer_weaker_than_reviewer_warning()` to `plugins/mill/scripts/_reviewers.py`, plus module docstring updates.
- Card 2 (`8a1aad84`): wired the advisory stderr warning into `plugins/mill/scripts/millpy-fix.py` right after `fixer_model = fixer_spec["model"]` resolution.
- Card 3 (`c423bc59`): added the escalation-relationship comment above `roles.fixer.model` in `plugins/mill/templates/mill-config.yaml`.
- Card 4 (`47560d27`): added 8 new test functions to `plugins/mill/unit_tests/test-reviewers.py`, appended to `main()`'s explicit `tests` list.
- Card 5 (`cbbbb4bc`): added 2 new test methods to `plugins/mill/unit_tests/test-millpy-fix.py`'s `TestMillpyFix` class covering the warning wiring.

Verify command `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-reviewers.py test-millpy-fix.py` passed (all tests OK). Working tree is clean with no uncommitted tracked changes. All 5 of 5 cards committed and pushed.

{"status":"success","commit_sha":"cbbbb4bc","session_id":"1cef1610-997f-49bc-a391-11c0b3605145"}
