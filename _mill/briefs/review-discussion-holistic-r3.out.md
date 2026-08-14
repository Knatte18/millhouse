MILL_REVIEW_BEGIN
# Review: Extract a language-agnostic code-comments skill; add a general docstring-length ceiling, purpose-not-mechanism rule, mandatory file/module header, and prohibit measured-result/design-rationale narrative

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; harness metadata reports "Sonnet 5" / claude-sonnet-5)
reviewed_file: _mill/discussion.md
date: 2026-08-14
```

## Findings

### [BLOCKING:consistency] Python's "good" docstring example still narrates how-it-works
**Section:** Technical Context, `plugins/python/skills/python-comments/SKILL.md` **Issue:** The edit range for "Function docstrings" is given as ~20-51, but the "Good vs bad examples" block (actual source lines 53-73) sits outside that range and its "GOOD" example still shows numbered `1. ... 2. ...` how-it-works narrative inside the docstring — exactly the pattern `python-how-it-works-conflict` removes. Left as-is, the rewritten prose and the untouched example directly contradict each other. **Fix:** Extend the Technical Context edit instruction for this file to also rewrite the example block so the shown "good" docstring matches the new rule (drop the numbered steps, or replace with a decomposition-style example).

### [BLOCKING:scope] Python module-docstring header prose not trimmed like Go's parallel section
**Section:** Technical Context, `plugins/python/skills/python-comments/SKILL.md` vs. `golang-comments/SKILL.md` **Issue:** Go's parallel "File-level comments" section gets an explicit "trim to syntax only, principle moves to code-comments" instruction, but Python's "Module docstrings" section (source lines 16-17, which state the same header principle — describe purpose in prose, list public functions/classes) only gets a fix to line 18, leaving 16-17 as duplicated principle prose. This contradicts `shared-vs-duplicated-prose`'s "never a restatement of the rule's substance." **Fix:** Add an explicit trim instruction for python-comments' Module docstrings bullets 16-17, mirroring the golang-comments treatment.

### [NIT:consistency] Line-wrap extraction ranges numerically overlap the "stays in place" paragraph
**Section:** Technical Context, golang/python line-wrap-style entries **Issue:** Cited ranges (~187-198 golang, ~138-149 python) numerically span past the ambiguous-punctuation paragraph into the trailing per-language rendering paragraph the same sentence says must stay in place — self-contradictory as written, even though intent is clear from prose. **Fix:** Tighten cited ranges to end at the ambiguous-punctuation paragraph, or state the "keep" paragraph's line number separately from the extraction range.

## Verdict

REQUEST_CHANGES
Two Technical Context gaps in the python-comments edit plan risk contradictory/duplicated prose surviving the rewrite.
MILL_REVIEW_END
