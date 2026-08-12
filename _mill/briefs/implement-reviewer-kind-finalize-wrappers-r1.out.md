All 4 declared cards (8, 9, 10, 11) have matching commits in the log — 4 of 4 cards committed, matching the batch's declared card count of 4. Verify passed (all 3 target test files pass, including the 3 new direct-`finalize()` test cases).

{"status":"success","commit_sha":"534c0b4edb0b0bbcbbbb8eea5be1c11eec9b9e2f","session_id":"2f270d4f-aa7d-4ba3-a861-dc51096cf174","cards_done":[8,9,10,11]}

Summary of files touched (all absolute paths under `/home/knatte/Code/millhouse/wts/review-pipeline-consistency-bugs`):
- `plugins/mill/scripts/_review_plan.py` — Card 8: added `"error_kind": "reviewer"` to `finalize()`'s `except ReviewError` dict.
- `plugins/mill/scripts/_review_discussion.py` — Card 9: same addition to `finalize()`'s `except ReviewError` `ReviewResult.reviews[0]` dict.
- `plugins/mill/scripts/_review_code.py` — Card 10: same addition to `finalize()`'s `except ReviewError` `ReviewResult.reviews[0]` dict.
- `plugins/mill/unit_tests/test-review-plan-flow.py`, `plugins/mill/unit_tests/test-review-discussion-flow.py`, `plugins/mill/unit_tests/test-review-code-flow.py` — Card 11: new direct-call tests against each `finalize()` wrapper.

4 of 4 cards committed this turn (batch declares 4 cards total). Verify command (`run-all.py --only test-review-plan-flow.py test-review-discussion-flow.py test-review-code-flow.py`) passed with all tests green, including the three new `error_kind: reviewer` assertions. Pre-existing ruff lint drift (import ordering, blind-exception catches, RUF100 noqa) exists in all touched files on `main` already and was not introduced or worsened by this batch's edits — verified by diffing against `main`'s versions.