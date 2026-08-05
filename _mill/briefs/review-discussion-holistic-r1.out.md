MILL_REVIEW_BEGIN
# Review: markdown skill: use semantic line breaks instead of one unbroken line per paragraph

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5
reviewed_file: _mill/discussion.md
date: 2026-08-05
```

## Findings

### [GAP] golang-comments lines 197-198 don't actually violate the new rule
**Section:** Scope (In, bullet 3) / Decision "Existing-content reformatting"
**Issue:** Verified against source: lines 197-198 read `// Wrap the error with %w to preserve the underlying error chain;` / `// callers can then use errors.Is()...` — this already breaks exactly at the semicolon, which the newly-decided clause-boundary trigger explicitly designates as a valid break point. Only lines 29-31 actually hard-wrap mid-phrase ("writes a" / "structured JSON response"); 197-198 is cited twice (Scope + Decision) as needing the same fix but requires none.
**Fix:** Drop 197-198 from the "needs fixing" list, or explain what change (if any) is actually intended there.

### [GAP] Soft-break-invisibility rationale not established for Python docstrings
**Section:** Decision "Scope extension: also update python-comments..." / Technical context
**Issue:** The rationale explicitly names only "Godoc and XML-doc tooling" as collapsing consecutive comment lines the way CommonMark does; it never makes the equivalent claim for Python. Unlike markdown/godoc/XML-doc, raw Python docstrings retain literal `\n` characters, and common consumption paths (`help()`, `pydoc`, many IDE tooltips) print the docstring text as-is rather than reflowing it — so a sentence-per-line docstring could show up as visibly broken text where the other two languages' tooling would render it seamlessly.
**Fix:** State explicitly whether this rendering risk was considered for Python, and whether it's accepted or the docs pipeline (e.g. Sphinx/Napoleon) neutralizes it.

### [GAP] Clause-boundary trigger — the hardest part of the rule — has no required example
**Section:** Scope (In, bullet 4)
**Issue:** The example requirement says only "illustrating the new one-sentence-per-line style," not the clause-boundary trigger (comma+coordinating-conjunction or semicolon before an independent clause). That trigger requires judging independent-clause-hood, the one part of the rule the discussion itself calls a judgment call distinct from mechanical sentence splitting — yet no example is mandated to pin down correct application.
**Fix:** Require at least one example (in at least one of the four files) that demonstrates the clause-boundary break, not just the sentence-per-line base case.

### [NOTE] Rule scope vs. non-paragraph markdown contexts (tables, blockquotes) unaddressed
**Section:** Scope (In, bullet 1) / new rule text
**Issue:** The rule targets "prose paragraphs"; it doesn't say whether table cells (where a bare newline breaks table parsing) or blockquotes (where each line needs a `>` prefix) are exempt. Likely obvious to a careful writer, but the whole point of this task is removing ambiguity for LLM writers.
**Fix:** Optionally add one clause noting the rule doesn't apply inside table cells/single-line contexts.

## Verdict

GAPS_FOUND
Two scope-inaccuracies (golang 197-198, Python rendering rationale) and an under-specified clause-boundary example requirement.
MILL_REVIEW_END
