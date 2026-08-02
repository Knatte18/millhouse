MILL_REVIEW_BEGIN
# Review: Self-discovered mill-go/mill-plan skill-doc and behavior gaps

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; exact point version not directly knowable)
reviewed_file: _mill/discussion.md
date: 2026-08-02
```

## Findings

### [GAP] Scope section contradicts 757's own three-way routing
**Section:** `## Scope` (In:) vs. `### 757-phase-gate-widening`
**Issue:** Scope says the widened phase-gate table rows "route to Resume," but the Decision itself routes only `reviewing-*-rN`/`fixing-*-rN` to Resume, `approved-*` to `## Execute — sequential loop`, and `holistic-reviewing` to `## Holistic code review` — verified against `mill-go/SKILL.md` lines 607ff (`## Resume`) and 658ff (`## Holistic code review`).
**Fix:** Correct the Scope bullet to name all three destinations (or reference the Decision), since a plan writer reading only Scope would misroute `approved-*`/`holistic-reviewing` straight to Resume — exactly the bug the Decision's rationale warns against.

### [GAP] 757's "next pending batch" routing has no defined behavior when all batches are already approved
**Section:** `### 757-phase-gate-widening`, `approved-{batch_name}` bullet
**Issue:** The bullet states "every other batch is either already `approved` or still `state: pending`," but omits the reachable case where the just-approved batch was the LAST one in `order` — verified `mill-go/SKILL.md`'s `## Execute` loop (line 203ff) flows directly into `## Holistic code review` (line 658) after the last batch; a crash between these two points leaves `phase: approved-{last_batch}` with zero pending batches, so "continue to the next batch in `order` whose `state` is `pending`" has no target.
**Fix:** Add a case: if no batch has `state: pending`, route to `## Holistic code review` instead (mirroring the normal in-flow transition), not just to the Execute loop.

### [NOTE] Decision 757 cites "### Resume" but the actual heading is "## Resume"
**Section:** `### 757-phase-gate-widening`
**Issue:** Three references ("`### Resume` step 1 locates...", "do not route through `### Resume`", "a Resume step...") use triple-hash, but `mill-go/SKILL.md` line 607 is `## Resume` (H2, not H3) — a plan writer copying the citation verbatim would search for the wrong heading level.
**Fix:** Correct to `## Resume` in the Decision text.

### [NOTE] Asymmetric annotation target for card-attributable vs. whole-batch reasons
**Section:** `### 758-mandatory-reason-annotation`, annotation target/format bullet
**Issue:** Card-attributable reasons get appended into the card's `Requirements:` field (documented elsewhere in `mill-plan/SKILL.md` as forward-looking — "what the card must achieve"), while whole-batch reasons get a separate `## Prior failure` section — mixing a historical failure log into `Requirements:` is inconsistent with that field's stated purpose and the cleaner precedent used for the whole-batch case.
**Fix:** Consider routing all self-resolve annotations (card-attributable or not) through a `## Prior failure`-style section, or explicitly justify why card-level annotations should live in `Requirements:` instead.

## Verdict

GAPS_FOUND
Scope/Decision routing mismatch and an unaddressed last-batch edge case in #757 need resolution before planning.
MILL_REVIEW_END
