MILL_REVIEW_BEGIN
# Review: plan validator and wiki-guard hook false positives — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-09-26
```

## Findings

### [NIT:consistency] Card 7 lists test-plan-validate.py under Edits with no matching change
**Location:** `_mill/plan/03-symbol-resolution.md` (Card 7 Edits), `_mill/plan/00-overview.md` (All Files Touched)
**Issue:** `plugins/mill/unit_tests/test-plan-validate.py` is in Card 7's `Edits:` but absent from the overview's "All Files Touched", and no requirement edits it (Grep finds no new framework/type-resolution references in it); the Batch Tests prose says it is only run as a regression check.
**Fix:** Record it as Context or drop it from Edits so the reference lists match the work.

### [NIT:design] Member-declared check runs before the own-refs coverage check
**Location:** `plugins/mill/scripts/_plan_validate.py:3307-3336`
**Issue:** Card 7 step 4 specifies covered-by-own-refs first, then member-declared. The code checks member-declared first (`_resolve_symbol_files(search_key, [type_file], {})`), then `_covered_by_own_refs`.
**Fix:** None needed. Both orders skip the token in the same cases and emit an error only when the member is declared and the file is not in own refs.

## Verdict

APPROVE
All cards are realised and cross-batch contracts hold; the only findings are non-blocking NITs.
MILL_REVIEW_END
