MILL_REVIEW_BEGIN
# Review: mill-plan SKILL.md: entry, phase-gate, finalize, and re-entry path gaps

```yaml
duration_s: 303.0
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (Sonnet 5 family, per system context)
reviewed_file: /home/hanf/Code/millhouse/wts/mill-plan-skilldoc-and-logic-bugs/_mill/discussion.md
date: 2026-08-13
```

## Findings

### [BLOCKING:design] local_max_review_rounds substitution scope is incomplete
**Section:** Decisions -> "Max-rounds block: add a `blocked` re-entry row (#832)" -> "Round-budget interaction"
**Issue:** The decision says to substitute `local_max_review_rounds` for `max_review_rounds` "throughout the SKILL.md's own prose (4a/4b/4c/6)". Verified against `mill-plan/SKILL.md`: the *authoritative* round-cap comparison lives in the shared "Convergence gate" section (`converged is False AND round < max_review_rounds` / `round >= max_review_rounds`, SKILL.md:353-354), which 4a/4b/4c only reference ("compute `converged` per the Convergence gate above") — 4a/4b/4c's own inline "round >= max_review_rounds" text is a redundant restatement of what the gate already decided, not an independent check. The loop's own governing bound ("Loop up to `max_review_rounds` rounds", SKILL.md:286) is a third unenumerated site. If an implementer substitutes only the four literal "4a/4b/4c/6" occurrences and leaves the gate's two bullets and the loop header on the un-extended config value, the resumed loop still computes `converged`/implicit-approval against the old (already-exceeded) cap — reproducing exactly the dead-end this clause exists to prevent (discussion-review round 2's own finding).
**Fix:** Explicitly name all substitution sites: the loop header at SKILL.md:286, both `max_review_rounds` occurrences inside the Convergence gate bullets (SKILL.md:353-354), plus the 4a/4b/4c/6 restatements — not just the latter four.

### [NIT:consistency] Round-report line denominator unaddressed by the substitution
**Section:** Same decision as above.
**Issue:** Step 1's "Report: **'Plan Review — round N/max_review_rounds'**" (SKILL.md:289) is not in the enumerated `4a/4b/4c/6` substitution list either, so a resumed loop would display a stale/confusing denominator (e.g. "round 4/3") even once the functional cap is correctly extended.
**Fix:** State explicitly whether the round-report line should also print `local_max_review_rounds` during a resumed loop, or note that it's intentionally left showing the config value.

## Verdict

REQUEST_CHANGES
One BLOCKING: local_max_review_rounds substitution list omits the gate's own authoritative checks and the loop header.
MILL_REVIEW_END
