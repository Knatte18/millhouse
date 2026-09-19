MILL_REVIEW_BEGIN
# Review: _plan_validate.py context-completeness: path-token exemption list gaps — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 5 (claude-sonnet-5)
reviewed_file: plan/
date: 2026-09-19
```

## Findings

### [BLOCKING:design] `_OWNERSHIP_RE` cannot match its own possessive test case
**Location:** Batch 1, Card 1 (`_OWNERSHIP_RE`); exercised by Batch 2, Card 4's `test_check_context_completeness_clean_ownership_possessive`.
**Issue:** The regex is `\b(?:batch|card)\s+\d+\s+(?:'s\s+)?(?:VERB)\b` — the mandatory `\s+` right after `\d+` requires whitespace between the number and `'s`, but the possessive form has none ("`batch 8's fix`"), so `\d+\s+` never matches and the whole pattern fails on exactly the phrasing the card's own docstring claims it supports ("optionally possessive, e.g. \"batch 8's fix\"").
**Fix:** Change the middle group to `\d+(?:'s)?\s+` (or equivalent) so the apostrophe-s attaches directly to the digits before the required whitespace.

### [BLOCKING:consistency] Dirty ownership/output tests never make their token resolvable
**Location:** Batch 2, Card 4 (`..._no_number_not_exempted`, `..._separate_line_not_exempted`) and Card 6 (`..._no_verb_not_exempted`).
**Issue:** Card 4's only file-creation instruction is scoped to "asserted clean (0 errors)" cases; none of these three dirty (1-error) tests is told to create `x.py`/`README.md` on disk or declare it as a `Creates:` target elsewhere. Per the existing mechanism (verified against `_check_context_completeness`'s `resolvable = existing_files or creates_union or deletes_union or moves_targets` gate, and against sibling test `test_check_context_completeness_dirty_quoted_material_prose_after_fence_closed`, which explicitly writes `fixtures/alpha.py` to disk before asserting its 1 error), an unresolvable token is silently skipped — these three tests would get 0 errors, not the asserted 1, and fail. Card 5's own dirty tests (same batch) correctly spell out "with a real `README.md` on disk" / "with all three files created" — this instruction was simply dropped for Card 4 and Card 6's dirty cases.
**Fix:** Add an explicit "create a real `x.py`/`README.md` under `project_root`" instruction to each of the three dirty tests, mirroring Card 5's phrasing.

### [NIT:consistency] Card 2's stated rationale for `_BACKTICK_RE`'s placement is inaccurate
**Location:** Batch 1, Card 2.
**Issue:** Card 2 justifies placing `_BACKTICK_RE` "immediately above `_OWNERSHIP_VERB_FORMS` from Card 1, since both Card 1's future callers and this function need it at module scope" — but Card 1's `_is_cross_card_ownership_exempt` never uses `_BACKTICK_RE`; only Card 2's own function does.
**Fix:** Drop the "both Card 1's future callers and" clause; the placement itself is fine, only the justification is wrong.

## Verdict

REQUEST_CHANGES
The ownership-regex possessive bug and three under-specified dirty-test fixtures will fail this plan's own `verify:` step.
MILL_REVIEW_END
