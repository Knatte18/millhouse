MILL_REVIEW_BEGIN
# Review: _plan_validate context-completeness: further false-positive/false-negative gaps, round 3 — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/
date: 2026-09-23
```

## Findings

None. Verified each card's mechanism claims directly against `plugins/mill/scripts/_plan_validate.py` current source and against `plugins/mill/unit_tests/test-plan-validate.py`'s existing fixtures:

- Card 1's `_RE_INLINE_ASSIGN_DECLARATION` behavior against `_compute_declared_symbols_union` (lines 2582-2648) traced by hand for both verified examples (`StepDurationS`, `bare_timeout_value`) — regex backtracking confirms both claimed outcomes.
- Card 2's leading-assign-prefix strip traced against `_symbol_candidate_shape` (lines 2054-2114), confirming `x = mod.get_value(args)` reduces to qualifying dotted pair `mod.get_value`.
- Card 3's majority-tally rewrite of `_is_literal_enumeration_exempt` (lines 1896-1924) hand-traced for the #984 fixture (5 shaped/3 non-shaped, no exemption) and the #1116 repro (2 shaped/1 non-shaped, no exemption, 1 finding) — matches card's stated outcomes.
- Card 4's `_resolve_symbol_files` signature/body rewrite verified against current implementation (lines 2146-2285) and `resolve_existing_paths` (`_review_common.py` lines 1136-1196, confirms per-token 0-or-1 return shape used by `_compute_plan_wide_cited_files`). The 7 deleted tests and `test_check_context_completeness_symbol_cache_invoked_once_per_key`/`qualifier_cache_correctness_different_qualifiers` fixtures read and confirmed to match the stated rationale.
- Card 5's audit criterion spot-checked against `test_check_context_completeness_symbol_dirty_missing` (needs migration, caught by verify), `test_check_context_completeness_symbol_all_lowercase_not_candidate` (shape-gate rejection, correctly excluded), and `test_check_context_completeness_symbol_clean_test_file_excluded_all_languages` (correctly in the "already-zero, migrate anyway" list).
- Card 6's fence/run-exclusion design cross-checked against `_requirements_fence_aware_body` (lines 3127-3168) and the current per-line loop (lines 2814-2992); the plan's departure from `_parse_cards`'s toggle convention is internally justified and consistent.
- The batch's "no other test file needs to run" claim: a grep hit in `test-review-templates.py` is a docstring-comment mention only (no import/call), so the claim holds in effect.

All six Shared Decisions are faithfully implemented in their respective cards; card ordering (1-3 independent, 4→5→6 dependent) is correct; no Moves in this batch so no Rename-mechanic requirement applies; verify: command is properly `PYTHONPATH=`-prefixed and `--only`-scoped in both overview and batch frontmatter.

## Verdict

APPROVE
Plan mechanisms verified against current source; no remaining false-positive/false-negative gaps found in this round.
MILL_REVIEW_END
