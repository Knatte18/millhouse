# Plan: millpy-implement/bg: Windows baseline-worktree teardown (WinError 145) and stale liveness reporting

```yaml
task: 'millpy-implement/bg: Windows baseline-worktree teardown (WinError 145) and stale liveness reporting'
slug: mill-go-windows-baseline-teardown-and-bg-liveness
approved: false
started: 20260904-083401
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: worktree-teardown-retry
    file: 01-worktree-teardown-retry.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-worktree.py
  - number: 2
    name: cleanup-orphan-baseline-sweep
    file: 02-cleanup-orphan-baseline-sweep.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-cleanup.py
  - number: 3
    name: bg-liveness-windows-probe
    file: 03-bg-liveness-windows-probe.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-bg-liveness.py
  - number: 4
    name: baseline-undercount-corroboration
    file: 04-baseline-undercount-corroboration.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-millpy-implement.py
```

## Shared Decisions

### Decision: three independent Windows-only bug fixes, no shared files

- **Decision:** This plan fixes three unrelated (co-reported) Windows-only bugs — worktree teardown lock (batches 1-2), bg-liveness false-dead reporting (batch 3), and per-batch baseline undercount (batch 4). No two batches edit the same file, so all four are root batches (`depends-on: []`) with no DAG ordering constraint between them.
- **Rationale:** `_mill/discussion.md`'s Scope section explicitly separates these into three sub-bugs with independent Decisions sections; the Technical Context confirms each touches a distinct file set (`_worktree.py` / `millpy-cleanup.py` / `_bg.py` / `_implementer_common.py`+`millpy-implement.py`).
- **Applies to:** all batches.

### Decision: no live Windows reproduction — all fixes validated via mocked/injected-boundary unit tests

- **Decision:** Every Windows-only code path (WinError145 retry, `ctypes.windll` liveness probe, the `dotnet build-server shutdown` call) is exercised in tests via mocking/monkeypatching (`unittest.mock`, `sys.platform` patched where needed), never a real Windows process or a real `dotnet`/`ctypes.windll` call. This dev environment is Linux; no Windows CI is available.
- **Rationale:** `_mill/discussion.md`'s `## Testing` section and Q&A log — matches the existing project convention (in-memory/tempfile fixtures, no real git/LLM/Windows dependency) already used throughout `plugins/mill/unit_tests/`.
- **Applies to:** all batches.

### Decision: `pipeline.done_gate` stays `null` — pre-existing repo-wide `ruff check .` debt

- **Decision:** Leave `mill-config.yaml`'s `pipeline.done_gate: null` unchanged; do not default it to a lint command as part of this task.
- **Rationale:** Per the mill-plan "Done-gate reminder", `uvx ruff check .` was run from `git_root` against the current worktree tip before planning and found 1942 pre-existing findings (613 auto-fixable) unrelated to this task's scope — it does not exit 0. Defaulting `done_gate` to it would make every future task in this hub depend on unrelated pre-existing lint debt being fixed first.
- **Applies to:** all batches (no batch sets `pipeline.done_gate`).

## All Files Touched

- `plugins/mill/scripts/_bg.py`
- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/scripts/_worktree.py`
- `plugins/mill/scripts/millpy-cleanup.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/unit_tests/test-bg-liveness.py`
- `plugins/mill/unit_tests/test-cleanup.py`
- `plugins/mill/unit_tests/test-implementer-common.py`
- `plugins/mill/unit_tests/test-worktree.py`
