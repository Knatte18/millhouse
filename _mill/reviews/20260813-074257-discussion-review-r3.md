MILL_REVIEW_BEGIN
# Review: mill-plan SKILL.md: entry, phase-gate, finalize, and re-entry path gaps

```yaml
duration_s: 320.0
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 5 (self-assessed)
reviewed_file: _mill/discussion.md
date: 2026-08-13
```

## Findings

### [NIT:consistency] #815 guardrail location contradicts itself
**Demoted-from:** BLOCKING
**Section:** Decision "New authoring guardrail... (#815)" vs. Q&A log last entry.
**Issue:** The Decision text says the new principle goes into mill-plan/SKILL.md's `## Principles` section (~line 551-560, next to "Card `Context:` is an allowlist"). The Q&A log's answer for the same question says it belongs "in Phase: Plan (SKILL.md-only)". `## Principles` and `### Phase: Plan` are distinct, non-nested top-level sections in the actual file (verified: `## Principles` starts after `## Timestamps`, well outside `## Phases`).
**Fix:** Pick one location and make the Q&A log and Decision agree — likely correct the Q&A entry to say "## Principles section" to match the Decision (which cites concrete line numbers and neighboring bullets).

### [NIT:consistency] Reworded halt message leaves `blocked_reason` string stale
**Section:** Decision "Max-rounds block... (#832)", step 6 message reword.
**Issue:** The decision reworks only the user-facing "halt with ..." text; `_status.set_blocked`'s `blocked_reason` argument (`"max-rounds exhausted after {N} rounds, {M} BLOCKINGs remain"`) keeps the same literally-false "{M} BLOCKINGs remain" phrasing that motivated the fix, and persists in status.md after the fixer pass already ran.
**Fix:** Either note explicitly that `blocked_reason`'s wording is intentionally left machine-stable (only the `"max-rounds exhausted"` prefix is parsed), or reword both strings for consistency — clarify which in the decision.

## Verdict
APPROVE
Resolve the #815 principle-location contradiction between the Decision and Q&A log before plan writing.
_Note: 1 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 0._
MILL_REVIEW_END
