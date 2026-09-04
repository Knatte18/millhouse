MILL_REVIEW_BEGIN
# Review: mill-plan: review-round cap and skip-check threading bugs — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: Claude (Sonnet-class model; exact version uncertain from self-assessment alone)
reviewed_file: plan/
date: 2026-09-04
```

## Findings

### [NIT:consistency] Interim-commit granularity unspecified for the new 4b/4c/4d full-validate gate
**Location:** Cards 3, 4, 8 **Issue:** The mechanical-fix-and-retry cycle these cards insert is described as using "the same fix semantics" as Step 1.5, which explicitly commits the mechanical fix before re-running `_plan_validate.run` — but Cards 3/4/8 never state whether that interim commit is separate (mirroring Step 1.5) or folds into the branch's own single terminal commit (`<plan_dir> <reviews_dir> <status_path> _mill/briefs/`). **Fix:** Add one sentence to Card 3 (the fullest-spec card) making the interim-commit behavior explicit; Cards 4/8 already cross-reference Card 3 so no further change needed there.

## Verdict

APPROVE
Source-grounded against actual SKILL.md/_status.py/_plan_validate.py text; all card anchors, signatures, and decisions verified accurate.
MILL_REVIEW_END
