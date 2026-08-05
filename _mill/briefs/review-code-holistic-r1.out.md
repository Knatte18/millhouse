MILL_REVIEW_BEGIN
# Review: markdown skill: use semantic line breaks instead of one unbroken line per paragraph — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-08-05
```

## Findings

### [BLOCKING] "Ambiguous punctuation" decision not applied to 3 of 4 cards
**Location:** `plugins/python/skills/python-comments/SKILL.md:132-141`, `plugins/golang/skills/golang-comments/SKILL.md:179-186`, `plugins/csharp/skills/csharp-comments/SKILL.md:29-36`
**Issue:** `00-overview.md`'s "ambiguous sentence-ending punctuation does not force a break" decision states "Applies to: all cards in this batch," but the delivered "Line-wrap style" sections in the python/golang/csharp comment skills contain no guidance about periods inside URLs or abbreviations like "e.g."/"etc." — only `markdown/SKILL.md` (lines 34-35) carries this rule.
**Fix:** Either add the ambiguous-punctuation carve-out to the three comment skills' new sections, or narrow the decision's "Applies to" scope in `00-overview.md` to Card 1 only so the documented decision matches what was actually delivered.

## Verdict

REQUEST_CHANGES
Shared decision claims batch-wide scope but is applied in only one of four cards.
MILL_REVIEW_END
