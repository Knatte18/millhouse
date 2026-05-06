# Plan: 21 (A) — mill-go cleanliness gate fixes

```yaml
task: 21 (A) — mill-go cleanliness gate fixes
slug: mill-cleanliness-gate-fixes
approved: true
started: 20260506-161233
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
  - name: 01-skill-fixes
    file: 01-skill-fixes.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: skill-md-only

- **Decision:** All changes are confined to two SKILL.md files; no Python helper changes.
- **Rationale:** The bugs are in orchestrator instructions, not in Python logic. Keeping the fix surface minimal reduces risk of regressions in the shared plugin.
- **Applies to:** all batches

## All Files Touched

- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
