MILL_REVIEW_BEGIN
# Review: mill-go2: fork-based dispatch reliability, shared-skill preloading, and catalog accuracy

```yaml
duration_s: 206.0
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-08-21
```

## Findings

### [NIT:consistency] de-briefing literal text doesn't reconcile with existing two-bullet structure
**Section:** Decisions -> "de-briefing text (implementer and fixer)" **Issue:** the implementer override currently splits the fork prompt into a "Fork every fresh attempt" bullet (`Agent(... prompt: <de-briefing> + "\n\nRead this file...")`) and a separate "De-briefing (prompt opening)" bullet supplying only the `<de-briefing>` prefix value -- that formula has no slot for text *after* the brief-pointer, so bookending requires restructuring the Agent() call itself, not just the de-briefing bullet's content, and the Decision doesn't say so explicitly. **Fix:** none needed beyond what's already covered -- the Testing section's "read the actual on-disk SKILL.md ... when writing/reviewing the plan" instruction already forces this cross-check, so flagging for awareness only.

## Verdict

APPROVE
Claims cross-checked against mill-go2/mill-go-base/mill-start/workflow SKILL.md are all accurate; decisions are well-supported.
MILL_REVIEW_END
