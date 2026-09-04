All 5 of 5 cards committed, matching the batch file's declared `Commit:` messages exactly. Working tree is clean, and `verify:` passed (all `test-plan-validate.py` unit tests pass, including the full pre-existing regression suite).

{"status":"success","commit_sha":"e7395be72fff9f0642048aec008816e8a8bc11ae","session_id":"a5522f43-8d9b-405b-b9fb-93b4d8e92900","cards_done":[1,2,3,4,5]}

Summary: 5 of 5 cards committed and verified.

Files touched (all in `/home/knatte/Code/millhouse/wts/plan-validate-batch-index-drift-and-misc-checks`):
- `plugins/mill/scripts/_plan_validate.py` — added `_check_verify_batch_mismatch` (wired into `run()` and docstrings), added `_add_n_leading_spaces` helper, extended `_check_requirements_quote_indent_drift` with a symmetric under-indent ("add") detection pass, and added `"signature inlined"`/`"no file read needed"` to `_CITATION_MARKERS`.

Commits (oldest to newest): `c0e4b331`, `a0bba487`, `3e0515c7`, `61d1e982`, `e7395be7`.

`verify:` command `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py` passed with no failures (this batch is a pure regression gate — new-behavior unit tests land in batch 2).

{"status":"success","commit_sha":"e7395be72fff9f0642048aec008816e8a8bc11ae","session_id":"a5522f43-8d9b-405b-b9fb-93b4d8e92900","cards_done":[1,2,3,4,5]}
