MILL_REVIEW_BEGIN
# Review: mill-go-base: take the subagent report from the SubagentHandback message

```yaml
duration_s: 27.7
verdict: APPROVE
reviewer_model: sonnet
reviewed_file: /home/knatte/Code/millhouse/wts/subagent-handback-report/_mill/discussion.md
date: 2026-09-26
```

## Findings

### [NIT:decision] Stale "implementer's task-notification" comments in review scripts have no disposition
**Demoted-from:** BLOCKING
**Section:** Scope / capture-and-unescape **Issue:** `millpy-review-discussion.py`, `millpy-review-plan.py`, `millpy-review-code.py` and `test-review-finalize.py` carry comments contrasting reviewer output with "the implementer's `<task-notification>` payload" being HTML-escaped; the discussion rewords only comments in `_implementer_common.py` and `millpy-merge-in-subagent.py`, so these become stale or contradictory. **Fix:** State keep or reword for these comments, and for the matching comment in `test-implementer-common.py`.

### [NIT:design] Unescape assumption is unverified
**Section:** capture-and-unescape **Issue:** "hand-back text is not HTML-escaped" is stated as an assumption, yet the finalize path unescapes unconditionally, so a hand-back report containing literal entity text is silently altered. **Fix:** Say who confirms the assumption, or record that the residual risk is accepted.

### [NIT:design] Notification-first ordering has no bound
**Section:** event-order-and-what-to-wait-for, case (2) **Issue:** "take no action and wait for the hand-back message" has no fallback if the hand-back never arrives, e.g. on an older harness whose completed notification carries no text and no message follows. **Fix:** Name the outcome, such as reusing the existing empty-payload handling in step 3.

## Verdict

APPROVE
One BLOCKING: comment rewording scope omits the review scripts and tests that reference the notification payload.
_Note: 1 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 0._
MILL_REVIEW_END
