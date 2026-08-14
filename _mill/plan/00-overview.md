# Plan: Extract a language-agnostic code-comments skill; add a general docstring-length ceiling, purpose-not-mechanism rule, mandatory file/module header, and prohibit measured-result/design-rationale narrative

```yaml
task: Extract a language-agnostic code-comments skill; add a general docstring-length ceiling, purpose-not-mechanism rule, mandatory file/module header, and prohibit measured-result/design-rationale narrative
slug: code-comments-skill-extraction
approved: false
started: 20260814-092858
parent: main
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to schedule batches.
Every batch lives at `NN-<batch-slug>.md` in this directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: shared-code-comments-skill
    file: 01-shared-code-comments-skill.md
    depends-on: []
    verify: null
  - number: 2
    name: workflow-routing-and-index
    file: 02-workflow-routing-and-index.md
    depends-on: [1]
    verify: null
```

## Shared Decisions

_Cross-cutting decisions every batch inherits: naming conventions, error-handling posture, test frameworks, style/lint constraints.
One subsection per decision.
Batch-local decisions live in each batch file._

### Decision: no-redundancy-extraction

- **Decision:** Rules that are substantively identical across languages (purpose-not-mechanism, length ceiling, file/module header requirement, no-end-of-line-comments, the merged mechanical-restatement rule, plus the already-identical line-wrap-style common core and comment-out/edit-history prohibitions) are stated exactly once in the new `code-comments` skill. Each per-language file keeps only its own syntax and one code example per shared rule — never a restatement of the rule's substance.
- **Rationale:** operator call ("I do NOT like redundancy") — extracting only byte-identical text and leaving new rules duplicated three ways would reintroduce the exact drift problem (`python-comments` silently contradicting the other two) that motivated this task.
- **Applies to:** all batches.

### Decision: no-automated-tests

- **Decision:** This task edits only Markdown `SKILL.md` prose (plus a mechanical regeneration of `SKILLS.md`). No automated test suite applies. Verification is manual/textual — grep-based confirmation that extracted content is not left duplicated in place, plus confirmation that each per-language file's structure matches the plan. `verify:` is `null` at both the overview and every batch.
- **Rationale:** matches `_mill/discussion.md`'s own `## Testing` section, which specifies grep-based manual verification, not a runnable test command.
- **Applies to:** all batches.

### Decision: line-wrap-rendering-paragraph-stays-per-language

- **Decision:** The line-wrap-style section splits at extraction. The common core (hard-wrap prohibition, one-sentence-per-line, clause-boundary break rule, ambiguous-punctuation exception) moves into shared `code-comments` verbatim. Each per-language file keeps only its own trailing note on how its tooling renders the result: Go/C# keep "consecutive comment lines collapse into one rendered paragraph"; Python keeps "raw docstrings preserve literal newlines" (the opposite claim).
- **Rationale:** review-driven correction during discussion — Python's rendering behavior is materially different from Go/C#'s, not just a tool-name swap, so it cannot be generalized into one shared sentence without losing the distinction.
- **Applies to:** batch 1 (`code-comments`, `golang-comments`, `python-comments`, `csharp-comments` cards).

### Decision: end-of-line-comments-no-carveout

- **Decision:** "No end-of-line comments" is a fully shared rule with no per-language carve-out. Go's `const` block example is rewritten to put each constant's comment on its own line above that constant, dropping the column-aligned end-of-line style.
- **Rationale:** operator call, for git-diff cleanliness — aligned end-of-line comments in a grouped block force realignment of every sibling line whenever one identifier's length changes.
- **Applies to:** batch 1 (`golang-comments` card).

## All Files Touched

_Full union of every `Creates:` / `Edits:` / `Moves:` **target** path across every batch, sorted alphabetically (Move **source** paths are excluded — they disappear, like `Deletes:` tokens).
Cards are the source of truth;
this section is the input `_plan_validate.py`'s `all-files-touched-mismatch` check cross-references against the derived union of every card's `Edits:`/`Creates:`/Move-target paths, to catch drift between the hand/agent-maintained list here and that derived union._

- `SKILLS.md`
- `plugins/csharp/skills/csharp-comments/SKILL.md`
- `plugins/golang/skills/golang-comments/SKILL.md`
- `plugins/mill/skills/code-comments/SKILL.md`
- `plugins/mill/skills/workflow/SKILL.md`
- `plugins/python/skills/python-comments/SKILL.md`
