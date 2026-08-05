# Batch: semantic-line-breaks

```yaml
task: 'markdown skill: use semantic line breaks instead of one unbroken line per paragraph'
batch: semantic-line-breaks
number: 1
cards: 4
verify: null
depends-on: []
```

## Rename mechanic

_Not applicable — this batch has no `Moves:` entries in any card._

## Batch Scope

This batch rewrites `plugins/mill/skills/markdown/SKILL.md`'s "No fixed-column hard-wrapping" section to prescribe semantic line breaks (one sentence per line, plus a clause-boundary trigger for long compound sentences) instead of "single unbroken line per paragraph," and adds the equivalent new guidance — with a before/after example — to the three language-specific comment skills (`python-comments`, `golang-comments`, `csharp-comments`), none of which currently has any line-wrap rule. Two of those three files also get a narrow in-place fix to an existing example that hard-wraps mid-sentence, contradicting the new rule being added to the same file. All four edits are independent (no card depends on another) and are grouped into one batch because each file is small (26-214 lines), a single Sonnet session holds all four easily, and every card is driven by the same rule text and the same "Decisions" reasoning documented in `00-overview.md`. There is no external interface — this is documentation-only, nothing downstream consumes an output of this batch.

## Cards

### Card 1: Rewrite markdown/SKILL.md's "No fixed-column hard-wrapping" section

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/markdown/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**

Replace the entire `## No fixed-column hard-wrapping` section (the heading plus its one paragraph, currently lines 24-26) — the exact current text is:

```
## No fixed-column hard-wrapping

Write prose paragraphs as a single unbroken line each — do not insert a line break at a fixed column (e.g. ~80-88 characters). That mechanical wrapping habit lands mid-word or mid-phrase (`file-` / `based`) instead of at a sentence or clause boundary, because the break is chosen by character count, not by meaning. Renderers soft-wrap long lines for display; hard-wrapping in the source only fights that and produces ragged diffs. Only break a line where CommonMark requires it (e.g. blank lines around fenced code blocks), never at a fixed column count.
```

with this exact replacement body (it is itself written with semantic line breaks — one sentence per line, with clause-boundary breaks where the "Break granularity" decision in `00-overview.md` calls for one — dogfooding the rule it describes; reproduce it verbatim, including every individual line break):

```
## No fixed-column hard-wrapping

Do not hard-wrap prose at a fixed column (e.g. ~80-88 characters).
That habit lands a line break mid-word or mid-phrase (`file-` / `based`) instead of at a sentence or clause boundary, because the break is chosen by character count, not by meaning.

Instead, write one sentence per line — that is a semantic line break.
Break also inside a long sentence, at an internal independent-clause boundary.
An internal independent-clause boundary is a comma followed by a coordinating conjunction ("but", "and", "or"), or a semicolon, where what follows has its own subject and verb.
A comma followed by a coordinating conjunction that joins a list item or a compound predicate — with only one subject and verb — does not trigger a break.

When sentence-ending punctuation is ambiguous — for example a period inside a URL, or an abbreviation like "e.g." or "etc." — do not force a break there.
Readability wins over mechanical rule compliance in that edge case.

Use a plain newline — a soft break — never a line ending in two trailing spaces or a backslash.
Both force a real `<br>` in rendered output.
CommonMark renders a single bare newline inside a paragraph as a soft break, shown as a space by any conforming renderer.
This is what makes semantic line breaks invisible to a reader while still being addressable and diffable in source.
A trailing-whitespace or backslash line ending changes how the rendered document actually looks.

This rule applies to prose paragraphs.
It does not apply inside table cells, where a bare newline breaks table parsing.
Blockquote content stays on one line per default project style.
CommonMark permits multi-line blockquotes to soft-wrap the same as a normal paragraph, so this is a stylistic default, not a syntax requirement.

The only other places to break are where CommonMark requires it — e.g. blank lines around fenced code blocks — and where this rule calls for a semantic break.
```

Immediately after that body, on its own new line, add a level-3 heading reading exactly `### Example` (three hashes, one space, capital E) — this is the file's first-ever fenced code example (the file was previously pure prose, per `00-overview.md`), a compact before/after snippet rather than the "Bad example"/"Good example" heading structure used in the three comment skills, matching this file's own style. Immediately below that heading, add this fenced ` ```markdown ` block verbatim:

```markdown
<!-- BAD: single unbroken line hides sentence boundaries from diffs and citations -->
The script renames the column, updates the ORM model, and refreshes the cached schema file. The migration touched three files, and the review took three rounds to catch a stale reference in the reporting job.

