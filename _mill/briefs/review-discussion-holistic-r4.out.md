MILL_REVIEW_BEGIN
# Review: mill-plan SKILL.md: step 6 max-rounds escape bugs, self-run validator citation errors, and Step 1.5 fix-table wrong remedies

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 5 (claude-sonnet-5)
reviewed_file: _mill/discussion.md
date: 2026-08-14
```

## Findings

### [BLOCKING:design] Category A/B split rests on a false premise for step 5
**Section:** Decision `revise-blocked-resume (#852)`, Category A bullet.
**Issue:** Claims step 5 (non-progress) "only ever fires once `round >= max_review_rounds`". Verified against `mill-plan/SKILL.md`'s actual step 5 text (~lines 505-513): the check runs "after writing each fixer report from round 2 onward" and fires purely on two consecutive rounds sharing an identical non-empty Pushed-Back title set — it has no dependency on `max_review_rounds` at all. Only step 6 is genuinely round-cap-gated. So a step-5-triggered `--revise` resume's `blocked_resume_round` is generally well below `max_review_rounds` (e.g. round 3 of a 10-round budget), meaning the "self-terminating, single-round grant" reasoning does not hold for step 5 — it would actually behave like Category B (continues with the loop's remaining budget), not Category A.
**Fix:** Move step 5 out of Category A into Category B (or introduce a third case), and correct the reasoning: step 5's trigger is round-count-independent exactly like step 1.5/4.5, only step 6 is genuinely round-cap-gated.

### [BLOCKING:design] No mechanism specified to exempt blocked-resume from the existing `revise-{N+1}` namespacing
**Section:** Decision `revise-blocked-resume (#852)`, "Do not reuse or extend the `revise-{N+1}` reviews-subdir namespacing" bullet, vs. `mill-plan/SKILL.md` Phase: Plan Review Path Setup (~lines 266-270).
**Issue:** The decision requires that a blocked-resume NOT trigger the existing `revise-{N+1}` reviews-subdir override, but that override is gated solely on `revise_requested` being set — and the decision's own bullet 5 says the blocked branch falls through via "the same fallthrough target the existing planned+approved `--revise` branch already uses," i.e. the same code path, which sets `revise_requested`. No new signal (e.g. a distinct `revise_from_blocked` flag) is proposed to distinguish the two `--revise` sources at Phase: Plan Review, so implementing the decision as written would still apply the namespacing to blocked-resumes, contradicting the explicit "do not reuse" instruction. Scope's "In:" list also never mentions touching the Path Setup namespacing guard.
**Fix:** Add a decision on how Phase: Plan Review's namespacing guard distinguishes "revise from approved" vs "revise from blocked" (e.g. thread a second boolean alongside `revise_requested`), and add the corresponding Scope bullet.

## Verdict

REQUEST_CHANGES
Category A/B split misclassifies step 5, and blocked-resume's exemption from `revise-{N+1}` namespacing has no implementing mechanism.
MILL_REVIEW_END
