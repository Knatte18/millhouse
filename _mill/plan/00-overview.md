# Plan: mill-go verify/cleanup gates misclassify build-tag deletions and round-suffixed phases

```yaml
task: "mill-go verify/cleanup gates misclassify build-tag deletions and round-suffixed phases"
slug: mill-go-verify-gate-misclassification
approved: false
started: "20260727-173358"
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: go-build-tag-directory-deletion-guard
    file: 01-go-build-tag-directory-deletion-guard.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-implementer-common.py
  - number: 2
    name: cleanup-live-phase-classification
    file: 02-cleanup-live-phase-classification.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-cleanup.py
```

## Shared Decisions

### Decision: Independent, unrelated fixes stay in separate batches

- **Decision:** Bug 1 (go-build-tag-retiering directory-deletion guard) and Bug 2
  (millpy-cleanup live-phase classification) touch entirely different
  files and subsystems with zero shared `Context:`. They are two root
  batches (`depends-on: []`) with no ordering constraint between them.
- **Rationale:** Per mill-plan's batch-sizing rule, batches that share
  <80% of their `Context:` should not be merged. These two share none.
- **Applies to:** all batches

### Decision: Match each file's existing test convention exactly

- **Decision:** Batch 1's new test cases follow
  `test-implementer-common.py`'s existing "Case NN" convention — real git
  fixtures, per-case `try/except Exception` incrementing a local `errors`
  counter, `PASS`/`FAIL` printed to stdout/stderr. Batch 2's new tests
  follow `test-cleanup.py`'s existing pattern of a standalone
  `def test_<name>() -> None` function (see `test_scan_orphan_portals`)
  using plain `assert` statements, explicitly called from within `main()`.
  Do not introduce pytest or any new test-running convention into either
  file.
- **Rationale:** Both files are large (4000+ / 1700+ lines) with one
  established internal convention each; introducing a second convention
  in the same file fragments maintenance for no benefit.
- **Applies to:** all batches

## All Files Touched

- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/scripts/millpy-cleanup.py`
- `plugins/mill/unit_tests/test-cleanup.py`
- `plugins/mill/unit_tests/test-implementer-common.py`
