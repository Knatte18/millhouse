MILL_REVIEW_BEGIN
# Review: git-pr: gh pr create fails on GraphQL 5xx with no REST fallback documented

```yaml
duration_s: 145.0
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5
reviewed_file: _mill/discussion.md
date: 2026-08-20
```

## Findings

### [BLOCKING:design] Step 7 "proceed on any failure" premise unverified against source
**Section:** Scope → Out (step 7 exclusion) **Issue:** The claim "[step 7] already treats any failure — including a GraphQL 5xx — as 'no PR found, proceed'" is not what `git-pr/SKILL.md` step 7 literally says: it only defines two branches ("PR already exists → stop" and "`gh` not installed → proceed to step 8"), leaving a third case (gh installed, command fails for another reason, e.g. GraphQL 5xx) with no explicit instruction. **Fix:** Either verify/state this is an inferred sequential-fallthrough convention (not an explicit rule) or make the Out-of-scope rationale conditional on that inference being correct, since the "caught safely downstream" argument depends on it.

### [NIT:consistency] report-wording assumes a diagnosis rest-fallback-trigger declined to make
**Demoted-from:** BLOCKING
**Section:** Decisions → report-wording vs. rest-fallback-trigger **Issue:** rest-fallback-trigger deliberately fires step 10.5 on *any* non-zero exit from step 10 without pattern-matching the error text (explicitly rejecting GraphQL/5xx text matching as "fragile"), yet report-wording's example text asserts a specific cause — "PR created via REST API (GraphQL was unavailable)" — that was never actually diagnosed by the trigger logic. **Fix:** Either report-wording should use cause-agnostic phrasing (e.g. "PR created via REST API fallback") or rest-fallback-trigger must add a lightweight check to justify attributing the failure to GraphQL specifically.

## Verdict

REQUEST_CHANGES
Two blocking issues: an unverified step-7 fallthrough premise and a report-wording/trigger-logic contradiction.
_Note: 1 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 1._
MILL_REVIEW_END
