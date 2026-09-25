MILL_REVIEW_BEGIN
# Review: Ask the parent session when stuck (parent_thread)

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-09-25
```

## Findings

### [BLOCKING:design] `parent-guided-retry` phase omitted from crash-resume routing
**Section:** `converted-sites` (`go-batch` row), `escalate-before-recording-block`
**Issue:** The `go-batch` retry action appends `phase: parent-guided-retry` then re-fires the implementer; per `mill-go-base/SKILL.md` line 151, dispatching an implementer never itself calls `append_phase`, so `phase:` stays `parent-guided-retry` for the whole re-fired run — structurally identical to the existing `self-resolved-verify-logic` phase. `self-resolved-verify-logic` is in the hardcoded `matches_wait_trigger` set (`mill-go-base/SKILL.md` lines 139-143) precisely so a crash mid-run still resumes correctly; `parent-guided-retry` is never added to that set or given its own Mid-execution phase-gate-widening branch. A crash during a parent-guided retry lands on the Entry phase table's `any other -> surface + halt` row (line 120), not a resume — contradicting this same decision's own rationale ("a re-run resumes normally").
**Fix:** Add `parent-guided-retry` to the `matches_wait_trigger` exact-set and give it a routing branch (mirroring `self-resolved-verify-logic`'s batch-state disambiguation), or state explicitly why it doesn't need one.

### [NIT:scope] `harness-tool-contracts.md` wait-site count goes stale
**Section:** Scope (harness-tool-contracts.md bullet), Decision `wait-mechanism`
**Issue:** `ask-parent`'s wait explicitly reuses "the same re-arming pattern as orch-wait Step 2," becoming a fifth consumer of the Monitor re-arm pattern documented in `harness-tool-contracts.md`. That doc's Monitor section names and counts "four wait sections" twice (lines 27, 38) and lists the four by name. The scope item for this file only asks for a new SendMessage note, not for updating that enumeration.
**Fix:** Add updating the "four wait sections" references (and the four-item list) to five, naming the `ask-parent` skill, to the harness-tool-contracts.md scope item.

## Verdict

REQUEST_CHANGES
One BLOCKING: parent-guided-retry phase has no crash-resume routing decision.
MILL_REVIEW_END
