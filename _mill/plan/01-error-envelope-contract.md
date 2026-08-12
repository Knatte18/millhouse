# Batch: error-envelope-contract

```yaml
task: 'millpy-review-plan finalize: usage-error indistinguishability, flag issues, verdict rendering stale'
batch: error-envelope-contract
number: 1
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-review-cli.py
depends-on: []
```

## Rename mechanic

N/A — no `Moves:` in this batch.

## Batch Scope

Change `_review_cli.py::print_error_envelope`'s signature to accept two new optional keyword
parameters — `error_kind: str = "usage"` and `round: int = 0` — and use them in the emitted JSON
envelope instead of the current hardcoded `"round": 0` and the current `reviews[0]` dict that has
no `error_kind` key at all. This is the foundational contract change every other batch in this
plan either calls into (Batch 2) or reads the resulting field from (Batch 5); Batch 3 does not
call `print_error_envelope` at all (it edits a different, parallel code path) and is intentionally
not gated on this batch. No caller is updated in this batch — every existing call site keeps
working unmodified because both new parameters have defaults matching today's exact behavior
(`error_kind="usage"`, `round=0`), so this batch's own `verify:` (the existing
`test-review-cli.py` suite) passes without any call-site change.

## Cards

### Card 1: `print_error_envelope` gains `error_kind` and `round` parameters

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_review_cli.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Change `print_error_envelope`'s signature from `print_error_envelope(review_type: str, msg: str) -> None` to `print_error_envelope(review_type: str, msg: str, *, error_kind: str = "usage", round: int = 0) -> None`.
  - Replace the envelope's hardcoded `"round": 0` field with `"round": round` (the new parameter).
  - Add `"error_kind": error_kind` as a new key inside the single dict in the `"reviews"` list (alongside the existing `"scope"`, `"verdict"`, `"error"`, `"findings"` keys) — do not add it at the envelope's top level.
  - Update the function's docstring to document the two new parameters and their defaults, following the existing `Args:` block style already used for `review_type`/`msg`.
  - Do not change `print_error`'s signature or body — it is a separate, unrelated function in the same file.
- **Commit:** `fix(review): print_error_envelope gains error_kind and round parameters`

### Card 2: extend `test_print_error_envelope_shape` for the new parameters

- **Context:**
  - `plugins/mill/scripts/_review_cli.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-cli.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In `test_print_error_envelope_shape` (the existing test function), after the three existing `print_error_envelope(...)` calls (for `"plan"`, `"discussion"`, `"code"`), add a fourth assertion block that calls `print_error_envelope("plan", "some error message")` with no explicit `error_kind`/`round` args and asserts the parsed envelope's `reviews[0]["error_kind"] == "usage"` and `envelope["round"] == 0` — locking in the defaults (this can reuse the envelope already parsed at the top of the function for the `"plan"` case rather than calling again, since that call already uses no explicit params).
  - Add a new, separate assertion block in the same test function that calls `print_error_envelope("plan", "explicit error", error_kind="reviewer", round=7)` and asserts the parsed envelope's `envelope["round"] == 7` and `reviews[0]["error_kind"] == "reviewer"`.
  - Follow the file's existing failure-reporting convention exactly: on each new assertion failure, `print(f"FAIL ...: ...", file=sys.stderr)` then `failures += 1`, matching the style of every other check already in this function. Do not introduce `assert` statements or a different reporting style into this function.
  - Do not modify any other test function in this file.
- **Commit:** `test(review): assert print_error_envelope's error_kind default and round threading`

## Batch Tests

`verify:` runs `test-review-cli.py`, which contains `test_print_error_envelope_shape` (extended by
Card 2) plus the file's other pre-existing tests (`test_review_cli_emits_envelope_on_config_failure`,
`test_review_cli_emits_envelope_on_reviewer_load_failure`, `test_review_cli_emits_envelope_on_slug_failure`,
the three `*_prepare_brief_path_*` tests, `test_finalize_actual_model_flag_reflected_in_review_file`) —
none of those read `error_kind` or `round`, so they continue to pass unmodified against the new
defaulted parameters, confirming this batch is a pure additive change with no observable behavior
shift for any existing caller.
