# Plan: markdown skill: use semantic line breaks instead of one unbroken line per paragraph

```yaml
task: 'markdown skill: use semantic line breaks instead of one unbroken line per paragraph'
slug: markdown-semantic-line-breaks
approved: false
started: '20260805-183435'
parent: main
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to
schedule batches. Every batch lives at `NN-<batch-slug>.md` in this
directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: semantic-line-breaks
    file: 01-semantic-line-breaks.md
    depends-on: []
    verify: null
```

## Shared Decisions

_Cross-cutting decisions every batch inherits: naming conventions,
error-handling posture, test frameworks, style/lint constraints. One
subsection per decision. Batch-local decisions live in each batch file._

### Decision: break granularity is sentence-per-line, plus clause-boundary breaks

- **Decision:** the base rule is one line break per sentence.
On top of that, break also at an internal independent-clause boundary inside a single sentence: before a coordinating conjunction ("but"/"and"/"or") or a semicolon, but only when what follows is a second independent clause with its own subject and verb.
A comma followed by a coordinating conjunction that joins a list item or a compound predicate — no second subject and verb — does not trigger a break.
- **Rationale:** pure sentence-only breaking leaves long LLM-generated compound sentences under-addressed for citation/diff purposes, but a bare "comma+conjunction" trigger false-positives on lists and compound predicates (e.g. `python-comments/SKILL.md`'s own "...on how the index was created, and a "count" column representative...", a list join, not two independent clauses). The corrected disambiguator (second independent clause required) stays a concrete, checkable test for a writing agent.
- **Applies to:** all cards in this batch (`markdown/SKILL.md`, `python-comments/SKILL.md`, `golang-comments/SKILL.md`, `csharp-comments/SKILL.md`).

### Decision: ambiguous sentence-ending punctuation does not force a break

- **Decision:** when sentence-ending punctuation is ambiguous — e.g. a period inside a URL, or an abbreviation like "e.g." or "etc." — do not force a line break there. Readability wins over mechanical rule compliance in that edge case.
- **Rationale:** forcing a break on every literal `.`/`!`/`?` without judgment would break mid-URL or mid-abbreviation, reintroducing the mid-token break the original rule existed to eliminate.
- **Applies to:** all cards in this batch.

### Decision: markdown forbids trailing-whitespace/backslash hard breaks

- **Decision:** the markdown skill's rule text must explicitly require a plain newline (soft break) — never a line ending in two trailing spaces or a backslash (both force a real `<br>` in rendered output).
- **Rationale:** CommonMark renders a single bare newline inside a paragraph as a soft break (a space), which is what makes semantic line breaks invisible to a reader while staying addressable/diffable in source. A trailing-whitespace or backslash ending forces a visible break instead, and is easy to introduce by accident.
- **Applies to:** Card 1 (`markdown/SKILL.md`) only — Python/Go/C# comment syntax has no equivalent trailing-whitespace hard-break behavior.

### Decision: scope extends to python-comments, golang-comments, csharp-comments

- **Decision:** apply the same one-sentence-per-line (+ clause-boundary trigger) principle to docstrings, doc comments, and inline comments in all three language-specific comment skills, not only to `markdown/SKILL.md`.
- **Rationale:** the same addressing/diff-locality problems apply to multi-sentence prose inside a Python docstring, a Go doc comment, or a C# XML `<summary>` block. Godoc and XML-doc tooling collapse consecutive comment lines into one rendered paragraph the same way CommonMark does, so the soft-break-is-invisible property holds there too. Python docstrings are the one exception: raw `\n` is preserved and `help()`/`pydoc`/IDE tooltips display it as-is rather than reflowing — accepted as a display-only difference since the addressing/diff-locality benefit holds regardless.
- **Applies to:** Card 2 (`python-comments/SKILL.md`), Card 3 (`golang-comments/SKILL.md`), Card 4 (`csharp-comments/SKILL.md`).

### Decision: existing content is untouched except within the four files being edited

- **Decision:** the new rule applies to newly-written prose going forward. Do not reformat any already-committed markdown or code comments elsewhere in the repo or on other branches. The only fixes are the two contradictory examples that live inside the very files being edited: `golang-comments/SKILL.md` lines 29-31 and `python-comments/SKILL.md` lines 63-64/66-67.
- **Rationale:** retroactive reformatting is unbounded scope and was explicitly deferred by the user to a follow-up task. Fixing the two in-file examples is a bounded, direct consequence of editing those specific files' own rule text — leaving them contradictory would make the skill's own documentation self-inconsistent.
- **Applies to:** Card 2 (`python-comments/SKILL.md`), Card 3 (`golang-comments/SKILL.md`).

## All Files Touched

- `plugins/csharp/skills/csharp-comments/SKILL.md`
- `plugins/golang/skills/golang-comments/SKILL.md`
- `plugins/mill/skills/markdown/SKILL.md`
- `plugins/python/skills/python-comments/SKILL.md`
