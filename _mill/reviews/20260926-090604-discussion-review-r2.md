MILL_REVIEW_BEGIN
# Review: mill-go-base: take the subagent report from the SubagentHandback message

```yaml
duration_s: 31.6
verdict: APPROVE
reviewer_model: sonnet
reviewed_file: /home/knatte/Code/millhouse/wts/subagent-handback-report/_mill/discussion.md
date: 2026-09-26
```

## Findings

### [NIT:consistency] Case (2) and the Bound contradict each other
**Demoted-from:** BLOCKING
**Section:** Decisions / event-order-and-what-to-wait-for **Issue:** Case (2) says a pointer-only `completed` notification arriving first means "take no action, wait for the hand-back message", while the Bound says that if no hand-back message has been seen when that same notification is processed, the orchestrator falls to the empty-report handling instead of waiting. **Fix:** State one rule for that moment, either wait with a defined trigger and limit (for example the next turn, or a probe) or fall through immediately, and drop the other.

### [NIT:decision] Unresolved test addition
**Section:** Scope (last bullet) / Testing **Issue:** "Only if an existing SKILL-text test pattern fits" leaves the plan writer to decide whether a test is added. **Fix:** Name whether such a test exists, or commit to grep verification only.

### [NIT:consistency] Bound text says "hand-back before or together with the notification"
**Section:** event-order-and-what-to-wait-for **Issue:** This claim sits beside case (2), which treats notification-first as a normal case, and the Problem section says the hand-back message "can arrive before the notification". **Fix:** Align the observed-order statement across the three places.

## Verdict

APPROVE
Case (2) and the Bound prescribe opposite actions for the same event; resolve before planning.
_Note: 1 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 0._
MILL_REVIEW_END
