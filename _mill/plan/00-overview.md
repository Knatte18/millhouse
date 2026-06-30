# Plan: Fix drift-guard false positive and mill-start missing task body/brief

```yaml
task: Fix drift-guard false positive and mill-start missing task body/brief
slug: mill-skill-and-tooling-gaps
approved: false
started: 20260630-044003
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: drift-guard-and-millstart-fix
    file: 01-drift-guard-and-millstart-fix.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-skill-helper-drift.py
```

## Shared Decisions

### Decision: single-batch coupling

- **Decision:** Both fixes (#576 drift-guard regex, #577 mill-start body/brief) live in one
  batch even though they are logically independent, because the test file's new Card 2
  regression lock asserts substrings of `mill-start/SKILL.md`. The SKILL edit (Card 1) and the
  lock that checks it (Card 3) must land together so the batch `verify:` is green.
- **Rationale:** Splitting would force an artificial dependency edge and leave the SKILL-only
  batch with no meaningful standalone verify (the SKILL is agent-consumed prose). One batch
  keeps the context to two edited files plus one read-only context file, well under limits.
- **Applies to:** all batches

### Decision: ASCII-only and no behaviour change to mill-go

- **Decision:** The `gate_cmd.lower()` line in `mill-go/SKILL.md:738` is a correct local
  variable and is NOT renamed; the bug is the test regex. Any printed/comment text added stays
  ASCII-only per CLAUDE.md.
- **Rationale:** The false positive is a test defect, not a SKILL defect; renaming `gate_cmd`
  would be out-of-scope churn. ASCII-only avoids the Windows cp1252 stdout crash.
- **Applies to:** all batches

## All Files Touched

- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/unit_tests/test-skill-helper-drift.py`
