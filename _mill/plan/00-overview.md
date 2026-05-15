# Plan: 52 (A) -- Fix unit_tests/run-all destroying wiki during batch verify

```yaml
task: 52 (A) -- Fix unit_tests/run-all destroying wiki during batch verify
slug: run-all-wiki-wipe-fix
approved: false
started: 20260515-075450
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: test-infra
    file: 01-test-infra.md
    depends-on: []
    verify: python plugins/mill/unit_tests/run-all.py
  - number: 2
    name: test-migration
    file: 02-test-migration.md
    depends-on: [1]
    verify: python plugins/mill/unit_tests/run-all.py
```

## Shared Decisions

### Decision: safe-temp-dir-yields-path

- **Decision:** `safe_temp_dir()` yields `Path`, not `str`.
- **Rationale:** All test files use `Path` throughout. Yielding `Path` lets callers do `tmp / "subdir"` directly. Yielding `str` would require every caller to wrap in `Path()`.
- **Applies to:** all batches

### Decision: safe-rmtree-ignore-errors

- **Decision:** `safe_rmtree` called from `safe_temp_dir()` uses `ignore_errors=True`.
- **Rationale:** Test cleanup failures must not mask the actual test result. This matches Python 3.10+ `TemporaryDirectory(ignore_cleanup_errors=True)` convention.
- **Applies to:** batch 1 (test-infra)

### Decision: test-spawn-core-scope

- **Decision:** Replace `TemporaryDirectory` with `safe_temp_dir()` only in the 2 junction-creating tests in `test-spawn-core.py`.
- **Rationale:** Only `test_recreate_active_junction_creates_link` and `test_recreate_active_junction_idempotent` call `recreate_active_junction` which creates a real NTFS junction. The other 10 tests in the file do not create junctions; `TemporaryDirectory` remains correct for them.
- **Applies to:** batch 2 (test-migration)

## All Files Touched

- `plugins/mill/unit_tests/_test_helpers.py`
- `plugins/mill/unit_tests/run-all.py`
- `plugins/mill/unit_tests/test-setup-hub-links.py`
- `plugins/mill/unit_tests/test-spawn-core.py`
