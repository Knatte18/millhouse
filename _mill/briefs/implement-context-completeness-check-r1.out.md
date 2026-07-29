2 of 2 cards committed (Card 1: feat(plan-validate) commit 9188dfca; Card 2: test(plan-validate) commit 2aeca844). Verify command `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-plan-validate.py` passed with all tests green, including the 14 new `test_check_context_completeness_*` functions.

Files touched:
- `/home/knatte/Code/millhouse/wts/mill-plan-autonomy-and-validation-gaps/plugins/mill/scripts/_plan_validate.py` — added `_check_context_completeness`, `_extract_requirements_text`, `_card_own_reference_set` helpers, wired into `run()`, updated module docstring.
- `/home/knatte/Code/millhouse/wts/mill-plan-autonomy-and-validation-gaps/plugins/mill/unit_tests/test-plan-validate.py` — added `requirements=` kwarg to `_make_batch_file`, 14 new test functions registered in `main()`'s tests list, updated module docstring coverage list.

{"status":"success","commit_sha":"2aeca8449e190c79024e12ab5071bafb63a4efff","session_id":"4e23ba95-c05e-47b5-a388-13094bedd8b6","cards_done":[1,2]}
