# Batch: plan-validate-deletes

```yaml
task: 'review-subsystem-fixes — Review subsystem: deleted-refs + execution infrastructure'
batch: plan-validate-deletes
cards: 3
verify: uv run --project "${CLAUDE_PLUGIN_ROOT}" python "${CLAUDE_PLUGIN_ROOT}/unit_tests/run-all.py"
depends-on: [content-helpers]
```

## Batch Scope

Teaches `_plan_validate.py` about the new `Deletes:` field. Adds `Deletes` to the validator's `_REQUIRED_CARD_FIELDS` and `_RE_REFS_HEADER` so every card must declare it. Extends `_check_non_existent_path` with a `deletes_union` parameter so `Reads:`/`Modifies:` tokens that resolve to intentionally-deleted files are silent-suppressed; `Deletes:` tokens themselves require the path to exist on disk OR be in `creates_union` at validation time. Tests cover every case the discussion's testing section enumerates. Independent of the backend integration batches — only `_plan_validate.py` and its unit test change.

Out of scope here: extending `_check_all_files_touched_mismatch` to include `Deletes` tokens in the cards-set; cross-card consistency check ("Deletes: of card N collides with Reads:/Modifies: of card M>N"). Both flagged for a future task.

## Cards

### Card 26: Add `Deletes` to validator regex and required fields

- **Reads:**
  - `plugins/mill/scripts/_plan_validate.py`
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Modifies:**
  - `plugins/mill/scripts/_plan_validate.py`
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Update the local `_RE_REFS_HEADER` regex constant in `_plan_validate.py` (top of file) to alternate over `Reads|Modifies|Creates|Deletes` instead of the current three-way alternation — matching the change to `_review_common._RE_REFS_HEADER` from Card 1. Update `_REQUIRED_CARD_FIELDS` from `["Reads", "Modifies", "Creates", "Requirements", "Commit"]` to `["Reads", "Modifies", "Creates", "Deletes", "Requirements", "Commit"]` so `_check_card_missing_field` flags any card without a `Deletes:` field (including the "none" sentinel form `- **Deletes:** none`). Update the test-side fixture helpers in `unit_tests/test-plan-validate.py` so the existing test suite continues to pass after this change: extend `_make_batch_file` and `_make_batch_file_cards` (the two card-emitting helpers in that file) to emit a `- **Deletes:** none` line between the existing `- **Creates:**` and `- **Requirements:**` lines by default, accepting a `deletes` kwarg (default `None → "none"`) and supporting `"Deletes"` in the `missing_fields` parameter. Also update the two custom `batch_text` literals inside `test_check_reads_not_backtick_path_clean` and `test_check_reads_not_backtick_path_dirty` to include `- **Deletes:** none` on each card so they don't trip the new required-field check. No other changes in this card.
- **Commit:** `feat(plan-validate): require Deletes: field on every card`

### Card 27: Extend `_check_non_existent_path` with `deletes_union`

- **Reads:**
  - `plugins/mill/scripts/_plan_validate.py`
  - `plugins/mill/scripts/_review_common.py`
- **Modifies:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `run()` of `_plan_validate`, after the existing `creates_union = compute_creates_union(plan_dir)` line, add `deletes_union = compute_deletes_union(plan_dir)`. Add `compute_deletes_union` to the existing `from _review_common import (...)` block in `_plan_validate.py` so the new call resolves. Add a new keyword parameter `deletes_union: set[str]` to `_check_non_existent_path` (after `creates_union`) and pass it through. Inside `_check_non_existent_path`: split the per-batch token scan into two paths so general refs vs Deletes refs apply different rules. Concrete shape: add a private helper `_parse_deletes_only(batch_path: Path) -> set[str]` next to the existing `_parse_modifies_only` (mirror its body, but match `m.group(1) == "Deletes"`). In `_check_non_existent_path`'s loop body: (a) for each token from `parse_batch_refs(batch_path)` MINUS `_parse_deletes_only(batch_path)` — the general refs, treated as Reads/Modifies/Creates: a missing-on-disk token is suppressed if `t in creates_union OR t in deletes_union` (existing creates-union behaviour PLUS new deletes-union suppression), otherwise it's a `non-existent-path` error. (b) For each token in `_parse_deletes_only(batch_path)` — the Deletes refs: a missing-on-disk token is suppressed if `t in creates_union` (cross-batch case where an earlier batch creates it and this card deletes it), otherwise it's a `non-existent-path` error with message `f"Deletes: token '{t}' does not exist on disk and is not a Creates: target in any batch"`. Existing message for general refs stays as-is. Verify the existing tests still pass after this card; add the new tests in Card 28.
- **Commit:** `feat(plan-validate): Deletes-aware non-existent-path check`

### Card 28: Tests for `_plan_validate` Deletes-aware behaviour

- **Reads:**
  - `plugins/mill/scripts/_plan_validate.py`
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Modifies:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add fixtures + assertions for every case in `discussion.md` `## Testing` for `_plan_validate`. Use `tempfile` to build minimal plan_dir fixtures (overview + 1-2 batch files). Cases: (a) `_REQUIRED_CARD_FIELDS` includes `"Deletes"` — a card without a `- **Deletes:**` line produces a `card-missing-field` error with `message` containing `"missing required field: Deletes:"`. (b) `Deletes:` token resolves to an on-disk file → no error. (c) `Deletes:` token missing on disk + token also appears in another batch's `Creates:` (so it's in `creates_union`) → no error (cross-batch case). (d) `Deletes:` token missing on disk + not in any `Creates:` → `non-existent-path` error whose `message` starts with `"Deletes: token '"`. (e) `Reads:` token missing on disk + appears in another batch's `Deletes:` (so it's in `deletes_union`) → no error (suppressed by deletes_union — the file is intentionally going away). (f) `Reads:` token missing on disk + in `creates_union` → no error (existing behaviour preserved). (g) `Reads:` token missing on disk + in NEITHER union → `non-existent-path` error (existing behaviour preserved). Existing tests in `test-plan-validate.py` must continue to pass — extend the file, don't replace.
- **Commit:** `test(plan-validate): cover Deletes-aware path checks`

## Batch Tests

`uv run --project "${CLAUDE_PLUGIN_ROOT}" python "${CLAUDE_PLUGIN_ROOT}/unit_tests/run-all.py"` — `test-plan-validate.py` covers Cards 26–28. The full suite must be green at end of batch.
