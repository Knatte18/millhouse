MILL_REVIEW_BEGIN
# Review: mill-plan/SKILL.md doc gaps: missing mill:conversation load, Phase: Plan commit step omits push — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5 (Sonnet-class, exact minor version unverifiable from within the session)
reviewed_file: plan/
date: 2026-07-29
```

## Findings

### [BLOCKING] Card 2's new Step 0b prose mis-cites the holistic-rounds-exhausted prompt's location
**Location:** Batch 01, Card 2 (mill-go/SKILL.md Step 0b insertion)
**Issue:** The replacement text to be written verbatim into `mill-go/SKILL.md` states "the holistic-rounds-exhausted prompt (in `## Agent-mode dispatch`)" — but per the file's own heading structure (`## Agent-mode dispatch` spans lines 105–515; the holistic-rounds-exhausted prompt at lines 769–774 falls under `## Holistic code review`, which spans 567–775), that prompt is NOT inside `## Agent-mode dispatch`. This mis-citation would be committed to the codebase as new, incorrect documentation prose. `_mill/discussion.md` itself never makes this specific section claim (it only cites line numbers) — the error was introduced during plan-writing.
**Fix:** Change the parenthetical to `(in `## Holistic code review`)`, or drop the section citation entirely and rely on the line-anchor-free description already used elsewhere in this same paragraph.

### [NIT] Every quoted "find" block in Card 1 and Card 2 carries a 2-space over-indent vs. the actual source lines
**Location:** Batch 01, Card 1 (all seven find/replace edits) and Card 2 (the one find/replace edit)
**Issue:** Card 1's Requirements preamble promises "an exact old block to find," but every quoted fenced-code "find" block is indented 2 spaces more than the corresponding line in `mill-plan/SKILL.md`/`mill-go/SKILL.md` (verified via grep against source, e.g. plan quotes `     After applying mechanical fixes...` with 5 leading spaces where the source has `   After applying mechanical fixes...` with 3). This is a nesting artifact of the plan's own bulleted-list markdown, not a content error, but a literal byte-for-byte copy as an Edit `old_string` will fail to match.
**Fix:** Either strip the extra 2 leading spaces from each quoted "find"/"replace" block before publishing the plan, or add a one-line note that quoted blocks are indentation-relative to the enclosing list item, not literal.

### [NIT] Reformatted max-rounds prompt's follow-up routing uses labels, not the numeric routing discussion.md's Decision specifies
**Location:** Batch 01, Card 1, edit 7 (max-rounds-escape prompt reformat)
**Issue:** `_mill/discussion.md`'s `max-rounds-prompt-format-conformance` Decision says to "update the corresponding 'Wait for the user's choice. A → ... B → ... C → ...' follow-up sentence to reference the new numbers (`1 → ... 2 → ... 3 → ...`) instead of letters." The card's actual replacement instead routes by label ("Deep problems → ...", "Shallow → ...", "Override → ..."). This is arguably more correct, since which choice is "1)" varies per round (whichever is computed as recommended), so a fixed "1 → / 2 → / 3 →" mapping would be misleading — but the card never states this rationale or flags the deviation from the Decision's literal wording.
**Fix:** Add one sentence to the card noting the label-based routing is an intentional deviation from the Decision's literal "1 → / 2 → / 3 →" wording because option-to-number assignment is recomputed per round.

## Verdict

REQUEST_CHANGES
One BLOCKING factual mis-citation would be committed into mill-go/SKILL.md's new prose; two NITs are cosmetic/documentation risks.
MILL_REVIEW_END
