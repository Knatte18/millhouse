MILL_REVIEW_BEGIN
# Review: mill-merge-in SKILL.md: _plan_dag helper calls missing signature lines

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5
reviewed_file: _mill/discussion.md
date: 2026-08-02
```

## Findings

### [NOTE] Problem section overstates existing in-file convention
**Section:** Problem
**Issue:** "every other helper call in this file family ... carries [signature:]" implies mill-merge-in/SKILL.md already follows the convention elsewhere; verified via grep that the file has zero `signature:` lines anywhere today, so the two new lines import a sibling-file convention rather than extend a local one (the discussion's own Technical Context section already grep-confirms this, so the two sections are in mild tension).
**Fix:** Soften the Problem sentence to say the convention is established in the file family generally (mill-go, mill-finalize), not that mill-merge-in already applies it elsewhere internally.

### [NOTE] Cited convention precedent is a looser structural match than an alternative
**Section:** Decisions > Signature-line placement and format
**Issue:** `mill-go/SKILL.md:183-186` (cited as "closest precedent") is a numbered-list-item continuation; `mill-go/SKILL.md:434-437` is a standalone, non-indented pair of `signature:` lines following prose under a step header — structurally closer to mill-merge-in step 4's plain-paragraph layout (verified: both locations read).
**Fix:** Cite 434-437 alongside or instead of 183-186 as the structural precedent, since the actual placement decision (unindented, standalone lines) matches it more closely.

## Verdict

APPROVE
Both decisions verified against current source; scope, rationale, and testing are adequately covered for this narrow doc fix.
MILL_REVIEW_END
