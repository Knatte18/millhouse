{"status":"success","commit_sha":"8167b117d23626eb055a309eae4d07a7b64420e5","session_id":"2230e10d-4d03-455b-8959-e11c686d6a68","cards_done":[1,2,3,4,5,6]}

All 6 of 6 cards committed and verified. Summary:

- Card 1 (`21ba4be6`): `_scan_approved_batches()` now computes real `blocking_count`/`nit_count` for skip-approved carryforward instead of hardcoding `blocking_count: 0` with no `nit_count` key.
- Card 2 (`5a20b97f`): `_review_one_batch()`'s terminal write site refactored to call `finalize_scope()`; dropped the now-dead `verdict = parse_verdict(raw)` reassignment in the NEED_CONTEXT resume-retry-success branch.
- Card 3 (`4e1d10ff`): added `"nit_count": 0` to `_review_one_batch()`'s 3 error-return sites for schema parity.
- Card 4 (`4fbada75`): `run()`'s holistic block's 3 success-path write sites refactored to `finalize_scope()`.
- Card 5 (`05f7df8a`): added `"nit_count": 0` to `run()`'s 3 remaining holistic error-path sites.
- Card 6 (`8167b117`): `run()` now sums `aggregate_nit` across `reviews[]` and passes `nit_count=aggregate_nit` into the final `ReviewResult`.

File touched (only one, as scoped): `/home/knatte/Code/millhouse/wts/mill-review-verdict-and-counting-gaps/plugins/mill/scripts/_review_plan.py`

Verify command `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-plan-flow.py` passed (all 29 sub-tests green, no regressions to existing `verdict`/`blocking_count` behavior). Working tree is clean; all commits pushed to `hanf/mill-review-verdict-and-counting-gaps`.

Note: pre-existing ruff findings (unsorted import block, an f-string without placeholders, a PERF402 hint) exist in `_review_plan.py` outside the lines this batch touched — confirmed present on the pre-batch HEAD via `git show`, so left untouched as out of scope for this fix.

{"status":"success","commit_sha":"8167b117d23626eb055a309eae4d07a7b64420e5","session_id":"2230e10d-4d03-455b-8959-e11c686d6a68","cards_done":[1,2,3,4,5,6]}