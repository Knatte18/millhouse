# Plan: Fix unit test suite failures, spurious review warning, and implementer verify-gate gaps

```yaml
task: Fix unit test suite failures, spurious review warning, and implementer verify-gate gaps
slug: mill-test-and-implementer-reliability
approved: false
started: 20260616-123346
parent: main
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
    name: review-common-fixes
    file: 01-review-common-fixes.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common-guard.py test-review-common.py
  - number: 2
    name: ascii-arrow-fix
    file: 02-ascii-arrow-fix.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-guards.py test-claude-sub.py
  - number: 3
    name: implementer-verify-gate
    file: 03-implementer-verify-gate.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-millpy-implement.py test-millpy-fix.py
  - number: 4
    name: implementer-guardrail
    file: 04-implementer-guardrail.md
    depends-on: [2]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-guards.py
```

## Shared Decisions

_Cross-cutting decisions every batch inherits._

### Decision: ASCII-only in code and test files

- **Decision:** No non-ASCII characters in any `.py` source or test file. Use `->` for arrows and ` -- ` for em-dashes in `print()`/`_log()`/comments.
- **Rationale:** Windows cp1252 consoles crash on non-ASCII stdout; `test-guards.py` enforces this for `test-*.py`. Batch 02 is itself a fix for a violation — do not reintroduce any non-ASCII.
- **Applies to:** all batches

### Decision: verify command isolation prefix

- **Decision:** Every non-null per-batch `verify:` starts with the literal `PYTHONPATH=` (empty value, single space) and scopes the test run with `run-all.py --only <files>`.
- **Rationale:** The empty `PYTHONPATH` reset stops the test subprocess inheriting the mill cache scripts dir, so tests load worktree modules, not stale cache modules. `--only` keeps each batch's verify scoped to the tests it affects (the full suite is multiple minutes).
- **Applies to:** all batches

### Decision: backward-compatible signature changes

- **Decision:** New parameters added to existing helpers (e.g. `verify_cmd` on `finalize_from_output` / `_forward_output`) default to `None` so existing callsites and tests keep working unchanged.
- **Rationale:** Lets a card add a parameter before its callsite is updated, and keeps the pre-existing `test-implementer-common.py` cases green without edits.
- **Applies to:** implementer-verify-gate

### Decision: test integrity (no weakening to go green)

- **Decision:** Implementers must never relax, exclude, downgrade, or delete test assertions to make `verify:` pass. This task both documents that rule (batch 04) and must itself honour it: fix code/tests properly, never gut coverage.
- **Rationale:** Directly the subject of issue #492; a weakened test is worse than a failing one because it hides the regression.
- **Applies to:** all batches

## All Files Touched

_Full union of every `Creates:` / `Edits:` across every batch, sorted alphabetically._

- `plugins/mill/agents/mill-implementer.md`
- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/scripts/millpy-fix.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/templates/implementer-brief.md`
- `plugins/mill/unit_tests/test-claude-sub.py`
- `plugins/mill/unit_tests/test-guards.py`
- `plugins/mill/unit_tests/test-implementer-common.py`
- `plugins/mill/unit_tests/test-millpy-implement.py`
- `plugins/mill/unit_tests/test-review-common.py`
