All 3 of 3 cards committed and confirmed against the batch file's declared `Commit:` messages. Verify (`test-plan-validate.py`) passes cleanly with all 82 tests (77 pre-existing + 5 new) passing.

{"status":"success","commit_sha":"ca60d292","session_id":"a836af46-6c37-444f-9349-f347e39ba6f7"}

Summary of work (3 of 3 cards committed):

- Card 11 (`57173ffe`): Added `_check_verify_unrelated_test_files` to `/home/knatte/Code/millhouse/wts/mill-go-batch-verify-baseline-reliability/plugins/mill/scripts/_plan_validate.py` — flags `verify:` `--only` test-file tokens that are untouched by their own batch's Edits/Creates/Moves-target Files Touched and byte-identical to the resolved parent branch.
- Card 12 (`6c2eaeba`): Wired the new check into `_plan_validate.run()` (new `parent_branch` kwarg), resolved `parent_branch` non-interactively at both `validate_run(...)` call sites in `/home/knatte/Code/millhouse/wts/mill-go-batch-verify-baseline-reliability/plugins/mill/scripts/millpy-review-plan.py`, left `millpy-validate-plan.py` untouched per the plan's explicit instruction, and added the `verify-unrelated-test-file` row to the Step 1.5 fix table in `/home/knatte/Code/millhouse/wts/mill-go-batch-verify-baseline-reliability/plugins/mill/skills/mill-plan/SKILL.md`.
- Card 13 (`ca60d292`): Added 5 new tests to `/home/knatte/Code/millhouse/wts/mill-go-batch-verify-baseline-reliability/plugins/mill/unit_tests/test-plan-validate.py` using a real pygit2-backed git fixture with a non-`main` parent branch (`hanf/some-parent`), covering: flagged, touched-so-not-flagged, differs-so-not-flagged, `parent_branch=None` fail-safe, and no-`--only`-segment cases.

Verify command run: `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py` — all tests pass. Working tree is clean (no uncommitted tracked changes).
