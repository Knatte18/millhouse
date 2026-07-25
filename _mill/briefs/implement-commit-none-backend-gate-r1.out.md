All 4 cards' commit subjects match exactly. 4 of 4 cards committed: cards 15, 16, 17, 18. Verify passed. Working tree is clean.

{"status":"success","commit_sha":"27feeee0","session_id":"84eb3604-3dc6-47de-ba4b-5255ad35f59b","cards_done":[15,16,17,18]}

Summary of work for batch `06-commit-none-backend-gate`:

- `/home/knatte/Code/millhouse/wts/mill-plan-review-validation-gaps/plugins/mill/scripts/_implementer_common.py` — added `_cards_done_all_commit_none` helper; threaded `commit_none_card_ids` (keyword-only) through `_reclassify_verify_failure`, `finalize_from_output`, and `_forward_output`; both top-level no-content-commit `if` conditions in `_forward_output` now also check the new exemption helper.
- `/home/knatte/Code/millhouse/wts/mill-plan-review-validation-gaps/plugins/mill/scripts/millpy-implement.py` — computes `commit_none_card_ids` from the batch file via `_plan_dag.parse_commit_none_card_ids` and threads it into both the `finalize_from_output` and `_forward_output` call sites.
- `/home/knatte/Code/millhouse/wts/mill-plan-review-validation-gaps/plugins/mill/unit_tests/test-implementer-common.py` — added cases 27c-27f covering the exemption firing, not overfiring on a mixed batch, the opt-in-only default, and the `_reclassify_verify_failure` direct-call path.

All 4 cards (15, 16, 17, 18) committed as 4 separate commits (`55bf1652`, `6544a5dd`, `dd260c26`, `27feeee0`), pushed to `hanf/mill-plan-review-validation-gaps`. Verify command `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-implementer-common.py` passes in full (all cases, including the 4 new ones). Working tree confirmed clean before this report.
