{"status":"success","commit_sha":"c91b08edc5bb1285c9b9edc24ec8e574035dd5d0","session_id":"9705d416-d8a0-45dd-9231-2a2d05587ace"}

All 7 cards are complete. Verify is green (4 test suites, all PASS).

Summary of what was delivered:

- `plugins/mill/scripts/millpy-implement.py` — Card 1: accepts `--round` flag (ignored, for CLI-shape parity with `millpy-fix.py`); Card 2: prepare-stage atomicity via `git diff --cached --quiet` instead of the fragile `last_log`/`skip_start_commit` message comparison.

- `plugins/mill/scripts/_implementer_common.py` — Card 3: `_content_commit_count` function (subtracts the `mill-go: start batch` housekeeping commit from the raw `git rev-list --count`); Card 4: `_batch_completeness_stuck` updated to call `_content_commit_count`; Card 5: `_reclassify_verify_failure` at all four `_run_verify_gates` sites, plus `_gate_session_id` hoisted above the gate call in the parsed-success path to prevent `NameError`.

- `plugins/mill/unit_tests/test-millpy-implement.py` — Card 6: four test cases covering `--round` acceptance, prepare-retry dirty-staged commit, and prepare-refire skip.

- `plugins/mill/unit_tests/test-implementer-common.py` — Card 7: seven new cases (44a-50g) exercising all reclassification paths through `_forward_output` and `_batch_completeness_stuck` using real git repos with housekeeping commits.

{"status":"success","commit_sha":"c91b08edc5bb1285c9b9edc24ec8e574035dd5d0","session_id":"9705d416-d8a0-45dd-9231-2a2d05587ace"}
