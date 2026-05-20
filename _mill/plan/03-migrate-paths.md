# Batch: migrate _paths.py

```yaml
task: Replace git subprocess calls with pygit2
batch: migrate _paths.py
number: 3
cards: 4
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

### Card 7: Update test-paths.py mock tests to work without _subprocess_util

- **Context:**
  - `plugins/mill/scripts/_pygit2_util.py`
  - `plugins/mill/unit_tests/_test_helpers.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-paths.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  After migration, `_paths.py` no longer calls `_subprocess_util.run`. The following tests in `test-paths.py` patch `_subprocess_util.run` and will silently NOT intercept the new `_pygit2_util` calls. Each must be rewritten as described:

  **`resolve_main_worktree_root` tests (lines ~373–420):** Replace all four `patch("_subprocess_util.run", ...)` test blocks with real-git-repo equivalents:
  - Container-form test: call `_paths.resolve_main_worktree_root(real_repo_root)` on an inited git repo; assert result equals the repo root.
  - Worktree-form test: create a real `git worktree add` linked worktree via subprocess; call `_paths.resolve_main_worktree_root(linked_worktree_path)`; assert result equals the main repo root.
  - Error test (returncode=1): pass a non-repo directory path to `_paths.resolve_main_worktree_root`; assert `SystemExit` is raised.
  - CRLF/whitespace test: the old test checked subprocess output stripping, which is no longer relevant; replace with a test that calls from a real repo and verifies idempotency (call twice, same result).

  **`resolve_git_root` wiki-guard tests (lines ~730–780):** These patch `_subprocess_util.run` to return a fake path. Replace with real-git-repo + `_pygit2_util.discover_workdir` mocking:
  - Case 1 (name check `"wiki"`): create a real git repo in a temp dir; rename or create a subdirectory named `"wiki"` inside it; mock `_pygit2_util.discover_workdir` to return `Path(tmp) / "wiki"`; assert `SystemExit("cwd is inside wiki")`.
  - Case 2 (path-equality guard): create a real git repo; mock `_pygit2_util.discover_workdir` to return `tmp_path` and mock `_paths.resolve_wiki_path` to return `tmp_path`; assert `SystemExit`.
  - Case 3 (falls through): mock `_pygit2_util.discover_workdir` to return `tmp_path` and `_paths.resolve_wiki_path` to return `other_path`; assert `resolve_git_root()` returns `tmp_path`.
  - Case 4 (name check before nested-halt): mock `_pygit2_util.discover_workdir` to return a non-"wiki" path and a "wiki"-named path; assert behaviours as in original.

  **`resolve_git_root` no-args test (lines ~817–829):** The test checks that git was called without `-C`. After migration, subprocess is not called at all. Replace with: mock `_pygit2_util.discover_workdir` and assert it is called with `None` (the no-args path); verify no `-C` check is needed since it's now an API parameter, not an argv flag.

  **Imports:** add `from unittest.mock import patch` import for mocking `_pygit2_util.discover_workdir` where needed. Remove usage of `_make_run_result` for the rewritten tests (keep the helper if other tests still use it). Remove `import _subprocess_util` from `test-paths.py` if no longer used after these rewrites.

- **Commit:** `test(_paths): update test-paths.py mock tests for pygit2 migration`

## Batch Tests

Batch verify runs `test-paths.py` and `test-paths-status.py`. All tests must pass with zero `FAIL` or `AssertionError` output. `test-paths-status.py` tests downstream path helpers that depend on these functions.
