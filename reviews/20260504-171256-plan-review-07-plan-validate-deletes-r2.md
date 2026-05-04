# Review: review-subsystem-fixes — Review subsystem: deleted-refs + execution infrastructure — 07-plan-validate-deletes

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: 07-plan-validate-deletes
date: 2026-05-04
```

## Findings

### [BLOCKING] Fixture helpers break all existing tests after Card 26

**Step:** Cards 26 and 28
**Issue:** `_make_batch_file` and `_make_batch_file_cards` generate batch files with no `Deletes:` field. After Card 26 adds `"Deletes"` to `_REQUIRED_CARD_FIELDS`, every existing test that calls these helpers will produce an unexpected `card-missing-field` error — 16 of 18 tests fail. Card 27 says "verify the existing tests still pass after this card" but that is impossible without first updating the fixtures. Card 28 says "extend the file, don't replace" but never instructs updating the two fixture helpers.
**Fix:** Card 26 or Card 28 must explicitly require adding `- **Deletes:** none` output to both `_make_batch_file` (with a `deletes` kwarg defaulting to `None → "none"` and support for `"Deletes"` in `missing_fields`) and to `_make_batch_file_cards`. Also update the two custom `batch_text` literals in `test_check_reads_not_backtick_path_clean` and `test_check_reads_not_backtick_path_dirty`.

### [NIT] Missing import not mentioned in Card 27

**Step:** Card 27
**Issue:** Card 27 instructs calling `compute_deletes_union(plan_dir)` in `run()` but does not mention adding `compute_deletes_union` to the `from _review_common import (...)` block in `_plan_validate.py`.
**Fix:** Add one bullet to Card 27's requirements: "Add `compute_deletes_union` to the `from _review_common import` statement."

## Verdict

REQUEST_CHANGES — fixture helpers not updated for new `Deletes` field breaks all existing tests.