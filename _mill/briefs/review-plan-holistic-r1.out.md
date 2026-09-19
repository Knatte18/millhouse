MILL_REVIEW_BEGIN
# Review: mill-plan: planning-process documentation/procedure gaps — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: plan/
date: 2026-09-19
```

## Findings

### [BLOCKING:design] Card 6 omits Step 3.5 retry from revise_from_blocked --max-rounds fix
**Location:** batch 01, card 6. **Issue:** Card 6 rewrites the "`--max-rounds` threading for blocked-resume (`revise_from_blocked` only)" paragraph (SKILL.md line ~324) but explicitly scopes the fix to "every prepare/finalize CLI invocation dispatched in step 2's dispatch below" only — it never threads `--max-rounds <round>` into Step 3.5's ERROR-only-aggregate retry dispatch, which re-fires the identical round `N` (round is not consumed on ERROR/absent-JSON). The sibling Entry-blocked-reentry flow (`local_max_review_rounds`) DOES thread its equivalent flag into Step 3.5 today (SKILL.md lines 479/530, subprocess branch), and card 5 in this same plan adds the missing Agent-mode counterparts for that flow at Step 3.5 too — so the two "correctly-scoped" flows the overview's Decision claims end up asymmetric. Card 6's own "Known limitation" paragraph confirms `--revise` can resume a block whose `blocked_reason` started `"max-rounds exhausted"` — i.e. `blocked_resume_round` typically exceeds `max_review_rounds`, meaning an ERROR-triggered Step 3.5 retry in that state would omit `--max-rounds` and hit the CLI's own `round_n > max_rounds` hard-error guard, producing a spurious ERROR-retry loop this exact card is meant to prevent. **Fix:** Extend card 6's Requirements to also thread `--max-rounds <round>` into Step 3.5's ERROR-retry dispatch (both Agent-mode `<args>` and subprocess `millpy-review-plan.py` invocation), mirroring the flow-2 blockquotes at lines 479/530 and card 5's new Agent-mode additions.

## Verdict

REQUEST_CHANGES
Card 6 leaves the revise_from_blocked --max-rounds fix incomplete at Step 3.5's ERROR-retry dispatch.
MILL_REVIEW_END
