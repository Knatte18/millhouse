MILL_REVIEW_BEGIN
# Review: _plan_validate.py context-completeness check: misses bare symbol/identifier references entirely, only matches path tokens

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

### [BLOCKING:scope] mill-plan SKILL.md fixer-remediation table not in Technical Context
**Section:** Technical context / Scope. **Issue:** `plugins/mill/skills/mill-plan/SKILL.md` line 362 has the `context-completeness` fixer row, worded entirely around "the referenced file" living in the payload's `path` field (as it does today for path-shaped findings); the new symbol branch's `path` field holds the original symbol token (per "Call/generic-suffix handling," e.g. `` `SaveState()` ``), not a file, and the resolved declaring file only appears inside `message` text (per "Membership check against the card's own refs": "message adapted for the symbol case... naming the resolved declaring file"). Neither this discussion's Scope nor Technical Context sections mention this file, so an implementer following only the discussion would leave the fixer instructed to add the literal symbol token to `Context:`. **Fix:** add `plugins/mill/skills/mill-plan/SKILL.md`'s context-completeness row to Technical Context/Scope as a file needing an update, and pin down (in a Decision) the message's exact format so the fixer can reliably extract the resolved file name for the symbol case.

## Verdict

REQUEST_CHANGES
Downstream fixer-skill table for context-completeness is an unenumerated affected file; message-format contract for symbol findings is unspecified.
MILL_REVIEW_END
