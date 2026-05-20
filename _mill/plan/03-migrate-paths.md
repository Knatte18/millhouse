# Batch: migrate _paths.py

```yaml
task: Replace git subprocess calls with pygit2
batch: migrate _paths.py
number: 3
cards: 3
verify: "uv run --project plugins/mill python plugins/mill/unit_tests/test-paths.py && uv run --project plugins/mill python plugins/mill/unit_tests/test-paths-status.py"
depends-on: [1]
```

## Batch Scope

Replaces the three subprocess git calls in `_paths.py` with `_pygit2_util` helpers. All three call sites are in separate functions: `resolve_git_root`, `resolve_main_worktree_root`, and `resolve_active_worktree`. After all three replacements, the `import _subprocess_util` line at `_paths.py:91` is removed. No other files are touched.

## Cards

### Card 4: Replace resolve_git_root() subprocess call

- **Context:**
  - `plugins/mill/scripts/_pygit2_util.py`
- **Edits:**
  - `plugins/mill/scripts/_paths.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - In `_paths.py`, replace the body of `resolve_git_root(start: Path | None = None) -> Path` (currently at lines ~115-145).
  - New implementation:
    1. Call `_pygit2_util.discover_workdir(start)` in a try/except. On `_pygit2_util.GitOpsError`, raise `SystemExit(f"Not in a git repository: {e}")` (same message shape as the existing code).
    2. Assign the result to `repo_root`.
    3. Preserve the existing wiki guard verbatim — both checks:
       - Fast name check: `if repo_root.name == "wiki": raise SystemExit(...)` using the existing message text.
       - Samefile check: the existing `try/except` block that calls `resolve_wiki_path` and compares with `samefile`.
    4. Return `repo_root`.
  - Remove `import _subprocess_util` from `_paths.py` only AFTER card 6 is complete (card 6 is the last subprocess call in this file). Do NOT remove it in this card.
  - Add `import _pygit2_util` at the import section of `_paths.py` (near the existing `import _subprocess_util` line).
- **Commit:** `refactor(_paths): replace resolve_git_root subprocess call with _pygit2_util`

### Card 5: Replace resolve_main_worktree_root() subprocess call

- **Context:**
  - `plugins/mill/scripts/_pygit2_util.py`
- **Edits:**
  - `plugins/mill/scripts/_paths.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - In `_paths.py`, replace the body of `resolve_main_worktree_root(git_root: Path) -> Path` (currently at lines ~153-181).
  - New implementation:
    1. Call `_pygit2_util.resolve_common_dir_parent(git_root)` in a try/except. On `_pygit2_util.GitOpsError`, raise `SystemExit(f"git rev-parse --git-common-dir failed for {git_root}: {e}")`.
    2. Return the result directly (it is already the main worktree root, equivalent to `common_dir.parent` in the old code).
  - The existing module docstring for `resolve_main_worktree_root` mentions `git rev-parse --git-common-dir` — update it to note the pygit2 implementation.
- **Commit:** `refactor(_paths): replace resolve_main_worktree_root subprocess call with _pygit2_util`

### Card 6: Replace resolve_active_worktree() branch call and remove _subprocess_util import

- **Context:**
  - `plugins/mill/scripts/_pygit2_util.py`
- **Edits:**
  - `plugins/mill/scripts/_paths.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - In `_paths.py`, find the subprocess call at ~line 341 inside `resolve_active_worktree`:
    ```python
    branch_result = _subprocess_util.run(
        ["git", "-C", str(worktree), "branch", "--show-current"]
    )
    branch = branch_result.stdout.strip()
    ```
  - Replace with:
    ```python
    try:
        branch = _pygit2_util.current_branch(worktree) or ""
    except _pygit2_util.GitOpsError:
        branch = ""
    ```
    The `or ""` converts `None` (detached HEAD) to `""`, which already falls through the existing `dir_slug != slug` check correctly.
  - After this replacement, `_subprocess_util` is no longer used anywhere in `_paths.py`. Remove the `import _subprocess_util` line from `_paths.py`.
- **Commit:** `refactor(_paths): replace resolve_active_worktree branch call with _pygit2_util; remove _subprocess_util import`

## Batch Tests

Batch verify runs `test-paths.py` and `test-paths-status.py`. `test-paths.py` tests `resolve_git_root`, `resolve_main_worktree_root`, and `resolve_active_worktree` using real git repos. `test-paths-status.py` tests downstream path helpers that depend on these functions.
