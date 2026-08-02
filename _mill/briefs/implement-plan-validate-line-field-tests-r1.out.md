All 1 of 1 declared cards committed (Card 3).

{"status":"success","commit_sha":"68ef4aac54a709580d5f0bcfb2aa23f40e3cc729","session_id":"6b20b3c8-7145-4d86-bd05-0676dfde186c","cards_done":[3]}

Summary: Implemented batch `02-plan-validate-line-field-tests` (1 of 1 cards, Card 3) by editing `/home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/plugins/mill/unit_tests/test-plan-validate.py`:
- Added a `line` assertion to `test_check_context_completeness_dirty_missing`.
- Added new test `test_check_context_completeness_dirty_odd_backtick_count_line_field`, reproducing the single-line odd-backtick-count mis-pairing false positive against `_plan_validate.py`'s `_check_context_completeness` (`/home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/plugins/mill/scripts/_plan_validate.py`), and registered it in `main()`'s test list.

Verify command `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-plan-validate.py` passes (all tests green). Working tree is clean; commit `68ef4aac` pushed to `hanf/mill-validate-verify-diagnostics-gaps`.

{"status":"success","commit_sha":"68ef4aac54a709580d5f0bcfb2aa23f40e3cc729","session_id":"6b20b3c8-7145-4d86-bd05-0676dfde186c","cards_done":[3]}