<!-- GOOD: one sentence per line, with a clause-boundary break inside the second sentence -->
The script renames the column, updates the ORM model, and refreshes the cached schema file.
The migration touched three files,
and the review took three rounds to catch a stale reference in the reporting job.
```

This example is the one required (per the "Break granularity" decision) to demonstrate both the positive clause-boundary break (the "and the review took..." split) and the negative case where a comma+conjunction does NOT break (the "updates the ORM model, and refreshes" compound predicate, one subject "The script", stays on one line). Together, the heading + body replacement above and this `### Example` subsection make up the file's entire new `## No fixed-column hard-wrapping` section — do not carry over any part of the original paragraph.

- **Commit:** `docs(markdown): prescribe semantic line breaks over single-line paragraphs`

### Card 2: Add semantic-line-break guidance to python-comments/SKILL.md and fix its own hard-wrapped example

- **Context:** none
- **Edits:**
  - `plugins/python/skills/python-comments/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**

Part A — add a new section. Insert the following new section body immediately before the `## Prohibited patterns` heading (i.e. immediately after the closing ` ``` ` of the second "Good vs bad examples" code block under `## Inline comments — narrate the reasoning`), with a blank line before and after. Reproduce it verbatim, including every individual line break:

```
## Line-wrap style: semantic line breaks, not fixed-column wrapping

Do not hard-wrap docstring or comment prose at a fixed column.
Write one sentence per line instead — a semantic line break — so a diff or review citation lands on the sentence that changed, not the whole paragraph.
Break also inside a long sentence, at an internal independent-clause boundary: a comma followed by a coordinating conjunction ("but", "and", "or"), or a semicolon, where what follows has its own subject and verb.
A comma followed by a coordinating conjunction that joins a list item or a compound predicate does not trigger a break.

Raw Python docstrings preserve literal newlines, so tools like `help()`, `pydoc`, and IDE tooltips display sentence-per-line text as short lines rather than reflowing it into one paragraph.
This is a display difference only — the text stays fully readable,
and the addressing/diff-locality benefit holds regardless of how it renders.
```

