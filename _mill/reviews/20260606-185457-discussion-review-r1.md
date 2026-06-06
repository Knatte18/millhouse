I now have all the information needed to write the review.

MILL_REVIEW_BEGIN
# Review: revise-ghissues-to-tasks

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-06-06
```

## Findings

### [GAP] get_task returns None; fold-in path unhandled

**Section:** Technical Context — `wiki/_client.get_task`

**Issue:** `get_task` returns `dict | None` (returns `None` when the task is not found), but the fold-in path in Technical Context and the preserved invariants section describes reading `body` and `status` from the return value unconditionally; a stale slug from the proposal would cause an `AttributeError` on `None["status"]`.

**Fix:** State that the apply step must guard against a `None` return from `get_task` (e.g. abort the fold-in with an error) before reading `body` or `status`.

### [NOTE] Proposal artifact close-comment discrepancy

**Section:** Decisions — preserved invariants; current SKILL.md Step 4

**Issue:** The current SKILL.md Step 4 proposal template shows `Consolidated into wiki task: <slug>` for all New-task issues in the "GitHub close commitments" section, but does not distinguish fold-in close comments (`Folded into wiki task: <slug>`). The discussion's invariant correctly distinguishes both strings; the rewritten proposal artifact format should make that distinction visible.

**Fix:** Note that the rewritten Step 4 proposal template must list fold-in close comments separately (or label them distinctly) so the operator sees the exact string that will be posted before approving.

## Verdict

GAPS_FOUND
One feasibility gap (unguarded `None` from `get_task`) must be addressed before plan writing.
MILL_REVIEW_END