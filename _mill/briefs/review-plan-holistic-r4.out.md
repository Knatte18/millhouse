MILL_REVIEW_BEGIN
# Review: mill-go-base: remove subprocess/psmux dispatch branches — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5
reviewed_file: plan/
date: 2026-08-12
```

## Findings

### [BLOCKING:design] Card 20's single stated exception omits a confirmed same-file collision
**Location:** batch 5, card 20 (renumbering), cross-checked against SKILL.md line 332 and discussion.md's own `renumber-agent-mode-steps-with-namespace-scoped-sweep` Decision.
**Issue:** SKILL.md line 332 ("Builder reads only the JSON envelope verdict, never the findings" (see step 3 of "Code Review loop")) is a namespace-3 reference physically located *inside* `## Agent-mode dispatch` (the section runs 217-920 by markdown header nesting, and 332 sits well within even the narrowest reading, before `### 0. Wiki health-check`). Card 20 is the only card that edits text inside this section, and its stated exception is "a citation into another skill's numbering" — that does not cover a same-file cross-namespace citation, so a literal application of card 20's grep-and-remap method turns "step 3" into "step 2" here, corrupting a reference that must stay "step 3." Card 21 independently lists this exact reference as a "known collision site (namespace 3)" to protect, but card 21 is explicitly scoped to text *outside* `## Agent-mode dispatch`, so it never reaches line 332 either — the reference falls through a gap between the two cards. discussion.md's own Decision flags line 332 as a hazard by name, so this is not a new observation the plan missed inventing, it is one the plan's own source material names and then fails to route to either card.
**Fix:** Add the same-file cross-namespace exception to card 20's requirements explicitly (name line 332's citation, or state the general rule: any reference into another namespace's own step numbers is also exempt, not just cross-skill citations), or move ownership of that one sentence to card 21 with its scope widened to include it.

### [NIT:consistency] History note's line count is stale by one
**Location:** batch 4, card 17 (`## History` section) and discussion.md's `git-history-is-the-backup` Decision.
**Issue:** The exact wording card 17 requires states "Pre-strip version (1483 lines...)". The current `SKILL.md` (identical to commit `356da5e5` per the plan's own verified-empty-diff claim) is 1484 lines, not 1483 — the plan faithfully copies a stale count from discussion.md's "Technical context" section (also states 1483) without re-verifying it against the file being described.
**Fix:** Recount lines against the actual pre-strip `SKILL.md` (or `git show 356da5e5:... | wc -l`) before card 17 writes the History note, and use the correct figure.

## Verdict

REQUEST_CHANGES
Card 20's renumbering exception clause misses a discussion-flagged, source-confirmed cross-namespace reference at line 332.
MILL_REVIEW_END
