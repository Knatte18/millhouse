MILL_REVIEW_BEGIN
# Review: Auto-approve on review-round cap

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5 (Sonnet 5)
reviewed_file: /home/knatte/Code/millhouse/wts/review-cap-auto-approve/_mill/discussion.md
date: 2026-09-18
```

## Findings

### [NIT:consistency] mill-go-base commit-message suffix left less literal than mill-plan's
**Section:** Decisions — "mill-go-base: mirror the existing implicit-approve-at-cap shape"
**Issue:** mill-plan's waiver decision gives an exact literal commit message string; the mill-go-base decision only says each commit message "notes the config-driven override (parallel to the existing suffix)" without pinning the literal text for either batch or holistic.
**Fix:** Optionally give the exact suffix text (e.g. mirroring `" (min_rounds/demoted-predicate not satisfied by round cap)"`) so the plan writer doesn't have to invent wording; not blocking since it's trivially resolvable at plan time.

## Verdict

APPROVE
All source claims verified against code; scope, decisions, and testing are complete and internally consistent.
MILL_REVIEW_END
