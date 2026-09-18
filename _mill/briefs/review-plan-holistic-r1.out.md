MILL_REVIEW_BEGIN
# Review: mill-start Explore: Agent(subagent_type: fork) dispatch fails to perform assigned investigation — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: plan/
date: 2026-09-18
```

## Findings

### [NIT:consistency] "Reuse exact phrasing" quote does not match the text actually inserted
**Location:** Batch 1, Card 1 **Issue:** Requirements instructs "reuse its exact `general-purpose` phrasing" and quotes mill-plan's "`general-purpose` when the research needs a tool beyond Explore's read-only grant", but the literal sentence given earlier in the same card to append reads "when the investigation needs a tool beyond `Explore`'s read-only grant" — "research" vs "investigation" diverge, so the "exact"/"reuse" claim is not literally true of the text that will actually be applied. **Fix:** Either change the append text to say "research" verbatim, or soften the instruction to "adapt (not reuse verbatim)" so the two statements in the card don't contradict each other.

### [NIT:scope] Batch Tests verification step references a file absent from Card 1's Context
**Location:** Batch 1, Card 1 / Batch Tests **Issue:** The manual verify step's condition (b) requires confirming the appended text "does not contradict ... mill-go-base/SKILL.md's 'Why not fork?' paragraph," but `plugins/mill/skills/mill-go-base/SKILL.md` is not listed in Card 1's `Context:` (only `mill-plan/SKILL.md` is). This is not a `Requirements:` mention so it falls outside the strict Context-completeness rule, but an implementer performing the described verification would still need to open a file the card never grants. **Fix:** Add `plugins/mill/skills/mill-go-base/SKILL.md` to Card 1's `Context:` list, or drop the mill-go-base cross-check from Batch Tests.

## Verdict

APPROVE
Single-card doc-only plan is well-grounded, decision-aligned, and DAG-valid; only two low-stakes wording/scope NITs found.
MILL_REVIEW_END
