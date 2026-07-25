All 3 cards for this batch are committed:

- Card 1 (`5da74ad5`) — added `count_unrecognized_severity_findings()` to `plugins/mill/scripts/_review_common.py`
- Card 2 (`ad7464c9`) — wired the helper into `finalize_scope()` in the same file
- Card 3 (`f5f520c7`) — added test coverage in `plugins/mill/unit_tests/test-review-common.py`
- Plus a follow-up fix commit (`21ae5464`) discovered while writing Card 3's tests: restricted the heading regex to all-uppercase bracket labels (`[A-Z]+`) so mixed-case headings like `[Major]`/`[major]` are excluded, per the discussion.md case-sensitivity clarification.

3 of 3 cards committed. `verify:` (`PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-review-common.py`) passes with exit code 0. `git status --porcelain --untracked-files=no` shows no dirty tracked files.

Relevant files:
- `/home/knatte/Code/millhouse/wts/mill-plan-review-validation-gaps/plugins/mill/scripts/_review_common.py`
- `/home/knatte/Code/millhouse/wts/mill-plan-review-validation-gaps/plugins/mill/unit_tests/test-review-common.py`

{"status":"success","commit_sha":"21ae5464","session_id":"9e076cb9-f6c4-4b44-b639-3060f55e4efc","cards_done":[1,2,3]}
