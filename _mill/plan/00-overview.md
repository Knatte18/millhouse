# Plan: Fix agent error recovery, implementer/review false-success contracts, VS Code watcher, and plan-validator Deletes

```yaml
task: "Fix agent error recovery, implementer/review false-success contracts, VS Code watcher, and plan-validator Deletes"
slug: "mill-agent-and-implement-contracts"
approved: false
started: "20260618-091402"
parent: "main"
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to
schedule batches. Every batch lives at `NN-<batch-slug>.md` in this
directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: plan-validate-deletes
    file: 01-plan-validate-deletes.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py
  - number: 2
    name: vscode-watcher-exclude
    file: 02-vscode-watcher-exclude.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-vscode.py
  - number: 3
    name: review-discussion-nitcount
    file: 03-review-discussion-nitcount.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-review-discussion-flow.py
  - number: 4
    name: holistic-fix-sweep
    file: 04-holistic-fix-sweep.md
    depends-on: []
    verify: null
  - number: 5
    name: implementer-contracts
    file: 05-implementer-contracts.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-implementer-common.py
```

## Shared Decisions

_Cross-cutting decisions every batch inherits._

### Decision: scope is bug-fix-per-issue, no refactors

- **Decision:** Each batch fixes exactly one GitHub issue (or, for batch 5, two issues that share a source file). No drive-by refactors, no behaviour changes beyond what the issue names.
- **Rationale:** The seven issues are independent plumbing defects with precise fix sites identified in `_mill/discussion.md`. Keeping batches issue-scoped keeps review tight and lets the DAG run fully parallel.
- **Applies to:** all batches

### Decision: cited line numbers are approximate

- **Decision:** All line numbers referenced in card Requirements are approximate (captured during exploration). The implementer locates edit points by symbol/function/section name, never by raw line number.
- **Rationale:** Files drift; the discussion review flagged this explicitly. Stable identifiers (function names, the exact section heading, the exact existing string) are authoritative.
- **Applies to:** all batches

### Decision: TDD where a test surface exists

- **Decision:** For every batch with a runnable `verify:`, add the regression test in the same card as the code change. The test must fail before the fix and pass after. Batch 4 is doc-only (no test surface).
- **Rationale:** Each issue identified a specific test gap; the test is what proves the fix and guards against regression.
- **Applies to:** batches 1, 2, 3, 5

### Decision: ASCII-only stdout, mill script-invocation conventions

- **Decision:** Any new `print()`/log strings stay ASCII (no em-dash, no arrows). New emitted JSON keys follow existing shapes in the same file.
- **Rationale:** Repo convention (Windows cp1252 stdout); consistency with surrounding code.
- **Applies to:** all batches

## All Files Touched

- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/scripts/_plan_validate.py`
- `plugins/mill/scripts/_review_discussion.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/templates/fixer-holistic-brief.md`
- `plugins/mill/templates/implementer-brief.md`
- `plugins/mill/templates/vscode-settings.json`
- `plugins/mill/unit_tests/test-implementer-common.py`
- `plugins/mill/unit_tests/test-plan-validate.py`
- `plugins/mill/unit_tests/test-review-discussion-flow.py`
- `plugins/mill/unit_tests/test-vscode.py`
