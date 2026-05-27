# Plan: V3 wiki adoption follow-up bugs

```yaml
task: V3 wiki adoption follow-up bugs
slug: wiki-v3-followups
approved: false
started: 20260527-085619
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: wiki-daemon-fixes
    file: 01-wiki-daemon-fixes.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
  - number: 2
    name: junction-fs-scan
    file: 02-junction-fs-scan.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
  - number: 3
    name: safe-rmtree-chmod-retry
    file: 03-safe-rmtree-chmod-retry.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
  - number: 4
    name: millpy-fix-windows-lock
    file: 04-millpy-fix-windows-lock.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
```

## Shared Decisions

### Decision: ASCII-only stdout

- **Decision:** Any new `print()` / `_log()` output stays ASCII (no en-dash, no arrows `→`, no curly quotes).
- **Rationale:** Windows cp1252 crashes on non-ASCII stdout, per CLAUDE.md repo conventions.
- **Applies to:** all batches.

### Decision: One bug per commit

- **Decision:** Each card's Commit: message references the GitHub issue number it closes (e.g. `fix(wiki): ... (#382)`).
- **Rationale:** Matches the existing repo pattern; lets the team trace fixes to issues via git log.
- **Applies to:** all batches.

### Decision: Re-use existing test scaffolds, do not rewrite

- **Decision:** New test cases follow the existing `main() -> int` + `ok()` / `fail()` shape used by `test-wiki-daemon.py`, `test-wiki-protocol.py`, `test-safe-rmtree.py`. No `unittest.TestCase` migration. The `test-millpy-fix.py` exception keeps its existing `unittest` shape.
- **Rationale:** Consistency with surrounding code; `run-all.py` discovers any `test-*.py` and treats it as a subprocess returning 0/1.
- **Applies to:** all batches.

### Decision: Cross-batch test-file overlap handled by DAG

- **Decision:** Batch 3 depends on Batch 1 because both modify `test-wiki-daemon.py` (Batch 1 adds new test cases for #382; Batch 3 converts every `shutil.rmtree` call in the file, including the ones Batch 1 just added). Batch 1's new test cases use `shutil.rmtree(tmp, ignore_errors=True)` matching the existing file convention; Batch 3 converts them along with the rest.
- **Rationale:** Avoids parallel-modifies-overlap on `test-wiki-daemon.py`. Batches 2 and 4 touch disjoint files and remain parallel-eligible.
- **Applies to:** Batch 1, Batch 3.

## All Files Touched

- `plugins/mill/scripts/_junction.py`
- `plugins/mill/scripts/_safe_rmtree.py`
- `plugins/mill/scripts/millpy-fix.py`
- `plugins/mill/scripts/wiki/_client.py`
- `plugins/mill/scripts/wiki/_server.py`
- `plugins/mill/unit_tests/test-junction.py`
- `plugins/mill/unit_tests/test-millpy-fix.py`
- `plugins/mill/unit_tests/test-no-direct-rmtree.py`
- `plugins/mill/unit_tests/test-safe-rmtree.py`
- `plugins/mill/unit_tests/test-wiki-daemon.py`
- `plugins/mill/unit_tests/test-wiki-protocol.py`
- `plugins/mill/unit_tests/test-wiki-store.py`
- `plugins/mill/unit_tests/test-wiki-sync.py`
