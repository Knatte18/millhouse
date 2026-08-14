MILL_REVIEW_BEGIN
# Review: Extract a language-agnostic code-comments skill; add a general docstring-length ceiling, purpose-not-mechanism rule, mandatory file/module header, and prohibit measured-result/design-rationale narrative

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5
reviewed_file: _mill/discussion.md
date: 2026-08-14
```

## Findings

### [BLOCKING:scope] Purpose-not-mechanism already exists, duplicated, in Go/C#
**Section:** Scope > In, bullet "Purpose-not-mechanism principle" **Issue:** Discussion claims this is "new, not present in any file today in this general form," but `golang-comments/SKILL.md` (Introduction, lines 12-16, and "Exported symbol doc comments" rules, lines 67-70) and `csharp-comments/SKILL.md` (XML documentation, lines 14-16) already state it near-verbatim; Technical Context's per-file edit lists for both files never mention trimming these sections. **Fix:** Add these sections to the extraction/trim list for `golang-comments` and `csharp-comments`, or explicitly decide to leave them as redundant restatement (contradicts `shared-vs-duplicated-prose`).

### [BLOCKING:design] "Out" scope claim about workflow.md table is false
**Section:** Scope > Out, "workflow.md's language-detection table... already routes to python-comments/golang-comments/csharp-comments" **Issue:** `plugins/mill/skills/workflow/SKILL.md`'s Language Detection table (lines 71-74) has only Python and C# rows — no Go row, no marker files, no reference to `golang-comments` anywhere in the file. The "no new row needed" decision rests on a false premise. **Fix:** Either confirm Go routing happens elsewhere and cite it, or add this as an in-scope item (new Go row) — currently `golang-comments` (and the new Step-0 `code-comments` load line inside it) may never be triggered via this table.

### [BLOCKING:design] Line-wrap-style "byte-for-byte identical" claim is false for Python
**Section:** Scope > In, "Move already-identical content... semantic line-wrap style section (currently byte-for-byte duplicated modulo the tool-name sentence)" **Issue:** Go vs. C# are indeed identical modulo tool name, but Python's version (lines 138-151) has an extra closing paragraph with a materially different technical claim — Python docstrings *preserve* literal newlines (opposite of Go/C# tooling *collapsing* consecutive comment lines into one paragraph) — plus differing phrasing ("not the whole paragraph" vs "not the whole comment block"). A verbatim move-to-shared-section would either lose this Python-specific behavioral point or misplace it as shared. **Fix:** Decide explicitly whether Python's newline-preservation paragraph stays in `python-comments` as a language-specific addendum or gets folded into the shared section with a per-language variant.

## Verdict

REQUEST_CHANGES
Two source-grounding failures (workflow.md routing, line-wrap "byte-for-byte" claim) and one incomplete extraction inventory (purpose-not-mechanism already duplicated).
MILL_REVIEW_END
