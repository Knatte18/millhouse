MILL_REVIEW_BEGIN
# Review: mill-plan: review-round cap and skip-check threading bugs

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

### [BLOCKING:design] operator_max_review_rounds vs local_max_review_rounds precedence undefined
**Section:** Decisions — #970 "operator-raised round-cap override" **Issue:** The new live-override variable `operator_max_review_rounds` substitutes for `max_review_rounds` at the same sites the pre-existing blocked-resume override (`local_max_review_rounds`, "Entry: resuming after a max-rounds block") already substitutes at when a loop was entered via the blocked re-entry row — the discussion never says which value wins, whether they compose, or whether the live instruction is even permitted while a blocked-resume loop (with its own fresh full budget) is active. **Fix:** Add a decision stating precedence (e.g. operator override always wins and replaces `local_max_review_rounds` for the remainder of the run) or explicitly declare the live-raise instruction inapplicable during a blocked-resume loop.

## Verdict

REQUEST_CHANGES
One BLOCKING: precedence between the two round-cap override mechanisms (live operator vs blocked-resume) is undecided.
MILL_REVIEW_END
