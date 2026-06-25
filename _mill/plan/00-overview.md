# Plan: Fix pre-existing unit-test failures, CRLF cleanliness false-positive, and review false-BLOCKING on Go

```yaml
task: "Fix pre-existing unit-test failures, CRLF cleanliness false-positive, and review false-BLOCKING on Go"
slug: mill-unit-test-and-signal-accuracy
approved: true
started: "20260625-070133"
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: review-dispatch-fixes
    file: 01-review-dispatch-fixes.md
    depends-on: []
    verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-cli.py test-review-guard.py"
  - number: 2
    name: implementer-signal-fixes
    file: 02-implementer-signal-fixes.md
    depends-on: []
    verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-cleanliness.py test-implementer-common.py"
  - number: 3
    name: stale-test-corrections
    file: 03-stale-test-corrections.md
    depends-on: []
    verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-finalize.py test-agent-mode-dispatch.py"
```

## Shared Decisions

### Decision: prod-vs-test classification is fixed per finding

- **Decision:** Each of the six fixes is pre-classified as a production-code fix or a test-only fix (see batch scopes). Implementers MUST NOT "fix" the opposite side. Brief-path and overstep-guard are production bugs; CRLF and Go-markers are production bugs; the finalize-`--round` and dispatch-parity failures are stale-test / test-fixture issues whose production code is correct and untouched.
- **Rationale:** Root-causing during discussion established direction for each; reversing it would revert intentional prod behavior (e.g. commit `8a5fefac` auto-discovery) or mask a correct gate (the no-content-commit gate).
- **Applies to:** all batches

### Decision: Windows line-ending hygiene

- **Decision:** Do not introduce new `write_text` calls without `newline=""` for files that round-trip through git on Windows. Match-logic that inspects `git status`/`git diff` output must be CR-tolerant.
- **Rationale:** The CRLF false-positive originates exactly from text-mode CRLF translation plus CR-blind diffing.
- **Applies to:** implementer-signal-fixes

### Decision: test scoping with PYTHONPATH= prefix

- **Decision:** Every batch `verify:` uses `run-all.py --only <files>` with the literal `PYTHONPATH= ` prefix. No unbounded full-suite run per batch.
- **Rationale:** This is a Python/mill project; the prefix prevents the test subprocess from loading stale cache modules (CLAUDE.md `verify-not-isolated`). The whole-suite green check is the final mill-go/Handoff gate, not a per-batch verify.
- **Applies to:** all batches

## All Files Touched

- `plugins/mill/scripts/_cleanliness.py`
- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/scripts/millpy-review-code.py`
- `plugins/mill/scripts/millpy-review-discussion.py`
- `plugins/mill/scripts/millpy-review-plan.py`
- `plugins/mill/unit_tests/test-agent-mode-dispatch.py`
- `plugins/mill/unit_tests/test-cleanliness.py`
- `plugins/mill/unit_tests/test-implementer-common.py`
- `plugins/mill/unit_tests/test-review-cli.py`
- `plugins/mill/unit_tests/test-review-finalize.py`
