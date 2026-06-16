# Batch: ascii-arrow-fix

```yaml
task: Fix unit test suite failures, spurious review warning, and implementer verify-gate gaps
batch: ascii-arrow-fix
number: 2
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-guards.py test-claude-sub.py
depends-on: []
```

## Batch Scope

A single-line ASCII fix (#486): `test-claude-sub.py` contains literal U+2192
(`->`) arrow characters in two comments, which trips the `no_unicode_arrow`
guard in `test-guards.py` and fails the suite on every run. Replace them with
ASCII `->`. Comment-only change; no test logic or behaviour is affected.

## Cards

### Card 4: Replace U+2192 arrows with ASCII in test-claude-sub.py (#486)

- **Context:**
  - `plugins/mill/unit_tests/test-guards.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-claude-sub.py`
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `test-claude-sub.py`, replace each literal U+2192 (the `->`
  arrow character) with the two-character ASCII sequence `->`. The known
  occurrences are in the comments at lines ~775 and ~787 (Scenario (b)/(c)
  comments); search the whole file for any other U+2192 and replace those too.
  Touch only the arrow characters — do not alter surrounding comment wording or
  any code. After the change, `test-guards.py`'s `_check_no_unicode_arrow` reports
  PASS.
- **Commit:** `fix(tests): replace U+2192 arrows with ASCII in test-claude-sub.py (#486)`

## Batch Tests

`verify:` runs `run-all.py --only test-guards.py test-claude-sub.py`.
`test-guards.py` is the acceptance gate (its `no_unicode_arrow` check must PASS);
`test-claude-sub.py` is re-run to confirm the comment edit did not disturb its
own test cases. Both are scoped to this batch's single edited file plus its guard.
