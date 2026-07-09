MILL_REVIEW_BEGIN
# Review: Fix nit-enforcement gate marker gaps, NIT-dispatch wording, implementer liveness probe, and Haiku false-completion — holistic

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-07-09
```

## Findings

### [NIT] Card 9 leaves step-3 summary (line 125) contradicting new 4(b)
**Location:** Batch 2 / Card 9
**Issue:** SKILL.md line 125 states "implementer notifications go through the existing clean-mid-work-stop / `incomplete` routing; reviewer and fixer notifications are checked with a one-shot liveness probe" — after this card the implementer stopped/interrupted trigger ALSO gets a probe, so line 125 becomes stale; card 9 only enumerates edits at lines 131-138/168/170 and relies on a catch-all re-read phrased around the literal string "never through the liveness probe," which line 125 does not contain and would likely be missed.
**Fix:** Add line 125 as an explicit before/after edit site in card 9, rewording it so the implementer stopped/interrupted path is described as probe-then-clean-mid-work-stop, matching the batch's precision-editing contract.

## Verdict

APPROVE
Sound, source-grounded plan; one non-blocking prose-consistency gap in card 9.
MILL_REVIEW_END