# Plan: 26 (A) — auto-report-auto-submit

```yaml
task: 26 (A) — auto-report-auto-submit
slug: auto-report-auto-submit
approved: true
started: 20260507-071435
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: auto-report SKILL.md edits
    file: 01-auto-report-skill-edits.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: pure SKILL.md edits

- **Decision:** All changes are text edits to SKILL.md files only. No Python scripts, no config keys, no tests.
- **Rationale:** The auto-report behavior is purely instructional — LLM-executed skills have no binary to compile or tests to run.
- **Applies to:** all batches

### Decision: `--auto` as the auto-fire sentinel argument

- **Decision:** mill-go and mill-plan pass `--auto` when invoking mill-self-report due to `auto_report: true`. The skill interprets `--auto` as "file all without confirmation."
- **Rationale:** Explicit at the callsite; manual invocations are unambiguous regardless of config.
- **Applies to:** all batches

## All Files Touched

- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/skills/mill-self-report/SKILL.md`
