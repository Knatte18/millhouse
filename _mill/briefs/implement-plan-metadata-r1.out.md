All 4 cards (23, 24, 25, 26) of this batch are complete: 4 of 4 cards committed, combined into 2 commits (cards 23+24+25 into one commit since they all touch `_review_plan.py`, and card 26 as a separate commit for the test file). Verify (`test-review-plan-flow.py`) passes. Working tree is clean.

Summary of changes:
- `/home/hanf/Code/millhouse/wts/reviewer-cost-summary/plugins/mill/scripts/_review_plan.py` — threaded `duration_s`/`tool_calls`/`cost_usd` through `_review_one_batch` (per-batch region, including the deliberately file-less outer `ReviewError` handler), `finalize()` (agent-mode finalize path), and `run()`'s holistic block (all three success paths, the `NEED_CONTEXT` retry summation, and the two `LLMError`/parse-failure `ReviewError` branches).
- `/home/hanf/Code/millhouse/wts/reviewer-cost-summary/plugins/mill/unit_tests/test-review-plan-flow.py` — added 8 new test cases (Test 44-51) covering the holistic happy path, retry summation (including the None-absorbing case), holistic call-failure/parse-failure ERROR entries, the per-batch `finalize_scope` success path, the file-less outer `ReviewError` regression guard, and the pre-call `round_n > max_rounds` guard regression test.

{"status":"success","commit_sha":"0f2bbc6bcd9027b655755967547ca9280718b2ec","session_id":"32447dc8-2704-4479-be14-0e644bac2868","cards_done":[23,24,25,26]}
