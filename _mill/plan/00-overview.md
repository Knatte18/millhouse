# Plan: 56 (A) -- Fix mill-go/start/plan/merge runtime behavioral bugs

```yaml
task: 56 (A) -- Fix mill-go/start/plan/merge runtime behavioral bugs
slug: mill-go-runtime-bugs
approved: true
started: 20260515-074657
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: python-fixes
    file: 01-python-fixes.md
    depends-on: []
    verify: uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py

  - number: 2
    name: templates
    file: 02-templates.md
    depends-on: []
    verify: uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py

  - number: 3
    name: mill-go-skill
    file: 03-mill-go-skill.md
    depends-on: []
    verify: uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py

  - number: 4
    name: other-skills
    file: 04-other-skills.md
    depends-on: []
    verify: uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
```

## Shared Decisions

### Decision: no-new-python-modules

- **Decision:** All Python changes go into existing files only. No new `.py` script files are added; unit test additions go into existing `test-paths.py` and `test-implementer-common.py`.
- **Rationale:** Each bug is a targeted fix to a named function. New modules would add import surface without benefit.
- **Applies to:** all batches

### Decision: ascii-print-only

- **Decision:** All new `print()` / `_log()` strings in Python code use ASCII characters only. Em-dash becomes ` -- `, arrow becomes ` -> `.
- **Rationale:** Windows cp1252 terminals crash on non-ASCII stdout/stderr (CLAUDE.md invariant).
- **Applies to:** batch 1

### Decision: skill-prose-style

- **Decision:** SKILL.md edits follow the existing prose style of each skill file — no reformatting of surrounding text, no added blank lines beyond what the surrounding block uses.
- **Rationale:** Minimises reviewer noise; keeps diffs surgical.
- **Applies to:** batches 3, 4

### Decision: verify-is-regression-check

- **Decision:** All four batches use `uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py` as their verify command. For batches 2–4 (template/SKILL.md changes), this is a regression check only — the unit tests do not exercise templates or SKILL.md prose.
- **Rationale:** A single consistent verify command ensures nothing in the Python layer is broken by any batch.
- **Applies to:** all batches

## All Files Touched

- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/scripts/_paths.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-merge-in/SKILL.md`
- `plugins/mill/skills/mill-merge/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/templates/implementer-brief.md`
- `plugins/mill/templates/review-code-holistic.md`
- `plugins/mill/unit_tests/test-implementer-common.py`
- `plugins/mill/unit_tests/test-paths.py`