Immediately after that body, on its own new line, add a level-3 heading reading exactly `### Good vs bad examples` (matching this file's existing heading pattern used twice already, e.g. under `## Function docstrings` and `## Inline comments`). Immediately below that heading, add this fenced ` ```python ` block verbatim:

```python
# BAD — single unbroken line, hides sentence boundaries from diffs and citations
"""
Loads the raw transaction file and filters out zero-price rows. The result feeds directly into the CBI stitching step, and later steps assume the join has already happened.
"""

# GOOD — one sentence per line, with a clause-boundary break inside the second sentence
"""
Loads the raw transaction file and filters out zero-price rows.
The result feeds directly into the CBI stitching step,
and later steps assume the join has already happened.
"""
```

Together, the heading + body replacement above and this `### Good vs bad examples` subsection make up the file's entire new section.

Part B — fix the file's own hard-wrapped example. Inside the `create_CBI_from_SSB_and_RSI` `GOOD` docstring example (under `### Good vs bad examples`, the one at the top of the file under `## Function docstrings`), the numbered list currently reads (exact current text, lines 62-67):

```
    1. Use SSB_quarterly for the period before RSI_weekly is sufficiently populated.
       This is a quarterly sampled price index from SSB, with distinct regions
       (covering all of Norway), but no count data.
    2. Use RSI_weekly for the main period, where this RSI is sufficiently populated.
       This RSI is supplied as a LORSI cube class, which contains Logarithmic
       Repeated Sales Indices (LORSI).
```

Replace those six lines with these four lines (same content, semantic line breaks — sentence-per-line, no clause-boundary break in either item since neither's comma+conjunction precedes a second independent clause: item 1's "but no count data" has no verb, item 2 has no comma+but/and/or at all):

```
    1. Use SSB_quarterly for the period before RSI_weekly is sufficiently populated.
       This is a quarterly sampled price index from SSB, with distinct regions (covering all of Norway), but no count data.
    2. Use RSI_weekly for the main period, where this RSI is sufficiently populated.
       This RSI is supplied as a LORSI cube class, which contains Logarithmic Repeated Sales Indices (LORSI).
```

Do not touch the `Returns:` paragraph immediately below (currently lines 69-71) — it is out of scope for this fix per `00-overview.md`'s "existing content is untouched" decision, even though its own comma+"and" ("...on how the index was created, and a "count" column representative...") is the file's own worked false-positive example cited in the "Break granularity" decision and must stay exactly as-is.

- **Commit:** `docs(python-comments): add semantic-line-break guidance and fix hard-wrapped docstring example`

### Card 3: Add semantic-line-break guidance to golang-comments/SKILL.md and fix its own hard-wrapped example

- **Context:** none
- **Edits:**
  - `plugins/golang/skills/golang-comments/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**

Part A — fix the file's own hard-wrapped example first. The `## File-level comments` section's example currently reads (exact current text, lines 28-34):

```go
// handlers_auth.go implements the HTTP handlers for login, logout, and token refresh.
// Each handler validates the request, delegates to the auth service, and writes a
// structured JSON response.

package auth
```

Replace the three comment lines with two (same content, semantic line breaks — sentence-per-line; the second sentence stays on one line because "delegates...and writes" is a compound predicate under one subject "Each handler", not a second independent clause):

```go
// handlers_auth.go implements the HTTP handlers for login, logout, and token refresh.
// Each handler validates the request, delegates to the auth service, and writes a structured JSON response.

package auth
```

Part B — add a new section. Insert the following new section immediately before the `## Inline comments` heading (i.e. immediately after the closing ` ``` ` of the `## Interface implementations` example, and its trailing `---` divider — keep that `---` divider where it is, then insert the new section, then its own `---` divider, matching this file's existing pattern of a `---` divider between every top-level section), with a blank line before and after. Reproduce it verbatim, including every individual line break and the two nested ` ```go ` fenced examples inside it:

````
## Line-wrap style: semantic line breaks, not fixed-column wrapping

Do not hard-wrap a multi-line doc comment at a fixed column.
Write one sentence per line instead — a semantic line break — so a diff or review citation lands on the sentence that changed, not the whole comment block.
Break also inside a long sentence, at an internal independent-clause boundary: a comma followed by a coordinating conjunction ("but", "and", "or"), or a semicolon, where what follows has its own subject and verb.
A comma followed by a coordinating conjunction that joins a list item or a compound predicate does not trigger a break.

Godoc collapses consecutive `//` comment lines into one rendered paragraph, the same way CommonMark does for markdown, so a semantic line break is invisible to a reader of the rendered doc.

**Bad example:**

```go
// LoadPortfolio reads every position file in dir and validates each one against the
// schema. It merges the valid files into a single Portfolio, and it returns an error
// if any file fails validation or two files declare the same position ID.
func LoadPortfolio(dir string) (*Portfolio, error) {
```

**Good example:**

```go
// LoadPortfolio reads every position file in dir and validates each one against the schema.
// It merges the valid files into a single Portfolio,
// and it returns an error if any file fails validation or two files declare the same position ID.
func LoadPortfolio(dir string) (*Portfolio, error) {
```

---
````

The heading immediately following `## Inline comments` in the file today (`## Error handling`, unchanged by this card) follows unchanged. Concretely: the new section and its trailing `---` go between the existing `## Interface implementations` example's `---` divider and the existing `## Inline comments` heading, with no other reordering.

- **Commit:** `docs(golang-comments): add semantic-line-break guidance and fix hard-wrapped file-header example`

### Card 4: Add semantic-line-break guidance and example to csharp-comments/SKILL.md

- **Context:** none
- **Edits:**
  - `plugins/csharp/skills/csharp-comments/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**

Insert the following new section immediately before the `## Prohibited patterns` heading, with a blank line before and after (this file has no existing multi-line comment example of any kind, so this is purely additive). Reproduce it verbatim, including every individual line break and the two nested ` ```csharp ` fenced examples inside it:

````
## Line-wrap style: semantic line breaks, not fixed-column wrapping

Do not hard-wrap a multi-line `/// <summary>` or inline comment at a fixed column.
Write one sentence per line instead — a semantic line break — so a diff or review citation lands on the sentence that changed, not the whole comment block.
Break also inside a long sentence, at an internal independent-clause boundary: a comma followed by a coordinating conjunction ("but", "and", "or"), or a semicolon, where what follows has its own subject and verb.
A comma followed by a coordinating conjunction that joins a list item or a compound predicate does not trigger a break.

XML-doc tooling collapses consecutive `///` comment lines into one rendered paragraph, the same way CommonMark does for markdown, so a semantic line break is invisible to a reader of the rendered doc.

**Bad example:**

```csharp
/// <summary>
/// Validates the incoming order against the pricing catalog and applies any active
/// discount codes. It then persists the finalized order, and it returns the
/// confirmation number the caller displays to the customer.
/// </summary>
public string ProcessOrder(Order order) {
```

**Good example:**

```csharp
/// <summary>
/// Validates the incoming order against the pricing catalog and applies any active discount codes.
/// It then persists the finalized order,
/// and it returns the confirmation number the caller displays to the customer.
/// </summary>
public string ProcessOrder(Order order) {
```
````

- **Commit:** `docs(csharp-comments): add semantic-line-break guidance and example`

## Batch Tests

`verify: null` — this batch changes only SKILL.md instruction prose across four files; there is no runtime code and no automated test surface (confirmed in `_mill/discussion.md`'s "Testing" section: "there is no runtime code, so there is no automated test surface"). Verification is by inspection during plan review and code review: confirm each rewritten/added section is itself written with semantic line breaks (dogfooding the rule it describes — verified line-by-line above in each card's Requirements), and confirm the two fixed examples (`golang-comments` lines 29-31, `python-comments` lines 63-64/66-67) no longer hard-wrap mid-sentence.
