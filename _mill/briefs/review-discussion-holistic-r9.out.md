MILL_REVIEW_BEGIN
# Review: Self-discovered mill-go/mill-plan skill-doc and behavior gaps

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; exact point version unconfirmed)
reviewed_file: _mill/discussion.md
date: 2026-08-02
```

## Findings

### [NOTE] #755 pointer-target line ranges are stale/inaccurate
**Section:** Decision `755-harness-contracts-doc` / Technical context
**Issue:** Cited line ranges for the two "Entry-gate wait" sections don't match source: mill-go/SKILL.md's `### Entry-gate wait for upstream mill-plan` actually spans lines 89-181 (cited as "~130-181"), and mill-plan/SKILL.md's `### Entry-gate wait for upstream mill-start` actually spans lines 42-124 (cited as "~42-91").
**Fix:** Re-verify line numbers at plan-writing time, or drop them in favor of the (correct) heading text, which is unique and searchable.

### [NOTE] Decision 757's "six of the seven" count is unreconcilable from the bullet list alone
**Section:** Decision `757-phase-gate-widening`, Rejected paragraph
**Issue:** The routing bullet list enumerates exactly 6 distinct widened phase patterns (reviewing-*-rN, fixing-*-rN, approved-*, holistic-reviewing, self-resolved-verify-logic, holistic-approved); the Rejected paragraph's "phase alone discriminates six of the seven widened values, not all seven" only reconciles if the pre-existing `implementing`/`reviewing`/`fixing` exact-match bucket is silently counted as a 7th "widened value," which it isn't described as anywhere in the bullet list itself.
**Fix:** Reword to explicitly state the 7th bucket (the pre-existing exact-match row) so the count is self-evident without cross-referencing the `matches_wait_trigger` call's exact-set separately.

## Verdict

APPROVE
Both findings are non-blocking citation/rationale-clarity issues; all decisions, rejected alternatives, and source claims verified accurate against source files.
MILL_REVIEW_END
