# Plan: mill-merge / mill-merge-in: brief-staging path bug and easy-to-miss caching instruction

```yaml
task: 'mill-merge / mill-merge-in: brief-staging path bug and easy-to-miss caching instruction'
slug: mill-merge-family-doc-gaps
approved: true
started: 20260919-112858
parent: main
root: ""
verify: null
discussion_sha: 9b92d19c24071f8fe3d5d39af67778fbf6ffa45c
```

## Batch Index

```yaml
batches:
  - number: 1
    name: doc-gaps-fixes
    file: 01-doc-gaps-fixes.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-brief-commit.py test-skill-helper-drift.py
```

## Shared Decisions

### Decision: doc-only, no `mill-config.yaml` change

- **Decision:** This plan touches only the two SKILL.md files named in `_mill/discussion.md`'s Scope section. It does not set `pipeline.done_gate` in `mill-config.yaml`, even though the batch's own `verify:` scope (two specific test files) does not cover the entire module tree.
- **Rationale:** `done_gate` is currently `null` hub-wide (pre-existing hub state, unrelated to this task). Introducing a repo-wide done-gate command is a hub-wide policy change with its own blast radius; bundling it into a two-file documentation task would expand scope well past what `_mill/discussion.md`'s Scope section authorizes ("no changes to any other SKILL.md, script, or helper"). The existing `test-brief-commit.py` / `test-skill-helper-drift.py` regression locks are the exact and sufficient safety net for a prose-only change to two SKILL.md files that add explanatory paragraphs without touching any bash command already covered by those locks.
- **Applies to:** all batches (there is only one).

### Decision: no test changes

- **Decision:** No unit test is added, removed, or modified by this plan.
- **Rationale:** Both cards add prose only — a new paragraph in each SKILL.md, inserted next to an already-correct bash block. `test-brief-commit.py`'s existing substring assertion (`"add _mill/briefs/"` present in `mill-merge-in/SKILL.md`) is unaffected by prose added elsewhere in the same file, and there is no code path in `mill-merge/SKILL.md`'s new recovery-path paragraph for a script-level test to exercise (see `_mill/discussion.md`'s `## Testing` section).
- **Applies to:** all batches (there is only one).

## All Files Touched

- `plugins/mill/skills/mill-merge-in/SKILL.md`
- `plugins/mill/skills/mill-merge/SKILL.md`
