# Batch: stale-test-corrections

```yaml
task: "Fix pre-existing unit-test failures, CRLF cleanliness false-positive, and review false-BLOCKING on Go"
batch: stale-test-corrections
number: 3
cards: 2
verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-finalize.py test-agent-mode-dispatch.py"
depends-on: []
```

## Batch Scope

Two test-only failures where the production code is correct and must stay untouched: (1) `test-review-finalize.py` asserts the old "`--round` required everywhere" contract, but commit `8a5fefac` deliberately switched plan/discussion finalize to auto-discover the round via `discover_round` (code finalize still requires it); (2) `test-agent-mode-dispatch.py`'s `test_implementer_parity_finalize_stage` uses a constant-SHA subprocess mock so finalize's `git rev-parse HEAD` equals the prepare-recorded `start_sha`, tripping the legitimate no-content-commit gate. Both cards fix the tests/fixtures only. This batch shares no files with the other batches. Batch-local decision: do NOT modify any `millpy-review-*.py` or `_implementer_common.py` production code in this batch — if a test cannot pass without a prod change, that is a signal to stop, not to edit prod.

## Cards

### Card 9: Update finalize --round tests to the auto-discovery contract

- **Context:**
  - `plugins/mill/scripts/millpy-review-plan.py`
  - `plugins/mill/scripts/millpy-review-discussion.py`
  - `plugins/mill/scripts/millpy-review-code.py`
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-finalize.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** `test_review_plan_finalize_round_required` and `test_review_discussion_finalize_round_required` assert that finalize without `--round` returns `rc == 1` and does not call `prepare()`. That contradicts the intended behavior: plan and discussion finalize auto-discover the round via `discover_round(...)` when `--round` is absent. Invert both tests so they assert finalize **succeeds** without `--round` (round auto-discovered) and `prepare()` is still not called — mock `_review_common.discover_round` to return a round integer (e.g. 1) in each test's `mock_modules["_review_common"]`, mirroring the existing no-prepare tests' mocking. Keep `test_review_code_finalize_round_required` unchanged (code finalize still requires `--round`). Update the two functions' docstrings and the `main()` aggregator pass/fail print strings to reflect the auto-discovery assertion. Do not edit any production file.
- **Commit:** `test(review): assert plan/discussion finalize auto-discovers round`

### Card 10: Fix dispatch finalize-parity fixture to make a real content commit

- **Context:**
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-agent-mode-dispatch.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `test_implementer_parity_finalize_stage`, the fixture mock (`mock_subprocess_run`, around the class setup) returns a constant `stdout` (`"abc1234\n"`) for every `_subprocess_util.run`, so prepare records `start_sha = "abc1234"` and finalize's no-content-commit gate (`_forward_output` in `_implementer_common.py`) sees `git rev-parse HEAD == start_sha` and demotes the envelope to `stuck/logic`. Adjust the mock so the `git rev-parse HEAD` call observed during the finalize stage returns a SHA different from the prepare-time `start_sha` (e.g. give the mock a `side_effect` that yields `abc1234` while prepare runs and a distinct SHA such as `def5678` during finalize, or otherwise scope a different `rev-parse HEAD` result to the finalize call). After the fix, `test_implementer_parity_finalize_stage` must assert `data["status"] == "success"` with `commit_sha` present and `session_id == "fake-session"`, and the LLM `run` must not be called. Do not change the production no-content-commit gate or any `_implementer_common.py` / `millpy-implement.py` code.
- **Commit:** `test(dispatch): make finalize-parity fixture commit a distinct HEAD sha`

## Batch Tests

`verify:` runs `test-review-finalize.py` (card 9: code-finalize `--round` still required; plan/discussion finalize succeed via auto-discovery; the no-prepare tests stay green) and `test-agent-mode-dispatch.py` (card 10: finalize-parity now returns success; the prepare-parity and reviewer-parity tests stay green). Both scoped via `run-all.py --only`. Test-only batch — there is no production surface to verify beyond the corrected assertions.
