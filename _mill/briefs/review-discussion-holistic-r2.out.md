MILL_REVIEW_BEGIN
# Review: Fix mill-ghissues-to-tasks to refuse fold-ins into done and deferred tasks

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-15
```

## Findings

### [NOTE] Locked-phase refusal tests assert no message text
**Section:** Technical context / Testing (lines 80, 103)
**Issue:** The discussion says the locked-phase tests at lines 265-352 should "update expected message text to the new wording," but those tests (verified) only assert that `SystemExit` is raised and `post_home == pre_home` — they never inspect message text, so no edit is required for them to stay green.
**Fix:** Drop the "update expected message text" instruction for these three cases (or have the plan add a positive message-text assertion deliberately rather than implying one exists).

### [NOTE] Step-5 inline guard currently subscripts status, not deferred
**Section:** Technical context (line 78)
**Issue:** The discussion correctly mandates `.get(...)` for the new predicate, but the existing Step-5 snippet uses `task['status']` (subscript) at SKILL.md line 107; the plan writer should switch both reads to `.get()`, not only the newly added `deferred` read.
**Fix:** State explicitly that the existing `task['status']` subscript also becomes `task.get('status')` in the rewritten Step-5 block.

## Verdict

APPROVE
Scope, decisions, and source claims all verified; only two non-blocking testing/wording notes.
MILL_REVIEW_END
