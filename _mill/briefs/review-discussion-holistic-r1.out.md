MILL_REVIEW_BEGIN
# Review: Entry-gate wait: drop nonexistent Monitor persistent:true

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-09-24
```

## Findings

### [NIT:design] Per-slug wait_started_epoch not stated for orch-review
**Section:** Decisions / Re-arm rather than persistent **Issue:** orch-review arms several concurrent waits, but only "per-slug task_id" is named as a difference, so a plan writer could share one `wait_started_epoch` across slugs. **Fix:** State that `wait_started_epoch` (and `remaining_s`) is tracked per slug.

### [NIT:consistency] harness-tool-contracts.md wording beyond lines 26/37
**Section:** Scope / In **Issue:** Line 3 of harness-tool-contracts.md ("orchestrator skills (mill-plan, mill-go)") and line 35 ("Both entry-gate wait sections below") also enumerate consumers and would go stale. **Fix:** Note these lines as in scope, or explicitly leave them.

## Verdict

APPROVE
Claims verified against source; scope, decisions and testing are clear, only minor NITs.
MILL_REVIEW_END
