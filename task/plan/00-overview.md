# Plan: 'mill-pause: graceful orchestrator pause between operations'

```yaml
task: 'mill-pause: graceful orchestrator pause between operations'
slug: mill-pause
approved: false
started: 20260512-140157
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
    name: skill-and-index
    file: 01-skill-and-index.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: skill-only

- **Decision:** Deliver as a single `SKILL.md` with no Python scripts, no status.md changes, no modifications to existing skills.
- **Rationale:** The task spec is explicit: "a minimal SKILL.md (~20 lines) with no scripts: it just sets the LLM's behavior for the remainder of the current turn." Behavioural change through the SKILL.md mechanism requires zero infrastructure.
- **Applies to:** all batches

### Decision: skills-index-regeneration

- **Decision:** After writing the SKILL.md, run `millpy-skills-index.py` to regenerate `SKILLS.md`. Do not hand-edit `SKILLS.md`.
- **Rationale:** `SKILLS.md` is auto-generated and the script is the authoritative regenerator. Hand-editing risks drift.
- **Applies to:** all batches

## All Files Touched

- `SKILLS.md`
- `plugins/mill/skills/mill-pause/SKILL.md`
