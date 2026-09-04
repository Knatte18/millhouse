MILL_REVIEW_BEGIN
# Review: _plan_validate.py context-completeness check: false positives across gitignored/quoted/negated/citation/cross-reference prose

```yaml
duration_s: 203.0
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 5 (claude-sonnet-5)
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

### [NIT:consistency] Scope "In" bullet mislabels 3 line-level exemptions as path-branch, and miscounts
**Demoted-from:** BLOCKING
**Section:** Scope > In (bullet 2, "Six new exemptions in the **path branch**...") **Issue:** The bullet lists 7 named exemptions plus the escape marker (8 total) under the header "Six new exemptions in the **path branch**," and includes negation-phrase, contrast-citation, and quoted-material as if they were path-branch items — but the Scope's own "Out" bullet (symbol-branch exclusion) and the Technical Context section ("the three line-level ones... join step 4, before the branch split, so they cover both branches. The four path-shape ones... belong in step 5") both correctly state those three are line-level and apply to both branches, not path-branch-specific. **Fix:** Rewrite the bullet to match the verified 4-path-shape / 3-line-level / 1-escape-marker breakdown already established elsewhere in the same document.

### [NIT:consistency] Technical Context's "called directly by unit tests" claim is false
**Demoted-from:** BLOCKING
**Section:** Technical context > "`run()` wiring" (final paragraph) **Issue:** States `_check_context_completeness` "is also called directly by unit tests with the current positional signature" as grounding for requiring the new creates→card-number map to be a keyword-only argument with a safe default. Verified against source: `_check_context_completeness` has exactly one call site in the entire codebase (`run()` at `_plan_validate.py:3441`); every `test_check_context_completeness_*` test in `test-plan-validate.py` (grep across all ~50 tests) calls `_plan_validate.run(plan_dir, project_root)`, none call the check function directly. **Fix:** Correct the claim (no existing direct-call tests to preserve) and reword the Testing section's "Signature compatibility" bullet as introducing a new direct-call test, not preserving existing ones.

## Verdict

APPROVE
Two self-contradictions between Scope/Technical-Context sections; both are cheap prose fixes but must be resolved before plan writing.
_Note: 2 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 0._
MILL_REVIEW_END
