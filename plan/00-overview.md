# Plan: 2 — Enforce uv run in .millhouse shortcut wrappers

```yaml
task: 2 — Enforce uv run in .millhouse shortcut wrappers
slug: uv-wrapper-enforce
approved: true
started: 20260505-121228
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - name: unit-and-docs
    file: 01-unit-and-docs.md
    depends-on: []
    verify: python plugins/mill/unit_tests/run-all.py
  - name: integration-test
    file: 02-integration-test.md
    depends-on: [unit-and-docs]
    verify: pwsh plugins/mill/integration_tests/test-bootstrap.ps1
```

## Shared Decisions

### Decision: no production code changes

- **Decision:** All production code (`_shortcuts.py`, `shortcut-wrapper.ps1`) is already correct on `main`. This plan touches only tests and documentation.
- **Rationale:** The core fix landed in commit `66e556f`. Unnecessary changes to production code would add merge risk with no benefit.
- **Applies to:** all batches

### Decision: integration test follows existing PYTHONPATH convention

- **Decision:** The Phase 4.7 block in `test-bootstrap.ps1` uses `uv run --project $millRoot python -c "..."` without setting PYTHONPATH inline, matching Phases 4 and 6a already in the file.
- **Rationale:** The existing integration test already relies on PYTHONPATH being set in the developer's environment (by mill-setup Phase 4.7). Deviating from that convention inside the same file would be inconsistent.
- **Applies to:** integration-test

### Decision: split verify by runner type

- **Decision:** The unit-test batch verifies with the Python runner; the integration-test batch verifies with `pwsh`. Each batch verify covers only the code changes in that batch.
- **Rationale:** `test-bootstrap.ps1` requires git, PYTHONPATH, and a real developer environment — it cannot be included in the unit-test runner. Separating them gives each batch an honest, executable verify command.
- **Applies to:** unit-and-docs, integration-test

## All Files Touched

- `plugins/mill/integration_tests/test-bootstrap.ps1`
- `plugins/mill/skills/mill-setup/SKILL.md`
- `plugins/mill/unit_tests/test-shortcut-wrapper.py`
