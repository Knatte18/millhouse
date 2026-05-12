# Review: mill-pause: graceful orchestrator pause between operations

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: task/discussion.md
date: 2026-05-12
```

## Findings

### [GAP] Mill-plan resume instruction left as unresolved "equivalent"
**Section:** Decision: resume-trigger; Decision: confirmation-message
**Issue:** `confirmation-message` names the resume instruction for mill-go explicitly ("Run /mill-go to resume") but defers mill-plan's resume instruction with "or the equivalent for mill-plan" — leaving it undefined. Verified from mill-go's entry phase gate: `planning` / `plan-review-*` / `plan-fix-*` routes to "tell user to finish mill-plan and halt", so the mill-plan equivalent is unambiguously "Run /mill-plan to resume", not /mill-go. The SKILL.md must emit the correct, context-sensitive instruction; an unresolved "equivalent" will cause the plan writer to guess.
**Fix:** Resolve the equivalent explicitly: "Run /mill-plan to resume" when pausing within a mill-plan session. State this in the confirmation-message decision so the SKILL.md author has a definitive answer.

### [NOTE] No-active-poll invocation case not addressed
**Section:** Problem / Scope
**Issue:** The discussion describes pause behavior when a `millpy-bg` poll is in progress, but does not cover invocation during mill-go's Entry/Prepare phase (before the first batch poll starts) or at a dispatch decision point between polls.
**Fix:** Add a one-sentence statement: if no poll is currently awaited, the skill's effect is simply "do not dispatch the next CLI call" — consistent with the in-scope rule but worth spelling out so the SKILL.md author handles the edge case explicitly.

## Verdict

GAPS_FOUND
One unresolved "equivalent" in the confirmation-message decision blocks the plan writer from writing a correct context-sensitive SKILL.md.