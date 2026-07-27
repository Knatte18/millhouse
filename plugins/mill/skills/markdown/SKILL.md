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

Write prose paragraphs as a single unbroken line each — do not insert a line break at a fixed column (e.g. ~80-88 characters). That mechanical wrapping habit lands mid-word or mid-phrase (`file-` / `based`) instead of at a sentence or clause boundary, because the break is chosen by character count, not by meaning. Renderers soft-wrap long lines for display; hard-wrapping in the source only fights that and produces ragged diffs. Only break a line where CommonMark requires it (e.g. blank lines around fenced code blocks), never at a fixed column count.
