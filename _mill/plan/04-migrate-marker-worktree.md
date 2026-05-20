# Batch: migrate _marker.py and _worktree.list_worktrees

```yaml
task: Replace git subprocess calls with pygit2
batch: migrate _marker.py and _worktree.list_worktrees
number: 4
cards: 2
verify: "uv run --project plugins/mill python plugins/mill/unit_tests/test-marker.py && uv run --project plugins/mill python plugins/mill/unit_tests/test-worktree.py"
depends-on: [1]
```

## Batch Scope

Replaces the two subprocess calls in `_marker.py` (`slug_from_branch` and `task_data`) with `_pygit2_util.current_branch`, and replaces the subprocess call in `_worktree.list_worktrees` with `_pygit2_util.list_worktrees`. After migration, `import _subprocess_util` is removed from `_marker.py` (no remaining subprocess calls). `_worktree.py` keeps its `import _subprocess_util` because `create`, `remove`, and `prune` still use subprocess.

## Cards

### Card 7: Replace subprocess calls in _marker.py

- **Context:**
  - `plugins/mill/scripts/_pygit2_util.py`
- **Edits:**
  - `plugins/mill/scripts/_marker.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Add `import _pygit2_util` to `_marker.py` at the top alongside existing imports.

  - In `slug_from_branch(git_root, wiki_path, cfg)`: replace the block:
    ```python
    result = _subprocess_util.run(
        ["git", "-C", str(git_root), "branch", "--show-current"]
    )
    branch = result.stdout.strip()
    if not branch:
        raise MarkerError("detached HEAD or non-branch state")
    ```
    with:
    ```python
    try:
        branch = _pygit2_util.current_branch(git_root)
    except _pygit2_util.GitOpsError as e:
        raise MarkerError(f"could not read branch in {git_root}: {e}") from e
    if branch is None:
        raise MarkerError("detached HEAD or non-branch state")
    ```

  - In `task_data(git_root, wiki_path, cfg)`: replace the redundant subprocess call:
    ```python
    branch = _subprocess_util.run(
        ["git", "-C", str(git_root), "branch", "--show-current"]
    ).stdout.strip()
    ```
    with:
    ```python
    try:
        branch = _pygit2_util.current_branch(git_root) or ""
    except _pygit2_util.GitOpsError as e:
        raise MarkerError(f"could not read branch in {git_root}: {e}") from e
    ```

  - Remove `import _subprocess_util` from `_marker.py` (no remaining subprocess calls after these replacements).
- **Commit:** `refactor(_marker): replace subprocess branch calls with _pygit2_util; remove _subprocess_util import`

### Card 8: Replace list_worktrees() subprocess call in _worktree.py

- **Context:**
  - `plugins/mill/scripts/_pygit2_util.py`
- **Edits:**
  - `plugins/mill/scripts/_worktree.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Add `import _pygit2_util` to `_worktree.py` at the top alongside existing imports.

  - Replace the body of `list_worktrees(cwd: Path) -> list[dict[str, str | None]]` (currently at lines ~119-162) with:
    ```python
    try:
        return _pygit2_util.list_worktrees(cwd)
    except _pygit2_util.GitOpsError as e:
        raise WorktreeError(f"git worktree list failed (cwd={cwd}): {e}") from e
    ```
    The return type and dict shape `{"path": str, "branch": str | None}` are identical to the existing implementation so all callers are unchanged.

  - Keep `import _subprocess_util` in `_worktree.py` — `create`, `remove`, and `prune` still use subprocess.
- **Commit:** `refactor(_worktree): replace list_worktrees subprocess call with _pygit2_util`

## Batch Tests

Batch verify runs `test-marker.py` and `test-worktree.py`. `test-marker.py` covers `slug_from_branch` with real git repos (happy path, empty prefix, detached HEAD, prefix mismatch). `test-worktree.py` covers `list_worktrees` and the write operations that remain subprocess.
