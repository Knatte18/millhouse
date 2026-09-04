MILL_REVIEW_BEGIN
# Review: _plan_validate.py context-completeness check: false positives across gitignored/quoted/negated/citation/cross-reference prose — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-09-04
```

## Findings

### [BLOCKING:consistency] SKILL.md fix-table promises negation-form guidance that doesn't exist
**Location:** `plugins/mill/skills/mill-plan/SKILL.md:385`
**Issue:** The `context-completeness` fix-table row tells the planner to consider "rephrasing a not-involved mention into one of the supported negation forms (see the Principles section's negation/contrast/quoting guidance below)", but the Principles bullet at lines 667–674 never documents the three negation templates (`no `x` is involved`, `without `x``, `` `x` is not needed/required/used/involved``) added by batch 1's card 5 — it only re-describes the pre-existing, unrelated prohibition-marker word-set exemption, then the contrast/quoting/gitignored/forward-Creates additions from card 20's second edit (which never asked for negation-form coverage).
**Fix:** Either spell out the three exact templates inline in the fix-table row, or append them to the Principles bullet so the "(see below)" cross-reference resolves to real content.

### [NIT:consistency] `_extract_requirements_text` is now dead code
**Location:** `plugins/mill/scripts/_plan_validate.py:1833`
**Issue:** Card 7 re-points `_check_context_completeness`'s extraction call to `_requirements_fence_aware_body` and deliberately leaves `_extract_requirements_text` in place; after the swap it has zero remaining call sites in the module (confirmed via grep — only its own `def` and two comments referencing it by name remain) and is not exercised by any test.
**Fix:** No action required this round (plan explicitly chose not to delete it for context-budget reasons) — flagging only so a future cleanup pass knows it is safe to remove once nothing else grows a dependency on it.

## Verdict

REQUEST_CHANGES
Fix the dangling negation-form cross-reference in mill-plan's SKILL.md fix table before merge.
MILL_REVIEW_END
