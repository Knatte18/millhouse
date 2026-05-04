# Review: review-subsystem-fixes — Review subsystem: deleted-refs + execution infrastructure — 07-plan-validate-deletes

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: 07-plan-validate-deletes
date: 2026-05-04
```

## Findings

### [BLOCKING] Test helpers break after Card 26 lands
**Step:** Card 28 (also triggered by Card 26)
**Issue:** Card 26 adds `"Deletes"` to `_REQUIRED_CARD_FIELDS`. After that commit, `_make_batch_file` still emits no `- **Deletes:**` line, `_make_batch_file_cards` likewise, and the two inline batch texts in `test_check_reads_not_backtick_path_clean` and `test_check_reads_not_backtick_path_dirty` also have no `Deletes:` field — all 16+ existing tests will fail with spurious `card-missing-field` errors for `Deletes`.
**Fix:** Card 28 must explicitly require: (1) add a `deletes: list[str] | None = None` parameter to `_make_batch_file` that emits `- **Deletes:** {fmt(deletes)}\n` when `"Deletes"` is not in `missing_fields`; (2) add `"- **Deletes:** none\n"` to each card block in `_make_batch_file_cards`; (3) add `"- **Deletes:** none\n"` to the two inline batch text strings in the backtick-path tests.

### [NIT] Import of `compute_deletes_union` not stated
**Step:** Card 27
**Issue:** Card 27 says to call `compute_deletes_union(plan_dir)` in `run()` but never says to add `compute_deletes_union` to the `from _review_common import (...)` block.
**Fix:** Add `compute_deletes_union` to the explicit import list in the requirements sentence; saves the implementer a search.

## Verdict

REQUEST_CHANGES
Existing tests break after Card 26 unless the fixture helpers are updated; Card 28 must state those changes explicitly.