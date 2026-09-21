MILL_REVIEW_BEGIN
# Review: _plan_validate.py: further context-completeness, fence/indent-drift, and tag-exclusion gaps — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-09-21
```

## Findings

None. Verified all 7 batch-1 cards against `plugins/mill/scripts/_plan_validate.py`:

- Card 1 (`_check_move_target_collision` intra-plan chain): `moves_sources` param added, `dst not in moves_sources` guard at line 602, `run()` threads `moves_sources` positionally at line 4427. Tests `test_move_target_collision_intra_plan_chain_same_batch_clean`/`_cross_batch_clean`/`_not_a_moves_source_still_dirty` present and registered.
- Card 2 (`_card_own_reference_set` Moves-target exemption): both `pair_m.group(1)`/`group(2)` collected at lines 2024-2025, docstring updated. Tests for declaring-card exemption and cross-card non-exemption both present (`test_check_context_completeness_clean_move_target_exempt_in_declaring_card`, `..._dirty_move_target_not_exempt_in_other_card`).
- Card 3 (`_compute_declared_symbols_union` + exemption 14): helper matches spec byte-for-byte (widest-span tie-break, first/last word extraction), wired into `_check_context_completeness` signature/materialization/exemption placement and into `run()`. Same-card, cross-card, and negative tests all present (lines 3220, 3264, 3319).
- Card 4 (`_is_conventional_test_file`): per-extension logic matches spec (`.go`/`.py`/`.cs`/`.ts`), placed immediately before `_resolve_symbol_files`, skip added at line 2264 before content read. Combined 4-language test present at line 3363.
- Card 5 (`_symbol_candidate_shape` length gates): `qualifies()` requires `len(segment) > 1`; dotted branch disqualifies `len(qualifier) <= 1` before trailing-segment check. All three tests present (single-letter qualifier, single-letter bare, two-letter-still-fires).
- Card 6 (`cs_member_re` `new`-exclusion): pattern updated to `(?:(?!\bnew\b).)*?` exactly as specified. Both the new-expression-suppressed test and the still-fires member-declaration regression test present.
- Card 7 (paired-fence indent-drift): `_first_nonblank_line_indent` helper, `last_matched_indent`/`last_matched_token` tracking through clean/strip/add passes, and the new paired-fence comparison block all match the plan's line-by-line instructions. All four scenario tests (mismatched, matching, no-prior-anchor, no-chain-across-trailing) present and registered.
- Card 8 (SKILL.md fix-table doc): `verify-excludes-edited-tagged-test` row's both branches now derive package pattern from the flagged file's own directory; `requirements-quote-indent-drift` row's "In both cases" → "In the first two cases" edit plus the new third-message-shape sentence both present verbatim. `move-target-collision`/`context-completeness` rows correctly left untouched (no message-text change was needed for either fix).

Cross-batch checks: `run()` wiring for `declared_symbols`/`moves_sources` is consistent with both consumers; `## All Files Touched` matches the three edited files; no out-of-plan files present; no duplicate helper definitions found (`_first_nonblank_line_indent`, `_is_conventional_test_file`, `_compute_declared_symbols_union`, `_card_own_reference_set` each defined exactly once). Test file registers all 337 defined `test_` functions in `main()`'s `tests` list (counts match 1:1).

## Verdict

APPROVE
All 7 code cards and the doc card match their plan specs exactly; tests cover happy/negative paths and are wired in.
MILL_REVIEW_END
