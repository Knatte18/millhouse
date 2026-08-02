# Plan: Verify/build gates leak shell state and ignore nested Go modules

```yaml
task: Verify/build gates leak shell state and ignore nested Go modules
slug: mill-verify-gate-scoping-bugs
approved: false
started: 20260802-101909
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
    name: bug1-holistic-verify-subshell-wrap
    file: 01-bug1-holistic-verify-subshell-wrap.md
    depends-on: []
    verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-fix.py"
  - number: 2
    name: bug2-nested-go-module-cwd
    file: 02-bug2-nested-go-module-cwd.md
    depends-on: []
    verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-implementer-common.py"
```

## Shared Decisions

### Decision: no-subprocess-real-go-toolchain

- **Decision:** neither fix's tests shell out to a real Go toolchain. Bug 1's `_resolve_holistic_verify` is a pure string-join function tested directly. Bug 2's tests continue mocking `go`-prefixed `_subprocess_util.run` calls (existing `_go_gate_mock` convention) while using real git/filesystem for fixture setup.
- **Rationale:** matches existing test infrastructure in both files; avoids adding a Go-toolchain dependency to the unit test suite.
- **Applies to:** all batches

### Decision: byte-identical-fallback

- **Decision:** bug 2's nested-module-detection fix must reproduce today's exact `cwd=project_root`, pattern `./<dir_str>/...` behavior whenever no nested `go.mod` is found strictly between the affected directory and `project_root` (inclusive of `project_root` itself as the final fallback).
- **Rationale:** the overwhelmingly common case is a single-module repo; the fix must not alter behavior for it. Fails open rather than skipping the compile check.
- **Applies to:** bug2-nested-go-module-cwd

## All Files Touched

- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/scripts/millpy-fix.py`
- `plugins/mill/unit_tests/test-implementer-common.py`
- `plugins/mill/unit_tests/test-millpy-fix.py`
