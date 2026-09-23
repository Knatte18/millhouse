MILL_REVIEW_BEGIN
# Review: _plan_validate context-completeness: further false-positive/false-negative gaps, round 3 — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-09-23
```

## Findings

### [BLOCKING:scope] Two symbol-branch exemption tests not migrated per card 5's own audit criterion
**Location:** `plugins/mill/unit_tests/test-plan-validate.py:4431-4466` (`test_check_context_completeness_symbol_prohibition_marker_exempt`) and `:4469-4504` (`test_check_context_completeness_symbol_citation_marker_exempt`)
**Issue:** Both fixtures write `internal/state.go` (declaring `SaveState`) to disk but cite it in NO card's `Context:`/`Edits:`/etc. anywhere in their single-batch plan. Verified against `_plan_validate.py:2606-2655` (`_compute_plan_wide_cited_files`) and `:2894` (`candidate_files = list(dict.fromkeys(cited_files_map.values()))`): since nothing cites `internal/state.go`, it is absent from `candidate_files`, so `_resolve_symbol_files` (`:2197-2309`) returns `[]` regardless of whether `_is_prohibition_exempt`/citation-marker matching (checked earlier, at `:2987`/`:3003`, before the resolution call at `:3141-3146`) fire correctly or not. Both tests assert 0 errors and pass either way, so they silently stopped proving the exemption applies to the symbol branch post-narrowing — exactly the "found-then-rejected vs. never-searched" trap card 5's Requirements (batch file lines 355-375) explicitly warns about and instructs auditing for beyond its named list ("apply this same criterion... in case further members of this class exist beyond the ones named here").
**Fix:** Add a second, citing-only batch (per the same generic recipe used correctly elsewhere, e.g. `test_check_context_completeness_symbol_comment_only_go`) whose `Context:` names `internal/state.go`, in both tests, so resolution is actually attempted and the exemption is the reason for 0 errors.

## Verdict

REQUEST_CHANGES
Card 5's test-migration audit missed two symbol-branch exemption tests that now pass vacuously via unresolvability, not via the exemption they claim to prove.
MILL_REVIEW_END
