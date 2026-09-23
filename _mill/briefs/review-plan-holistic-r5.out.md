MILL_REVIEW_BEGIN
# Review: _plan_validate context-completeness: further false-positive/false-negative gaps, round 3 — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: plan/
date: 2026-09-23
```

## Findings

### [BLOCKING:scope] Card 5's audit misses a test tied to a mechanism Card 4 deletes
**Location:** batch 1, cards 4-5. **Issue:** `test_check_context_completeness_symbol_issue_1030_deprecated_directory_property` (test-plan-validate.py:5576) asserts 0 errors specifically because its fixture file sits under a `Deprecated/` dir pruned by `_SYMBOL_SEARCH_OUT_OF_SCOPE_DIRS` — the exact mechanism card 4 deletes outright — yet it is absent from card 4's explicit 6-test deletion list (only the 5 `..._out_of_scope_...`-named tests and `..._first_match_wins_root_precedence` are named). **Verified:** confirmed via source read that `_resolve_symbol_files` (post-card-4) drops the deleted constants entirely, and the test's own fixture (`internal/Deprecated/Legacy.cs`, uncited by any card) is not in card 4's or card 5's named-exception lists. Card 5's generic "add a second batch citing the file" recipe is UNSAFE here: citing the file makes it a candidate under the new design (no more dir pruning), so `StatusFlag` resolves and the card's own Requirements: reference flips the assertion from 0 to 1 errors — breaking the test, not migrating it. Left un-migrated, the test still passes green (file stays uncited → excluded from search either way) but silently stops testing anything about deprecated-dir handling (a feature this plan removes). **Fix:** add this test's name to card 4's deletion list alongside the other 6 (or explicitly except it from card 5's grep-audit with a deletion note, mirroring how `_first_match_wins_root_precedence` was handled).

### [BLOCKING:scope] Card 5's "run verify to green" backstop doesn't catch skipped migrations whose outcome is already 0 errors
**Location:** batch 1, card 5. **Issue:** Several remaining symbol-branch tests place their target fixture file(s) outside every card's own refs AND outside every other card's refs (fully uncited plan-wide): `clean_ambiguous_matches`, `qualifier_no_match_still_zero`, `qualifier_ambiguous_dirs_still_zero`, `comment_only_{go,cs,py,ts}`, `string_literal_only_{go,cs,py,ts}`, `usage_site_only_{go,cs,py,ts}`, `clean_test_file_excluded_all_languages` (verified by reading each fixture: e.g. `comment_only_go`'s `internal/handler.go` is never cited, only `other.py` is edited). Post-rework, an un-migrated instance of these produces 0 errors for the WRONG reason (file simply excluded from the narrowed search) rather than exercising the intended branch (`_has_declaration` comment/string/usage rejection, `_filter_matches_by_qualifier` still-ambiguous, `_is_conventional_test_file` exclusion). Card 5's own stated backstop — "Running verify... to green is the authoritative completeness check for this card, not a manual tally" — is false for exactly this subset, since the assertion value (0) is identical whether migrated or silently skipped. **Fix:** state explicitly that the audit criterion "assertions depend on resolution being attempted" includes tests whose 0-error outcome depends on a specific rejection branch (ambiguous/qualifier-mismatch/comment-only/string-only/usage-only/test-file-excluded), not only tests asserting a nonzero error count, so this class isn't silently skipped by an implementer relying solely on the green-verify signal.

### [NIT:consistency] `_compute_plan_wide_cited_files` omits the card_text join step
**Location:** batch 1, card 4. **Issue:** Requirements says "for every card returned by `_parse_cards(...)`, union `_card_own_reference_set(card_text)`'s tokens" but `_parse_cards` returns `(card_num, card_lines)` pairs, not `card_text` — the `card_text = "\n".join(card_lines)` step every other caller in this file performs is left implicit. **Fix:** state the join explicitly in this card's Requirements, matching `_check_context_completeness`'s own established pattern.

## Verdict

REQUEST_CHANGES
Card 5's migration audit has one unsafe recipe application and one backstop gap that verify-green won't surface.
MILL_REVIEW_END
