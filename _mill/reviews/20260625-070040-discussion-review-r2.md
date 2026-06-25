MILL_REVIEW_BEGIN
# Review: Fix spawn lifecycle integrity, agent-mode async assumption, merge-in conflicts, and pre-existing failure validation

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-25
```

## Findings

### [NOTE] <PARENT_BRANCH> token unresolved-parent case
**Section:** Decisions § pre-existing-validation (#542)
**Issue:** `parent_branch` can resolve to `None` (`millpy-implement.py:224-226` falls back to None on failure), but the decision treats the value as always present ("already resolved at ~line 224") and does not say how the brief's validation step behaves when the token renders empty/None.
**Fix:** State the fallback — if the parent branch is unresolvable, the brief's parent-reproduction check is skipped and the failure is treated in-scope (not auto-labeled pre-existing), so an empty token never green-lights a regression.

## Verdict

APPROVE
All decisions are source-grounded and plannable; the lone parent-None edge is a NOTE, not a blocker.
MILL_REVIEW_END
