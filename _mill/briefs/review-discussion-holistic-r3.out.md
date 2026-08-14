MILL_REVIEW_BEGIN
# Review: mill-plan SKILL.md: step 6 max-rounds escape bugs, self-run validator citation errors, and Step 1.5 fix-table wrong remedies

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-08-14
```

## Findings

### [BLOCKING:design] "one extra round, no persisted flag" rests on a false premise for 2 of 4 resume sites
**Section:** Decisions → revise-blocked-resume (#852), "No new state needs to persist across rounds" bullet
**Issue:** The no-persisted-flag rationale explicitly assumes `blocked_resume_round > max_review_rounds` ("already terminal... regardless of outcome"), which holds only for the step 5/step 6 block sites (they can only fire once `round >= max_review_rounds`). Step 1.5's validator two-pass cap and step 4.5's non-reviewable-round two-pass cap are both explicitly round-count-independent ("no round consumed" — SKILL.md lines 292, 449, 476) and can block at any round, including round 1, well below `max_review_rounds`. A `--revise` resume from either of those two sites produces `blocked_resume_round <= max_review_rounds`; threading `--max-rounds <blocked_resume_round>` into only that one dispatch does not cap the *loop* itself (the SKILL's own "Loop up to max_review_rounds rounds" bound is untouched), so a REQUEST_CHANGES-with-blockings outcome on the resumed round does NOT re-trigger step 5/6 as claimed — it falls through to ordinary 4d and the loop silently continues through every remaining round up to the original `max_review_rounds`, all within the single `--revise` invocation.
**Fix:** Revise the rationale/design for the step 1.5 and step 4.5 resume cases specifically — either accept and document that those two resumes continue the interrupted loop with its full remaining budget (not "exactly one extra round"), or add round-budget tracking so all four sites actually get the promised one-round grant; the current text asserts a single uniform property across all four sites that is only true for two of them.

## Verdict

REQUEST_CHANGES
False premise in #852's "no persisted flag needed" resume design breaks the stated one-round-grant guarantee for 2 of 4 sites.
MILL_REVIEW_END
