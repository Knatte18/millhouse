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

### [BLOCKING:consistency] Stale "exactly one round" claim survives the r4 Category A/B correction
**Section:** Decisions > revise-blocked-resume, Rationale bullet; Q&A log, second entry.
**Issue:** The r4 correction (confirmed accurate) moved step 5 into Category B, which resumes with the loop's full remaining budget, not one round — yet the Decision's own Rationale still says "every resume grants exactly one additional round," and the Q&A log still says "step 5/6 grant exactly one self-terminating round, step 1.5/4.5 resume the loop's normal remaining budget" (also mis-citing this as an r3 correction; it was r4). Both statements restate the pre-r4, now-disproven uniform categorization.
**Fix:** Update the Rationale bullet to state the bound is "at most one extra round for Category A (step 6), full remaining budget for Category B (step 1.5/4.5/step 5)" and correct the Q&A log's parenthetical to match the Decision's current Category A={step 6} / Category B={step 1.5, step 4.5, step 5} split, citing r4.

### [NIT:design] Category A's "re-triggers step 6" claim ignores step 5 preemption
**Section:** Decisions > revise-blocked-resume, Category A bullet.
**Issue:** "A REQUEST_CHANGES verdict with blocking findings re-triggers step 6 on that same round" — but step 5 (non-progress) runs before step 6 and fires instead if the resumed round's Pushed Back title set matches the prior blocking round's, which is plausible right after a resume. The outcome is still a one-round halt either way, so this doesn't change correctness, only the narrative's precision.
**Fix:** Note that the resumed round may instead re-trigger step 5 (non-progress) rather than step 6, if the title sets match; either is still a single self-terminating halt.

## Verdict

REQUEST_CHANGES
Fix the stale post-r4 "exactly one round" wording still present in the Rationale bullet and Q&A log.
MILL_REVIEW_END
