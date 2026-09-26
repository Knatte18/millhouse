# Plan: mill-merge: run the deterministic path as one script

```yaml
task: 'mill-merge: run the deterministic path as one script'
slug: mill-merge-script
approved: false
started: 20260926-140331
parent_branch: main
root: ""
verify: null
discussion_sha: 3bbe44d8d7105fe56b8eaa584945dff807c286be
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to schedule batches.
Every batch lives at `NN-<batch-slug>.md` in this directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: merge-core-entry
    file: 01-merge-core-entry.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-merge.py
  - number: 2
    name: merge-core-squash
    file: 02-merge-core-squash.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-merge.py
  - number: 3
    name: merge-cli
    file: 03-merge-cli.md
    depends-on: [2]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-merge.py test-millpy-merge.py
  - number: 4
    name: skill-rewrite
    file: 04-skill-rewrite.md
    depends-on: [3]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-guards.py
  - number: 5
    name: cross-references
    file: 05-cross-references.md
    depends-on: [4]
    verify: PYTHONPATH= uv run --project plugins/mill python -m py_compile plugins/mill/integration_tests/test-merge.py
```

## Shared Decisions

### Decision: module-layout

- **Decision:** `plugins/mill/scripts/_merge.py` holds all step logic, the `Ops` effect boundary, and the runner `run_merge`.
  `plugins/mill/scripts/millpy-merge.py` is a thin argparse CLI over `_merge.run_merge`.
  Unit tests for `_merge.py` live in `plugins/mill/unit_tests/test-merge.py` (the validator's convention-derived name for `_merge.py`);
  CLI tests live in `plugins/mill/unit_tests/test-millpy-merge.py`.
- **Rationale:** matches discussion Decision `script-shape` and the `millpy-spawn.py` / `_spawn_core.py` precedent.
- **Applies to:** all batches

### Decision: effect-boundary

- **Decision:** every external effect in `_merge.py` goes through one `Ops` instance: subprocess calls (`Ops.run`), path/config resolution, `_marker`, `_inplace`, `_parent_branch`, `_pr_state`, `_archive_tag`, `wiki._client`, `_notify`, the clock (`Ops.now`), and `Ops.pid`.
  `_status` reads/writes and lock-file I/O are NOT behind `Ops`: they operate on real files, which the tests place in a `tempfile.TemporaryDirectory()`.
  Tests subclass `Ops` as `FakeOps`, overriding methods with scripted return values and recording calls.
- **Rationale:** discussion Decision `testing-scope` (injectable boundary, in-memory/tempfile fixtures, no real git/gh/daemon).
- **Applies to:** all batches

### Decision: unit-tests-only

- **Decision:** no card adds a real-git or real-gh test of `_merge.run_merge` / `millpy-merge.py`;
  the existing `plugins/mill/integration_tests/test-merge.py` gets comment-only edits.
- **Rationale:** the discussion scopes this out explicitly (Scope "Out": new integration tests with real git/gh;
  Decision `testing-scope`, which rejects a real-git integration test because the PR-state gate needs `gh` and a fake `gh` shim outweighs the gain).
  Argv shapes are pinned by `FakeOps` call-recording assertions instead.
- **Applies to:** all batches

### Decision: stop-signalling

- **Decision:** steps signal a stop by raising `_merge.Stop` (an `Exception` subclass carrying `status`, `reason`, `action`, `resume`, `data`, `report`).
  The runner catches only `Stop`;
  any other exception propagates (the CLI then crashes with a traceback and no JSON, per discussion Decision `script-shape`).
  `_merge.Terminated` subclasses `BaseException` so no `except Exception` inside a helper can swallow a SIGTERM.
- **Rationale:** a raised stop unwinds through the Step 5 `try/finally` naturally, so rollback and lock release need one code path.
- **Applies to:** 01-merge-core-entry, 02-merge-core-squash

### Decision: ascii-output

- **Decision:** every string placed in `reason`, `report`, or `warnings` passes through `_merge._ascii`, which maps U+2014 to ` -- `, U+2192 to ` -> `, and any other non-ASCII character to `?`.
  Halt texts copied from the old `plugins/mill/skills/mill-merge/SKILL.md` are stored in source already ASCII-converted, so `_ascii` is a backstop, not the primary mechanism.
- **Rationale:** CLAUDE.md ASCII-only stdout rule (Windows cp1252).
- **Applies to:** all batches

### Decision: done-gate-recommendation

- **Decision:** recommendation for the operator: `pipeline.done_gate: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py` (the currently effective value is `null`).
  A repo-wide `uvx ruff check .` was run against the current worktree tip and exits 1 with pre-existing lint debt unrelated to this task, so no lint command is recommended.
  Not applied: mill-go gates on the effective config value, not this Decision.
- **Rationale:** batch `verify:` scopes cover only the new test files and the guard test;
  a full unit run would catch regressions in tests that read skill text.
- **Applies to:** operator only

## All Files Touched

- `CLAUDE.md`
- `plugins/mill/integration_tests/test-merge.py`
- `plugins/mill/scripts/_merge.py`
- `plugins/mill/scripts/millpy-merge.py`
- `plugins/mill/skills/mill-go-base/SKILL.md`
- `plugins/mill/skills/mill-merge-in/SKILL.md`
- `plugins/mill/skills/mill-merge/SKILL.md`
- `plugins/mill/skills/mill-status/SKILL.md`
- `plugins/mill/unit_tests/test-merge.py`
- `plugins/mill/unit_tests/test-millpy-merge.py`
