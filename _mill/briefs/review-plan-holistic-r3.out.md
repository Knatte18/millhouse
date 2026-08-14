MILL_REVIEW_BEGIN
# Review: Extract a language-agnostic code-comments skill; add a general docstring-length ceiling, purpose-not-mechanism rule, mandatory file/module header, and prohibit measured-result/design-rationale narrative — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 5 (claude-sonnet-5)
reviewed_file: plan/
date: 2026-08-14
```

## Findings

### [BLOCKING:consistency] Python's Inline Comments section restates the shared why-not-what rule
**Location:** batch 1 / card 3 (vs. cards 2 and 4)
**Issue:** Card 3 keeps `python-comments`' "Inline comments — narrate the reasoning" section, whose bullet "Explain **why** this step is needed and **what domain rule it implements**, not what the code mechanically does" restates the same why-not-what substance already stated in shared `code-comments`' "Purpose, not mechanism" section — while cards 2 and 4 remove the analogous Go/C# "Inline comments" sections entirely for exactly that reason ("byte-identical to the shared why-not-what rule ... now stated once in `code-comments`"). This applies the `no-redundancy-extraction` Shared Decision ("never a restatement of the rule's substance") inconsistently within the same batch.
**Fix:** Trim the restated why-not-what bullet from `python-comments`' Inline Comments section, keeping only the genuinely Python-specific selectivity guidance ("not on every step...") and the natural-language example.

### [NIT:consistency] Cards 2 and 3 delta narratives under-describe dropped bullets
**Location:** batch 1 / card 2, card 3
**Issue:** Card 2's Requirements prose doesn't mention that `golang-comments`' "File-level comments" bullet "Describe the file's role within the package, not just the package itself" is dropped outright (not moved to shared, simply gone). Card 3's Requirements prose names two dropped Module-docstring bullets but omits the also-dropped "For modules with multiple public functions or classes, list and briefly describe them" bullet (only `_mill/discussion.md`'s "bullets 16-17" phrasing covers it — the plan card's own delta text doesn't).
**Fix:** Update each card's Requirements delta narrative to account for every dropped bullet explicitly, so the diff description matches the verbatim final-content block it ships.

## Verdict

REQUEST_CHANGES
Batch 1's no-redundancy decision is applied inconsistently to Python's Inline Comments section; delta narratives in two cards are incomplete.
MILL_REVIEW_END
