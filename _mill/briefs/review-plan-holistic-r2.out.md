MILL_REVIEW_BEGIN
# Review: git-pr: gh pr create fails on GraphQL 5xx with no REST fallback documented — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: plan/
date: 2026-08-20
```

## Findings

### [NIT:consistency] Step 11's reworded trigger imprecisely covers the double-URL-lookup-failure sub-case
**Location:** Batch rest-fallback, Card 1, Requirement 2 (step 11 trigger) vs Requirement 1 (step 10.5, "If both URL-lookup attempts also fail" branch)
**Issue:** Step 10.5's double-failure branch says "stop — do not proceed to step 11," but step 11's own reworded trigger parenthetical ("step 10.5's own duplicate-PR check did not already resolve and report a URL") is literally true in that same branch (matched, but no URL was ever reported), so read in isolation the two sections give contradictory directives for the identical state.
**Fix:** Reword the step 11 parenthetical to explicitly exclude the matched-but-unresolved case, e.g. "...and step 10.5 did not already instruct stopping (duplicate match, resolved-with-URL or not)."

## Verdict

APPROVE
Decisions, cards, DAG, and file content are faithfully aligned; one minor wording-precision NIT only.
MILL_REVIEW_END
