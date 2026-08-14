MILL_REVIEW_BEGIN
# Review: mill-go/millpy-implement: Windows dotnet build-server file-lock races in verify/baseline stages

```yaml
duration_s: 208.0
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5 (best-effort self-assessment)
reviewed_file: _mill/discussion.md
date: 2026-08-14
```

## Findings

### [NIT:consistency] Retry-shutdown wording vs. Testing D1 call count
**Section:** Decision `verify-gate-retry-one-shot-no-sleep` **Issue:** the decision's phrasing ("running `dotnet build-server shutdown`... as the only wait between attempts") reads as if the retry fires its own new shutdown call, which could mislead a plan writer who skips Testing D1's explicit 3-call sequence (initial run, existing unconditional shutdown, retry) showing the retry reuses the pre-existing shutdown rather than adding a second one. **Fix:** tighten the decision's wording to state explicitly that no new shutdown call is added — the retry relies on the already-unconditional post-run shutdown that fires before the signature check.

## Verdict

APPROVE
Decisions, scope, and technical-context line references all verified accurate against source; one wording nit only.
MILL_REVIEW_END
