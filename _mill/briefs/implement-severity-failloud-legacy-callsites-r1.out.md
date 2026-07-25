{"status":"success","commit_sha":"56a26dc70937c3cf96c33db2379f977421e05321","session_id":"ec6109e5-97c3-4790-b422-91265ca991af","cards_done":[4,5,6]}

Summary: 3 of 3 cards committed this batch (Cards 4 and 5 combined into commit `70aa8425` since both touch only `_review_plan.py`; Card 6 in commit `56a26dc7`).

Work done:
- `/home/knatte/Code/millhouse/wts/mill-plan-review-validation-gaps/plugins/mill/scripts/_review_plan.py` — imported `count_unrecognized_severity_findings` from `_review_common` and applied it at all 5 `parse_blocking_count(..., severity="BLOCKING")` call sites, folding unrecognized-severity findings into `blocking_count`/`_parsed_blocking`.
- `/home/knatte/Code/millhouse/wts/mill-plan-review-validation-gaps/plugins/mill/unit_tests/test-review-plan-flow.py` — added Test 29, seeding a per-batch reviewer response with only a `### [MAJOR]` heading and asserting `blocking_count == 1`, proving the synchronous per-batch dispatch path is fail-loud.

Verify: ran `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-plan-flow.py test-review-common.py`. New Test 29 and the existing Test 14 (aggregate blocking_count) both pass, along with `test-review-common.py`'s full suite. 3 pre-existing failures remain (Test 24, 25, 28 -- all "task status file not found" errors unrelated to severity counting); confirmed via a temporary detached worktree of `hanf/linux-port-more` that these same 3 tests fail identically there, so they are pre-existing and out of this batch's scope, not introduced by this change.

Both commits pushed to `hanf/mill-plan-review-validation-gaps`. `git status --porcelain --untracked-files=no` is clean (no uncommitted tracked changes).

{"status":"success","commit_sha":"56a26dc70937c3cf96c33db2379f977421e05321","session_id":"ec6109e5-97c3-4790-b422-91265ca991af","cards_done":[4,5,6]}
