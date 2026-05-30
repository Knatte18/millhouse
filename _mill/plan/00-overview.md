# Plan: Wiki-daemon + bg-worker + test-suite robustness on Windows

```yaml
task: Wiki-daemon + bg-worker + test-suite robustness on Windows
slug: infra-robustness-windows
approved: false
started: 20260530-145439
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: wiki-client-robustness
    file: 01-wiki-client-robustness.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-wiki-daemon.py
  - number: 2
    name: bg-worker-liveness
    file: 02-bg-worker-liveness.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-bg-liveness.py
  - number: 3
    name: orchestrator-integration
    file: 03-orchestrator-integration.md
    depends-on: [2]
    verify: null
```

## Shared Decisions

### Decision: ascii-only-stdout

- **Decision:** Any `print()` / `_log()` / log-sentinel string added or changed
  in this task is ASCII only — render `—` as ` -- ` and `->` as ` -> `.
- **Rationale:** Windows cp1252 stdout crashes on non-ASCII bytes; this is a
  standing repo constraint and these fixes all run on the Windows path.
- **Applies to:** all batches.

### Decision: test-invocation

- **Decision:** Unit tests run via
  `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only <file.py>`.
  The leading empty `PYTHONPATH=` scopes the reset so the subprocess loads
  worktree modules, not the mill cache. Tests stay in-process
  (`WIKI_DAEMON_INPROCESS=1` is already set by the test files / `_test_helpers`);
  no test spawns a real daemon or real process.
- **Rationale:** Matches the `verify-not-isolated` validator rule and the
  existing suite's in-process posture; `run-all.py --only` is robust to each
  file's `__main__` convention (`test-wiki-daemon.py` uses `main()`,
  `test-bg-liveness.py` uses `unittest.main()`).
- **Applies to:** wiki-client-robustness, bg-worker-liveness.

### Decision: wikibusyerror-propagates

- **Decision:** `WikiBusyError(WikiError)` is the canonical "daemon busy after
  retries" signal. The internal retry absorbs the transient window; callers
  (skills) let `WikiBusyError` propagate unchanged. No per-callsite retry is
  added anywhere in this task.
- **Rationale:** Distinguishes "daemon busy" from "daemon dead" without adding
  retry surface the internal loop already covers (YAGNI per discussion).
- **Applies to:** wiki-client-robustness, orchestrator-integration.

### Decision: catch-broaden-minimally

- **Decision:** When widening an `except` to stop an escaping exception, name
  the specific classes proven to escape (`OSError, SystemError`) — never a bare
  `except Exception`. `KeyboardInterrupt` / `SystemExit` must remain
  un-swallowed (neither subclasses `OSError`/`SystemError`).
- **Rationale:** Smallest correct widening; keeps interrupt/exit semantics.
- **Applies to:** bg-worker-liveness.

### Decision: infrastructure-stuck-is-orchestrator-inferred

- **Decision:** `stuck_type: infrastructure` is inferred by the orchestrator
  (mill-go) from a `("dead", pid)` return of the single-shot `_bg.check_bg_status`
  helper (called once per incremental poll iteration; never a blocking wait) —
  it is NOT emitted by any CLI. Recovery is a plain **fresh re-fire** of the CLI (no
  `--resume`; the killed session is dead, matching the existing `running`-state
  Resume). mill-start, being always-interactive, surfaces an error and halts
  instead of inferring a stuck_type.
- **Rationale:** No CLI emits this; `millpy-implement.py` has no resume flag
  (`resume=False` at `:186`). Keeps recovery consistent with documented design.
- **Applies to:** orchestrator-integration.

## All Files Touched

- `plugins/mill/scripts/_bg.py`
- `plugins/mill/scripts/wiki/__init__.py`
- `plugins/mill/scripts/wiki/_client.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/unit_tests/test-bg-liveness.py`
- `plugins/mill/unit_tests/test-wiki-daemon.py`
