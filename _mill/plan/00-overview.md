# Plan: Replace git subprocess calls with pygit2

```yaml
task: Replace git subprocess calls with pygit2
slug: pygit2-git-ops
approved: false
started: 20260520-102836
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: _pygit2_util foundation
    file: 01-pygit2-util-foundation.md
    depends-on: []
    verify: "uv run --project plugins/mill python -c \"import sys; sys.path.insert(0, 'plugins/mill/scripts'); import _pygit2_util; print('ok')\""
  - number: 2
    name: unit tests
    file: 02-unit-tests.md
    depends-on: [1]
    verify: "uv run --project plugins/mill python plugins/mill/unit_tests/test-pygit2-util.py"
  - number: 3
    name: migrate _paths.py
    file: 03-migrate-paths.md
    depends-on: [1]
    verify: "uv run --project plugins/mill python plugins/mill/unit_tests/test-paths.py && uv run --project plugins/mill python plugins/mill/unit_tests/test-paths-status.py"
  - number: 4
    name: migrate _marker.py and _worktree.list_worktrees
    file: 04-migrate-marker-worktree.md
    depends-on: [1]
    verify: "uv run --project plugins/mill python plugins/mill/unit_tests/test-marker.py && uv run --project plugins/mill python plugins/mill/unit_tests/test-worktree.py"
  - number: 5
    name: migrate _cleanliness.py and _review_common.py
    file: 05-migrate-cleanliness-review.md
    depends-on: [1]
    verify: "uv run --project plugins/mill python plugins/mill/unit_tests/test-cleanliness.py && uv run --project plugins/mill python plugins/mill/unit_tests/test-review-common-guard.py"
```

## Shared Decisions

### Decision: GitOpsError exception type

- **Decision:** `_pygit2_util.py` raises `GitOpsError(RuntimeError)` on all failures. Callers re-raise as the error type their layer expects (`SystemExit` in `_paths.py`, `MarkerError` in `_marker.py`, `ReviewError` in `_review_common.py`, `WorktreeError` in `_worktree.py`). `_cleanliness.py` lets `GitOpsError` propagate uncaught (callers check for `SystemExit`; `GitOpsError` is a subclass of `Exception` so it propagates up to the script entry point).
- **Rationale:** `GitOpsError(RuntimeError)` is catchable with `except Exception:` (unlike `SystemExit`). Each module maps it to its own exception type, preserving existing caller contracts.
- **Applies to:** all batches

### Decision: no fallback to subprocess

- **Decision:** No fallback: if `_pygit2_util` raises `GitOpsError`, callers re-raise their layer's exception immediately. There is no "try pygit2, fall back to subprocess" pattern.
- **Rationale:** pygit2 is an explicit dependency; fallback would hide failures and add complexity. If pygit2 is absent, `import _pygit2_util` fails at module load, not silently at call time.
- **Applies to:** all batches

### Decision: remove unused _subprocess_util imports

- **Decision:** After replacing all subprocess calls in a module, remove `import _subprocess_util` from that module if no other calls remain. `_review_common.py` and `_worktree.py` keep the import (they still use it for `git diff` and write operations respectively).
- **Rationale:** Dead imports mislead readers into thinking subprocess is still used.
- **Applies to:** batches 3, 4, 5

### Decision: porcelain string compatibility

- **Decision:** `status_porcelain()` returns `list[str]` in porcelain v1 format (`XY path`). Callers in `_cleanliness.py` and `_review_common.py` are unchanged.
- **Rationale:** Callers do line-set arithmetic on porcelain strings. Keeping the string format means zero changes to `_filter_porcelain`, `_porcelain_diff`, and `compute_new_dirt`.
- **Applies to:** batches 1, 5

## All Files Touched

- `plugins/mill/pyproject.toml`
- `plugins/mill/scripts/_cleanliness.py`
- `plugins/mill/scripts/_marker.py`
- `plugins/mill/scripts/_paths.py`
- `plugins/mill/scripts/_pygit2_util.py`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/scripts/_worktree.py`
- `plugins/mill/unit_tests/test-pygit2-util.py`
- `plugins/mill/uv.lock`
