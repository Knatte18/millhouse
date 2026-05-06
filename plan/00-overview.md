# Plan: 22 (A) — SKILL.md round-2 fixes

```yaml
task: 22 (A) — SKILL.md round-2 fixes
slug: skill-md-fixes-2
approved: true
started: 20260506-162556
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - name: mill-plan SKILL.md fixes
    file: 01-skill-md-fixes.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: documentation-only scope

- **Decision:** No Python code changes. All edits are confined to `plugins/mill/skills/mill-plan/SKILL.md`.
- **Rationale:** Both issues (#164, #169) are SKILL.md documentation gaps. The validator logic and the flag implementation are correct; only the skill instructions are wrong.
- **Applies to:** all batches

## All Files Touched

- `plugins/mill/skills/mill-plan/SKILL.md`
