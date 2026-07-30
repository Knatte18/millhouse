All 3 cards' Commit: messages match exactly. 3 of 3 cards committed — all complete.

{"status":"success","commit_sha":"2399cf5d","session_id":"703a6437-3035-4645-98c6-3d43d5a4b3b5","cards_done":[1,2,3]}

Summary: All 3 cards in batch `01-requirements-quote-indent-drift-check.md` committed and verified (3 of 3 cards done, verified honestly via commit-log match against Commit: messages).

- `/home/knatte/Code/millhouse/wts/mill-plan-requirements-byte-exactness-gap/plugins/mill/scripts/_plan_validate.py` — Card 1: added `_strip_n_leading_spaces`, `_card_edits_tokens`, `_requirements_fence_aware_body`, `_check_requirements_quote_indent_drift`, the `_RE_FENCE_BODY` constant, wired into `run()`, and documented in the module docstring.
- `/home/knatte/Code/millhouse/wts/mill-plan-requirements-byte-exactness-gap/plugins/mill/skills/mill-plan/SKILL.md` — Card 2: added the `requirements-quote-indent-drift` fix-table row and extended the `Requirements:` Principles bullet.
- `/home/knatte/Code/millhouse/wts/mill-plan-requirements-byte-exactness-gap/plugins/mill/unit_tests/test-plan-validate.py` — Card 3: added the nine `test_check_requirements_quote_indent_drift_*` functions and registered them in the runner's `tests = [...]` list.

Verify (`run-all.py --only test-plan-validate.py`) passed with all tests green, including the nine new ones. Ruff findings surfaced on both edited Python files were confirmed pre-existing (identical error sets on `main`), so none were introduced by this batch.

{"status":"success","commit_sha":"2399cf5d","session_id":"703a6437-3035-4645-98c6-3d43d5a4b3b5","cards_done":[1,2,3]}
