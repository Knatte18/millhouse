# Plan: Fix wiki push upstream, cleanliness gate, mojibake, container config, and stacked-branch finalize

```yaml
task: "Fix wiki push upstream, cleanliness gate, mojibake, container config, and stacked-branch finalize"
slug: "mill-infra-and-path-fixes"
approved: false
started: "20260615-104327"
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
    name: review-warning-ascii
    file: 01-review-warning-ascii.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common.py
  - number: 2
    name: config-repo-layer
    file: 02-config-repo-layer.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-config.py
  - number: 3
    name: wiki-sync-robustness
    file: 03-wiki-sync-robustness.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-wiki-sync.py
  - number: 4
    name: terminal-cleanliness-gate
    file: 04-terminal-cleanliness-gate.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-cleanliness.py
  - number: 5
    name: stacked-finalize-cleanup
    file: 05-stacked-finalize-cleanup.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-finalize-cleanup.py
```

## Shared Decisions

_Cross-cutting decisions every batch inherits._

### Decision: six-independent-fixes

- **Decision:** Each of the six bundled GitHub issues is implemented as its own batch with no inter-batch dependencies (all `depends-on: []`). #469 and #462 are merged into a single batch (`wiki-sync-robustness`) because both edit `wiki/_sync.py`'s `commit_push`; keeping them separate would create a parallel-modifies-overlap on that file.
- **Rationale:** The fixes touch disjoint file sets and have no code coupling, so they parallelize cleanly. Merging only where a shared file forces it avoids overlap while preserving parallelism.
- **Applies to:** all batches

### Decision: ascii-console-output

- **Decision:** Any runtime `print(...)`/`_log(...)` output added or edited must be ASCII-only (`—` → ` -- `, `→` → ` -> `). Em dashes in docstrings/comments are left untouched.
- **Rationale:** Windows cp1252 stdout/stderr mojibakes or crashes on non-ASCII (CLAUDE.md invariant; the literal subject of #475).
- **Applies to:** all batches

### Decision: path-resolution-via-helpers

- **Decision:** All path resolution goes through `_paths.py` helpers (`resolve_main_worktree_root`, `resolve_container_path`, `resolve_task_path`). No hand-rolled `container / "wts" / slug` or `<wt> / hub_relative` joins.
- **Rationale:** Project path invariant (CLAUDE.md `## Path invariants`); the #470 fix in particular must use `resolve_main_worktree_root(worktree_root)` rather than reconstructing the clone path.
- **Applies to:** config-repo-layer, stacked-finalize-cleanup, terminal-cleanliness-gate

### Decision: test-tiering

- **Decision:** Tests extend the existing test files where one exists (`test-review-common.py`, `test-config.py`, `test-wiki-sync.py`, `test-cleanliness.py`) and add a new file only for genuinely new surface (`test-finalize-cleanup.py`). Tests that need real git use a tempfile bare-repo + clone (the established `test-wiki-sync.py` pattern) or mock `_pygit2_util.status_porcelain` (the `test-cleanliness.py` pattern). No real LLM, no network.
- **Rationale:** Matches the repo's existing test conventions and keeps `verify:` fast and deterministic.
- **Applies to:** all batches

## All Files Touched

- `plugins/mill/scripts/_cleanliness.py`
- `plugins/mill/scripts/_config.py`
- `plugins/mill/scripts/_finalize_cleanup.py`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/scripts/_setup.py`
- `plugins/mill/scripts/wiki/_sync.py`
- `plugins/mill/skills/git-pr/SKILL.md`
- `plugins/mill/skills/mill-finalize/SKILL.md`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/unit_tests/run-all.py`
- `plugins/mill/unit_tests/test-cleanliness.py`
- `plugins/mill/unit_tests/test-config.py`
- `plugins/mill/unit_tests/test-finalize-cleanup.py`
- `plugins/mill/unit_tests/test-review-common.py`
- `plugins/mill/unit_tests/test-wiki-sync.py`
