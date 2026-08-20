MILL_REVIEW_BEGIN
# Review: git-pr: gh pr create fails on GraphQL 5xx with no REST fallback documented

```yaml
duration_s: 92.0
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-08-20
```

## Findings

### [NIT:decision] Duplicate-PR URL lookup failure has no stated disposition
**Section:** Decisions -> duplicate-pr-detection
**Issue:** If the "already exists" pattern matches but both the `gh pr view` retry and its REST `GET` fallback also fail to yield a URL, no reporting behavior is specified.
**Fix:** State the fallback message (e.g. "PR already exists but URL could not be retrieved") for this double-failure case, or note it's acceptable to leave to plan-writer discretion.

## Verdict

APPROVE
Decisions are all rationale-backed with rejected alternatives; source claims verified against SKILL.md and mill-merge/SKILL.md.
MILL_REVIEW_END
