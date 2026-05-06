# Plan: 23 (A) — mill infra bugfix-batch

```yaml
task: 23 (A) — mill infra bugfix-batch
slug: mill-infra-bugfix-batch
approved: true
started: 20260506-165947
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - name: 01-bugfix-batch
    file: 01-bugfix-batch.md
    depends-on: []
    verify: 'uv run --project "${CLAUDE_PLUGIN_ROOT}" python "${CLAUDE_PLUGIN_ROOT}/unit_tests/run-all.py"'
```

## Shared Decisions

### Decision: no-new-abstractions

- **Decision:** Only add what is needed to fix bugs B, C, and D. No refactoring of adjacent code or callers not directly involved.
- **Rationale:** Minimal diff reduces regression risk and keeps the review surface small.
- **Applies to:** all batches

### Decision: test-in-existing-files

- **Decision:** All new tests go into the existing test files (`test-status.py`, `test-millpy-implement.py`, `test-millpy-bg.py`) using the established sequential-letter pattern.
- **Rationale:** Consistent with the existing test infrastructure; no new test runner entries needed.
- **Applies to:** all batches

## All Files Touched

- `plugins/mill/scripts/_status.py`
- `plugins/mill/scripts/millpy-bg.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/unit_tests/test-millpy-bg.py`
- `plugins/mill/unit_tests/test-millpy-implement.py`
- `plugins/mill/unit_tests/test-status.py`
