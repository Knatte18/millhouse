MILL_REVIEW_BEGIN
# Review: mill-go-base: remove subprocess/psmux dispatch branches — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; I cannot independently confirm the exact point version)
reviewed_file: plan/
date: 2026-08-12
```

## Findings

### [BLOCKING:scope] `skills_dir.rglob("SKILL.md")` cited but its file not in Context
**Location:** batch 4 card 14, batch 5 card 24
**Issue:** Both cards' `Requirements:` assert the skills-index generator "collects its inputs with `skills_dir.rglob("SKILL.md")`" — a literal expression verified to exist at `plugins/mill/scripts/millpy-skills-index.py:100` — but that file is not in either card's `Context:` (card 14: `_mill/discussion.md`, `SKILLS.md`; card 24: `mill-skills-index/SKILL.md`, `mill-go/SKILL.md`, `mill-go2/SKILL.md`, the three companion files). `mill-skills-index/SKILL.md` itself only describes the scan generically ("`plugins/*/skills/**/SKILL.md`"), it does not name `skills_dir.rglob`.
**Fix:** Add `plugins/mill/scripts/millpy-skills-index.py` to `Context:` on both cards, or drop the specific-expression claim and cite only what `mill-skills-index/SKILL.md` itself states.

### [NIT:consistency] Card 20 misstates the source file's step-6.5 sub-labels
**Location:** batch 5 card 20
**Issue:** Card 20 says the current numbering "runs 2 through 7 with sub-labels `4(a)`, `4(b)`, `4(c)`, `6.5`, `6.5.1`, and `6.5.2`." `mill-go-base/SKILL.md` itself never writes `6.5.1`/`6.5.2` — step 6.5's two/three sub-items are plain `1.`/`2.`/`3.`; the dotted `6.5.1`/`6.5.2` form is only how `mill-go2/SKILL.md` cites them externally. The card's own next sentence ("its two numbered sub-items keep their `1.`/`2.`/`3.` local numbering") is correct and self-corrects this, so no wrong edit results, but the initial framing misdescribes the file this card edits.
**Fix:** Drop `6.5.1`/`6.5.2` from the "current sub-labels" list; state that step 6.5's sub-items are bare `1.`/`2.`/`3.` and that the dotted form is mill-go2's own citation convention (handled separately by card 23).

### [NIT:consistency] Overview's "twelve-tree-guard-checkpoints" rationale arithmetic doesn't add up
**Location:** `00-overview.md`, Shared Decision `twelve-tree-guard-checkpoints-not-ten`
**Issue:** The rationale quotes SKILL.md's own inline sentence "(5 more in this section, 7 in Holistic)" and says this "totals 12 with the one that sentence is attached to" — but 5+7+1=13, not 12. Verified independently: the file actually has 5 checkpoint call sites total in `### 3. Code Review loop` (including the one the sentence is attached to, so 4 "more") and 7 in `## Holistic code review`, i.e. 4+7+1=12. The file's own "5 more" is a pre-existing off-by-one, and the plan's rationale compounds it into a different wrong sum that happens to land on the right final answer (12, which Card 13's own file-order enumeration and a `_treeguard.check_and_restore(` grep both independently confirm).
**Fix:** Correct the rationale's arithmetic (4 more in this section + 7 in Holistic + itself = 12) or drop the quoted parenthetical and rely solely on the grep-count justification already given.

## Verdict

REQUEST_CHANGES
Two nits and one context-completeness gap (an unlisted source file backing a specific cited expression in two cards).
MILL_REVIEW_END
