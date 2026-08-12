# Plan: mill-go-base SKILL.md: resume phase branch, entry routing, and undocumented flags

```yaml
task: 'mill-go-base SKILL.md: resume phase branch, entry routing, and undocumented flags'
slug: mill-go-base-skilldoc-and-logic-bugs-2
approved: true
started: '2026-08-12T17:57:32Z'
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
    name: routing-fixes
    file: 01-routing-fixes.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-mill-go-base-agent-only.py test-skill-helper-drift.py
```

## Shared Decisions

### Decision: prose-only edits, no Python changes

- **Decision:** Both fixes (#837, #840) are edits to orchestrator-prompt markdown text (`SKILL.md`, `resume.md`) consumed by the LLM acting as Builder. There is no separate Python "router" implementing this routing logic, so neither card touches any `.py` file and no Python signature changes.
- **Rationale:** Confirmed in `_mill/discussion.md`'s "Technical context" section — both files are pure orchestrator-prompt prose; `_status.read_batches` is an existing helper already used elsewhere in `SKILL.md`'s widening table (the `self-resolved-verify-logic` bullet), reused here rather than inventing a new accessor.
- **Applies to:** all batches

### Decision: no shared helper between the two fixes

- **Decision:** #837's liveness check (in `SKILL.md`) and #840's fallback (in `resume.md`) are each self-contained edits to their own file. Do not factor them into a shared helper or unify their routing.
- **Rationale:** `_mill/discussion.md`'s `837-approved-batch-liveness-check` Decision explicitly rejected unifying #837 and #840 into one shared-fallback mechanism as a bigger, riskier diff that touches already-correct behavior for no material benefit.
- **Applies to:** all batches

## All Files Touched

- `plugins/mill/skills/mill-go-base/SKILL.md`
- `plugins/mill/skills/mill-go-base/resume.md`
