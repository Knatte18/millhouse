---
name: code-comments
description: Language-agnostic code comment and documentation rules. Use when writing or reviewing code comments in any language.
---

# Code Comments Skill

Guidelines for code comments and documentation.
Language-agnostic — each language's own `{lang}-comments` skill covers syntax and mechanics on top of this.

---

## Purpose, not mechanism

Doc comments explain **what** a symbol does and **why** it exists — not just a restatement of the name.
Do **not** narrate **how** something works internally (algorithm steps, control flow);
that belongs in the implementation, not the comment.
A reader should understand a symbol's purpose from its signature and doc comment alone, without reading the implementation.

Inline comments explain **why** something is done, never **what** is being done;
the code already shows that.
If the code needs a "what" comment, the code itself is unclear — refactor instead.

### Corollary: many comments needed is a refactoring signal

An implementation that seems to need many comments to explain itself is a signal to decompose it into well-named sub-functions with their own docstrings — not evidence that the docstring needs to be longer.

## Length ceiling

Doc comments rarely need to exceed ~10-15 lines.
Longer is a symptom that implementation-narrative has crept into the comment, not a size problem to fix by trimming words.

## File/module header

Every source file must open with a comment describing what the file contains and why it exists, in plain narrative prose.
One to three lines is usually sufficient.
See the per-language skill for exact placement and syntax.

## No end-of-line comments

Comments go on their own line, above the code they describe — never at the end of a code line.
An aligned end-of-line comment in a grouped block forces every sibling line to realign (and shows up in the diff) whenever one identifier's length changes;
an above-line comment avoids that.

## Line-wrap style — semantic line breaks, not fixed-column wrapping

Do not hard-wrap a multi-line comment at a fixed column.
Write one sentence per line instead — a semantic line break — so a diff or review citation lands on the sentence that changed, not the whole comment block.
Break also inside a long sentence, at an internal independent-clause boundary: a comma followed by a coordinating conjunction ("but", "and", "or"),
or a semicolon, where what follows has its own subject and verb.
A comma followed by a coordinating conjunction that joins a list item or a compound predicate does not trigger a break.

When sentence-ending punctuation is ambiguous — for example a period inside a URL, or an abbreviation like "e.g." or "etc." — do not force a break there.
Readability wins over mechanical rule compliance in that edge case.

See the per-language skill for how that language's tooling renders consecutive comment lines.

## Prohibited patterns

- **Never** comment out code.
  Delete it.
  Version control handles history.
- **No edit-history comments** ("added in v2", "removed old logic", "changed from X to Y").
- **No mechanical restatements** — a comment that just restates what the code already says by reading it.
  If code needs a "what" comment, refactor instead.
- **No measured-result or design-rationale narrative** — a doc comment must not contain measured numeric deltas, rejected-alternative trails, or reproduction/incident narrative.
  That belongs in an inline why-comment, `_codeguide/` module docs, or a `Doc/` design-decision note.
- **No enumerated-consumer lists** — don't name every current caller, writer, consumer, or implementer of a shared symbol or resource when the comment's point doesn't depend on which ones currently do
  (e.g. "the logger, reed, shuttle, and burler all write it").
  That list goes stale whenever a subsystem is added or removed, turning an unrelated change elsewhere in the codebase into a forced edit here.
  Write "several of `<component>`'s own subsystems" or similar instead, unless the specific names are themselves load-bearing to the point being made.
