# Plan: 27 (A) — Prune unused skills and scripts

```yaml
task: 27 (A) — Prune unused skills and scripts
slug: prune-millhouse
approved: true
started: 20260507-072611
parent: main
root: ""
verify: python plugins/mill/unit_tests/run-all.py
```

## Batch Index

```yaml
batches:
  - number: 1
    name: Prune unused skills and scripts
    file: 01-prune-skills.md
    depends-on: []
    verify: python plugins/mill/unit_tests/run-all.py
```

## Shared Decisions

### Decision: single batch

- **Decision:** All work lands in one batch.
- **Rationale:** Every change is a small targeted edit or deletion. The total context is well within a 200k-token window. No inter-batch dependency exists that would justify splitting.
- **Applies to:** all batches

### Decision: create before delete for test-gh-issues.py

- **Decision:** Card 1 creates `test-gh-issues.py` before Card 2 deletes `test-millpy-fetch-issues.py`. Both cards are in the same batch; the implementer must execute Card 1 first.
- **Rationale:** The new file is extracted from the source being deleted. If deleted first, the implementer has no source to copy from.
- **Applies to:** batch 1

### Decision: SCRIPTS.md updated by hand, SKILLS.md via script

- **Decision:** Remove the three deleted-script sections from `SCRIPTS.md` by direct edit. Regenerate `SKILLS.md` by running `millpy-skills-index.py`.
- **Rationale:** SCRIPTS.md changes are purely subtractive (remove three clearly-delimited sections); manual edit is safe and avoids re-running all scripts. SKILLS.md has a single-command regenerator that is reliable and idempotent.
- **Applies to:** batch 1

## All Files Touched

- `SKILLS.md`
- `plugins/mill/SCRIPTS.md`
- `plugins/mill/scripts/_config.py`
- `plugins/mill/scripts/_shortcuts.py`
- `plugins/mill/scripts/millpy-cleanup.py`
- `plugins/mill/skills/mill-setup/SKILL.md`
- `plugins/mill/unit_tests/test-cleanup.py`
- `plugins/mill/unit_tests/test-gh-issues.py` *(created)*
- `plugins/mill/unit_tests/test-shortcut-wrapper.py`
- `plugins/mill/unit_tests/test-skill-writer.py`
