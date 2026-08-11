MILL_REVIEW_BEGIN
# Review: Surface reviewer time/tool-call cost + a review-summary command

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-08-11
```

## Findings

### [BLOCKING:design] Stale-notification-probe Decision inverts the `test -f` shortcut's trigger condition
**Section:** Decisions § "Agent-mode duration across a transient re-dispatch" — the "Probe says no-longer-running, or the probe call itself errors" bullet, parenthetical about "the reviewer-only `test -f output_path` shortcut, which still funnels into this same branch when the file is absent."
**Issue:** Verified against `mill-go-base/SKILL.md` step 4(c) (lines ~312-314): the shortcut fires when `output_path` **exists** (skip `TaskOutput`, treat as no-longer-running immediately) — it does the opposite when the file is **absent** ("the result is ambiguous ... fall back to `TaskOutput` exactly as today"), which can resolve to either the "still running" branch (no summation) or this branch, not deterministically this one. The discussion's parenthetical has the file-exists/file-absent condition backwards and overstates the absent-case as deterministic.
**Fix:** Correct the parenthetical to state the shortcut applies when `output_path` exists (deterministic funnel into this branch, `TaskOutput` skipped); when absent, the ambiguous fallback probe can land in either outcome, so no shortcut-specific claim belongs in the "absent" case.

## Verdict
REQUEST_CHANGES
One Decision misdescribes SKILL.md's `test -f` shortcut condition backwards; correct before plan-writing.
MILL_REVIEW_END
