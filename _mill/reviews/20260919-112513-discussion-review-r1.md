MILL_REVIEW_BEGIN
# Review: _plan_validate.py context-completeness: path-token exemption list gaps

```yaml
duration_s: 217.0
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-09-19
```

## Findings

### [NIT:consistency] Ownership exemption's clause-scoping contradicts its own #1022 example
**Demoted-from:** BLOCKING
**Section:** Decisions > Ownership-phrase exemption; Testing > Ownership exemption.
**Issue:** The decision reuses `_clause_bounds` (verified in `_plan_validate.py`), whose comma-boundary semantics are demonstrated by the existing `test_check_context_completeness_dirty_contrast_citation_comma_clause_boundary` test: a comma before a marker phrase puts it in a *different* clause from the token, so the exemption does NOT fire. The verbatim #1022 shape -- "the stale prose reference in `x.cs`, **which batch 8 fixes**." -- has exactly that comma between the token and the ownership verb phrase, so under the stated clause-scoped mechanism it would land in a separate clause and stay flagged (dirty), not exempted. This directly contradicts `test_check_context_completeness_clean_ownership_batch_fixes`, which expects this exact sentence to be clean, and also contradicts the discussion's own `..._dirty_ownership_separate_clause_not_exempted` test, which requires a comma-separated ownership phrase to NOT be exempt -- the two tests specify opposite outcomes for the same comma-separated shape.
**Fix:** Either scope the ownership regex line-wide (like `_is_prohibition_exempt`, not clause-wide) and revise the "separate clause" guard test accordingly, or rewrite the #1022 clean-test fixture without the comma and explicitly document why the real-world #1022 phrasing (with its comma) is intentionally left unfixed.

### [NIT:consistency] Threshold rationale direction is backwards
**Section:** Q&A log, literal-enumeration threshold question.
**Issue:** "3 or more ... (Recommended -- above the reported example's own list of 7...)" -- 3 is below 7, not above it; the rationale's wording contradicts the numbers it cites.
**Fix:** Reword to "safely below the reported example's 7-token list" (or similar) so the rationale reads correctly.

### [NIT:design] Mixed-shape literal-enumeration heuristic's false-negative risk on genuine dependency lines is unacknowledged
**Section:** Decisions > Literal-value enumeration exemption.
**Issue:** The rule exempts every backtick token on a 3+-token line once any one token fails both the path-shape and `_symbol_candidate_shape` tests. A genuine dependency enumeration that also cites one non-path/non-symbol literal on the same line (e.g. a CLI flag or sentinel string alongside real file paths) would be wrongly swept in and suppressed -- unlike `_is_prohibition_exempt`/`_CITATION_MARKERS`, whose docstrings explicitly document their accepted false-negative tradeoffs, this decision's rationale doesn't acknowledge this specific risk.
**Fix:** Add a sentence to the rationale (or a `dirty_..._real_dependency_plus_literal_not_exempted` test) documenting/accepting this tradeoff explicitly, consistent with the file's existing convention.

## Verdict

APPROVE
Ownership exemption's own worked example (#1022) and its own two test cases contradict each other under the stated clause-scoped mechanism.
_Note: 1 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 0._
MILL_REVIEW_END
