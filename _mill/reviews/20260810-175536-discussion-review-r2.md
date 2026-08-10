MILL_REVIEW_BEGIN
# Review: mill-go/mill-plan SKILL.md: undocumented mutation sequences, precondition bugs, and non-portable cross-references

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5
reviewed_file: _mill/discussion.md
date: 2026-08-10
```

## Findings

### [BLOCKING:design] 3.6 item 5's target halt is unreachable given its own enclosing gate
**Section:** Decision `810-mutation-sequence`, mutation sequence for `mill-go/SKILL.md:1148`
**Issue:** `mill-go/SKILL.md:1133`'s "When ... `fallback_reviewer` is not null AND ...:" gate encloses all of items 1-5 (verified: identical indentation, lines 1135-1149). Item 5 (line 1148) fires only when `fallback_reviewer is None` — logically incompatible with its own enclosing gate. Per 3.5's own text (line 1127, "If sub-step 3.6 does NOT apply, halt with BLOCKED: holistic code review ERROR-only..."), a `None` `fallback_reviewer` means 3.6 never applies, so control never reaches item 5 — it appears to be dead code as literally structured.
**Fix:** Surface this to the discussion owner: either treat it as another deliberately-deferred pre-existing inconsistency (parallel to the step-7 residual-gap callout already in Scope/Out), or clarify whether item 5 needs repositioning outside the "not null" gate before the plan writer inserts the new mutation-sequence text there.

### [NIT:consistency] Q&A log repeats the mill-start-wide precedent claim the Decision retracted
**Section:** Q&A log, last entry ("For #806, use bare `<skill>/SKILL.md`...")
**Issue:** Decision `806-portable-cross-refs`'s rationale explicitly retracts citing "throughout mill-start/SKILL.md" as precedent (lines 249/288 there are still full-form, i.e. the exact bug being fixed) and states "this decision does not rely on the mill-start citation at all going forward." The Q&A log's "Why" field for the same decision still asserts the pattern is "proven portable ... throughout mill-start/SKILL.md" — a superseded statement left uncorrected.
**Fix:** Align the Q&A log's "Why" wording with the corrected Decision rationale (drop the "throughout mill-start/SKILL.md" clause, rely on the line-381 precedent + harness base-directory mechanism only).

## Verdict

REQUEST_CHANGES
One BLOCKING: 3.6 item 5's halt appears structurally unreachable, affecting where #810's new text lands.
MILL_REVIEW_END
