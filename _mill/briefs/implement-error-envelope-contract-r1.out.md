Both cards (2 of 2) are committed and match the batch's Commit: messages exactly. Verify passed with exit code 0. No uncommitted tracked changes remain.

{"status":"success","commit_sha":"1ca7ef0b790659316a5349b666e21caa7ffcb007","session_id":"4d0cad78-cd98-446f-958e-3b53e4ae645c","cards_done":[1,2]}

Summary: 2 of 2 cards committed for batch `01-error-envelope-contract`.

- `/home/knatte/Code/millhouse/wts/review-pipeline-consistency-bugs/plugins/mill/scripts/_review_cli.py` — `print_error_envelope` now accepts keyword-only `error_kind: str = "usage"` and `round: int = 0`, threading `round` into the envelope's top-level field and `error_kind` into the single `reviews[0]` dict.
- `/home/knatte/Code/millhouse/wts/review-pipeline-consistency-bugs/plugins/mill/unit_tests/test-review-cli.py` — `test_print_error_envelope_shape` extended to assert the default `error_kind == "usage"` on the existing no-arg "plan" call, plus a new explicit `error_kind="reviewer", round=7` call asserting both values thread through.

Verify command `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-review-cli.py` passed (exit 0). Ruff flagged 21 pre-existing lint issues in the test file, confirmed unchanged from `main` (verified via `git show main:...` + ruff diff) — none introduced by this batch's edits.

{"status":"success","commit_sha":"1ca7ef0b790659316a5349b666e21caa7ffcb007","session_id":"4d0cad78-cd98-446f-958e-3b53e4ae645c","cards_done":[1,2]}