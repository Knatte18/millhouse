# Plan: code-comments skill: prohibit enumerating current consumers/writers of a shared resource

```yaml
task: 'code-comments skill: prohibit enumerating current consumers/writers of a shared resource'
slug: 'code-comments-skill-consumer-enumeration-rule'
approved: false
started: '20260904-161657'
parent: 'main'
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to schedule batches.
Every batch lives at `NN-<batch-slug>.md` in this directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: enumerated-consumer-rule
    file: 01-enumerated-consumer-rule.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-skills-index.py
```

## Shared Decisions

### Decision: single-file, prose-only change

- **Decision:** The entire task is one appended bullet in `plugins/mill/skills/code-comments/SKILL.md`'s `## Prohibited patterns` section.
  No Python, no template, no index regeneration.
- **Rationale:** `discussion.md`'s Scope section fixes the change to exactly this file.
  The skill's YAML frontmatter (`name:`, `description:`) is untouched, so `SKILLS.md` — which renders only that frontmatter — needs no regeneration and `/mill-skills-index` is not run.
- **Applies to:** all batches

### Decision: markdown style follows the file's own existing conventions

- **Decision:** The new bullet uses semantic line breaks (one sentence per line), two-space continuation indent to match sibling bullets, and the literal `—` em-dash character used by the four existing bullets in that section.
- **Rationale:** `plugins/mill/skills/markdown/SKILL.md` mandates semantic line breaks for generated markdown, and the four existing `## Prohibited patterns` bullets already follow exactly this shape.
  CLAUDE.md's ASCII-only rule applies to `print()`/`_log()` stdout, not to markdown source, so `—` is correct here.
- **Applies to:** all batches

### Decision: no mirror into per-language comment skills

- **Decision:** `golang-comments`, `csharp-comments`, and `python-comments` are not edited.
- **Rationale:** Of those three, only `plugins/golang/skills/golang-comments/SKILL.md` has a `## Prohibited patterns` section at all, and its single bullet is a language *syntax* rule.
  `code-comments` is the declared language-agnostic layer those skills build on, so duplicating a content rule into them would drift.
- **Applies to:** all batches

### Decision: `done_gate` left `null`

- **Decision:** `pipeline.done_gate` in `mill-config.yaml` is not set by this task.
- **Rationale:** The change has zero runtime surface — no Python, no Go, no C# is touched — so a repo-wide regression gate would only add cost without protecting anything this plan can break.
  Editing `mill-config.yaml` would additionally trip the `wiki-config-mutation` validator check for a change unrelated to the task's own scope.
- **Applies to:** all batches

## All Files Touched

- `plugins/mill/skills/code-comments/SKILL.md`
