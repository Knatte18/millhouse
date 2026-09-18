MILL_REVIEW_BEGIN
# Review: mill-go-base: orchestration robustness gaps

```yaml
duration_s: 252.0
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5 (Sonnet 5)
reviewed_file: _mill/discussion.md
date: 2026-09-18
```

## Findings

### [BLOCKING:design] Entry-gate blocked-row halt message left unfixed by #1013
**Section:** `### 1013-blocked-resume` Decision, item (a). **Issue:** The Decision proves, via its own analysis of `_status.py`, that every batch-triggered block (`SKILL.md`'s cleanliness/scope/parent-branch blocking call sites) sets `blocked_reason` only on the batch entry via `set_batch_field`, never via `_status.set_blocked` — so the task-level top-yaml `blocked_reason:` field stays absent. Yet the Entry phase gate's own `blocked` row (SKILL.md line 111, 119: `blocked_reason = status["yaml"].get("blocked_reason")` → "surface blocked_reason from status.md and halt") only ever reads that same top-level field, so for the common case (a batch-level block, not a `set_blocked`-based task halt) the operator's halt message will surface an empty/None reason — exactly the recoverability gap #1013 exists to close. The discussion documents this dichotomy in detail solely to justify how the new "Resume after external fix" *sub*-section should read state, but never decides whether the existing top-of-gate halt display should also fall back to the per-batch field. **Fix:** Add an explicit Decision/instruction updating the `blocked` row's halt action to read the per-batch `blocked_reason` (via `_status.read_batches`) when the top-level field is absent, or explicitly state as a rejected-alternative why the operator is expected to inspect `## Batches` directly instead.

## Verdict

REQUEST_CHANGES
Entry-gate blocked-row halt message gap left undecided despite the discussion's own analysis surfacing it.
MILL_REVIEW_END
