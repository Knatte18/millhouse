Both cards (2 of 2) committed, matching the batch's declared card count of 2. Verify passed. Nothing tracked is dirty.

Summary: 2 of 2 cards committed. Card 1 added `_RE_SHELL_OPERATOR` and `_RE_GO_TEST_INVOCATION` regex constants, the `done_gate` parameter, and rewrote the Go-test detection to be segment-scoped in `plugins/mill/scripts/_plan_validate.py`. Card 2 added the `done_gate` keyword-only parameter to `run()` and threaded `cfg.get("pipeline", {}).get("done_gate")` through all three call sites in `plugins/mill/scripts/millpy-review-plan.py` and `plugins/mill/scripts/millpy-validate-plan.py`. The full `test-plan-validate.py` suite (83 tests) passed with no regressions.

Files touched (all absolute paths under `/home/knatte/Code/millhouse/wts/plan-validate-verify-command-validation-bugs`):
- `plugins/mill/scripts/_plan_validate.py`
- `plugins/mill/scripts/millpy-review-plan.py`
- `plugins/mill/scripts/millpy-validate-plan.py`

{"status":"success","commit_sha":"f7fc54107b5ed795f0070ca61746c13425322510","session_id":"8125a945-86f9-4c4d-a210-d641fc75bc29","cards_done":[1,2]}
