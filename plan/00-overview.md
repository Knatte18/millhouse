# Plan: 17 (A) — SKILL.md API accuracy audit + implementer-brief contract fixes

```yaml
task: 17 (A) — SKILL.md API accuracy audit + implementer-brief contract fixes
slug: skill-api-audit
approved: true
started: 20260506-113414
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - name: skill-md-fixes
    file: 01-skill-md-fixes.md
    depends-on: []
    verify: null
  - name: session-id-template
    file: 02-session-id-template.md
    depends-on: [skill-md-fixes]
    verify: "uv run --project plugins/mill python -m py_compile plugins/mill/scripts/millpy-implement.py"
```

## Shared Decisions

### Decision: targeted-edits-only

- **Decision:** Every card is a targeted string replacement inside an existing file. No file is created or deleted. No logic changes outside the `millpy-implement.py` token dict addition.
- **Rationale:** The task scope is narrow (4 doc bugs + 1 template/script fix). YAGNI — don't restructure files while fixing a specific mismatch.
- **Applies to:** all batches

### Decision: no-new-tests

- **Decision:** No new unit or integration tests are written.
- **Rationale:** SKILL.md changes are documentation only (no runnable surface). The template token substitution is an existing code path covered by existing tests; adding one entry to the token dict is not a novel path.
- **Applies to:** all batches

## All Files Touched

- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/skills/mill-resume/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/templates/implementer-brief.md`
