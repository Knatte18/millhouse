---
name: markdown
description: Markdown formatting rules for generated files. Use when writing .md files.
---

# Markdown Formatting Skill

Rules for metadata formatting in generated markdown files. Language-agnostic.

---

## Fenced YAML for metadata

Use fenced YAML code blocks (` ```yaml `) for all metadata in generated `.md` files. This includes status files, review reports, child registry entries, and any other machine-written markdown.

YAML frontmatter (`---`) is reserved for system-parsed metadata in skill definitions (`SKILL.md`) and plugin manifests. Never use frontmatter for human-facing metadata in generated files — previewers hide it.

## Structure

- Use markdown headings (`#`, `##`) to structure the document.
- Place metadata in fenced YAML code blocks immediately after their heading.
- Group related fields in a single block. Use separate blocks for separate concerns (e.g., task metadata vs. timeline).

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

### Example

```markdown
<!-- BAD: single unbroken line hides sentence boundaries from diffs and citations -->
The script renames the column, updates the ORM model, and refreshes the cached schema file. The migration touched three files, and the review took three rounds to catch a stale reference in the reporting job.

<!-- GOOD: one sentence per line, with a clause-boundary break inside the second sentence -->
The script renames the column, updates the ORM model, and refreshes the cached schema file.
The migration touched three files,
and the review took three rounds to catch a stale reference in the reporting job.
```
