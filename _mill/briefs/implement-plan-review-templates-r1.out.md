All 3 cards from the batch (Card 14, 15, 16) match commits in the log exactly. 3 of 3 cards committed — all complete.

{"status":"success","commit_sha":"2ad5be01","session_id":"7bc4e493-72f6-40a2-b622-cd7d934a034b","cards_done":[14,15,16]}

Summary: 3 of 3 cards committed (Card 14, 15, 16 — all with matching commit-log entries confirmed via the range-start check). Verify (`test-review-templates.py`) passes with all 5 tests including the new `test_plan_criteria_bullets_present`. Working tree is clean.

Files touched:
- `/home/knatte/Code/millhouse/wts/mill-review-verdict-and-counting-gaps/plugins/mill/templates/review-plan-holistic.md` (Card 14)
- `/home/knatte/Code/millhouse/wts/mill-review-verdict-and-counting-gaps/plugins/mill/templates/review-plan-batch.md` (Card 15)
- `/home/knatte/Code/millhouse/wts/mill-review-verdict-and-counting-gaps/plugins/mill/unit_tests/test-review-templates.py` (Card 16)

Note: encountered a pre-existing, unrelated ruff `RUF100` warning (unused `noqa: E402` on line 28 of `test-review-templates.py`) — confirmed present on `main` via `git show main:...`, so left untouched per scope discipline.

{"status":"success","commit_sha":"2ad5be01","session_id":"7bc4e493-72f6-40a2-b622-cd7d934a034b","cards_done":[14,15,16]}