Both cards (4 and 5) are committed — 2 of 2 cards declared in this batch, matching the batch file's `cards: 2`. Verify passes. No uncommitted tracked changes.

Summary: 2 of 2 cards committed and complete.

- Card 4 (commit `dd59522f`): fixed the holistic-disablement gate in `/home/knatte/Code/millhouse/wts/mill-pipeline-silent-failure-and-report-bugs/plugins/mill/scripts/_review_plan.py` (~line 730) to check `holistic_max_rounds` instead of the raw config value, mirroring `_review_discussion.py`.
- Card 5 (commit `10eada08`): added Test 33 to `/home/knatte/Code/millhouse/wts/mill-pipeline-silent-failure-and-report-bugs/plugins/mill/unit_tests/test-review-plan-flow.py` covering `--max-rounds` forcing holistic dispatch despite `rounds:0`. Running the full suite surfaced that Card 4's fix legitimately changed the behavior exercised by the pre-existing Test 22 (batch reviewer null + `max_rounds=0` override now correctly disables holistic too, rather than coincidentally slipping through the round-cap stub-return), so I updated Test 22's expectation to assert the `ReviewError` ("at least one must be set") that Test 6b already establishes as the correct pattern for that both-null scenario, rather than weakening or deleting the test.

Verify command `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-review-plan-flow.py` passes in full (all test blocks PASS). Working tree is clean.

{"status":"success","commit_sha":"10eada08","session_id":"cf8ec1fe-cd7d-42b9-9332-8e0b61790bee","cards_done":[4,5]}
