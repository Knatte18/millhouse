All 3 of 3 cards are committed and pushed, and the verify command passes (44 tests, both files OK).

- Card 5: removed `--recompute-baseline`, `_run_recompute_baseline` and the `_verify_baseline` import from `millpy-merge-in-subagent.py`; the error message is now `--mode is required`. The scoped ruff check flagged `_plan_dag` and `_status` as unused after the deletion, so I removed both imports.
- Card 6: removed the recompute-baseline tests and their two helpers from `test-millpy-merge-in-subagent.py`, updated `test_9_missing_mode`, and added `test_recompute_baseline_flag_rejected`. I also removed the now-unused `import _status` from that test file.
- Card 7: deleted step `### 3.5. Baseline recompute` from `mill-merge-in/SKILL.md`; the remaining steps are not renumbered. Two "recompute" hits remain in that file (lines 116 and 173) and are unrelated.

{"status":"success","commit_sha":"dd56e3a62ed68f2a8039c6ac192c1d82cbe84df9","session_id":"f2ec1e2f-2869-48c9-bf4c-cf6b71d4959c","cards_done":[5,6,7]}
