# Batch: unit tests

```yaml
task: Replace git subprocess calls with pygit2
batch: unit tests
number: 2
cards: 3
verify: "uv run --project plugins/mill python plugins/mill/unit_tests/test-pygit2-util.py"
depends-on: [1]
```

## Batch Scope

Creates `test-pygit2-util.py` with unit tests for every public function in `_pygit2_util.py`. Tests use real git repos created in `tempfile.TemporaryDirectory` via subprocess (fixture creation uses subprocess; the module under test uses pygit2). Covers happy paths, detached HEAD, linked worktrees, and porcelain edge cases. No existing test files are modified.

## Cards

### Card 3: Create test-pygit2-util.py

- **Context:**
  - `plugins/mill/scripts/_pygit2_util.py`
  - `plugins/mill/unit_tests/_test_helpers.py`
  - `plugins/mill/unit_tests/test-marker.py`
  - `plugins/mill/unit_tests/test-paths.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-pygit2-util.py`
- **Deletes:** none
- **Requirements:**
  - Use the same path-setup pattern as the existing unit tests: compute `_HERE`, `_SCRIPTS`, insert into `sys.path`, then import `_pygit2_util`.
  - All tests use `tempfile.TemporaryDirectory`. Fixture git repos are created via `subprocess.run(["git", "init", ...])`, `git config user.email/name`, and `git commit`.
  - Each test function prints `"PASS: <name>"` on success; raises `AssertionError` on failure. No pytest — same style as the existing unit tests.
  - A `run_all()` function at the bottom calls every test in sequence and prints a final summary.
  - Call `run_all()` under `if __name__ == "__main__":`.

  **`test_discover_workdir_happy_path()`:** init a real git repo in a tempdir, make a commit, call `_pygit2_util.discover_workdir(tmpdir)`, assert the result equals the tempdir path.

  **`test_discover_workdir_non_repo()`:** call `_pygit2_util.discover_workdir(Path(tmp) / "nonexistent")` inside a tempdir, assert `GitOpsError` is raised.

  **`test_resolve_common_dir_parent_main()`:** init a real git repo, make a commit, call `_pygit2_util.resolve_common_dir_parent(repo_path)`, assert it equals `repo_path`.

  **`test_resolve_common_dir_parent_linked()`:** init a real git repo, make a commit, run `git worktree add <linked_path> -b linked-branch` via subprocess, call `_pygit2_util.resolve_common_dir_parent(linked_path)`, assert it equals `repo_path`.

  **`test_head_sha_happy_path()`:** init a real git repo, make a commit, call `_pygit2_util.head_sha(repo_path)`, assert the result is a 40-char lowercase hex string and matches `git rev-parse HEAD` output.

  **`test_current_branch_named()`:** init a real git repo, make a commit on branch `main`, call `_pygit2_util.current_branch(repo_path)`, assert it returns `"main"` (or whatever branch git init creates).

  **`test_current_branch_detached()`:** init a real git repo, make a commit, run `git checkout --detach HEAD` via subprocess, call `_pygit2_util.current_branch(repo_path)`, assert it returns `None`.

  **`test_status_porcelain_clean()`:** init a real git repo, make a commit, call `_pygit2_util.status_porcelain(repo_path)`, assert result is `[]`.

  **`test_status_porcelain_modified()`:** init a real git repo, make a commit, modify a tracked file, call `_pygit2_util.status_porcelain(repo_path)`, assert one line starting with `" M "`.

  **`test_status_porcelain_staged()`:** init a real git repo, make a commit, create a new file, run `git add` via subprocess, call `_pygit2_util.status_porcelain(repo_path)`, assert one line starting with `"A  "` (staged new file: X=A, Y=space).

  **`test_status_porcelain_untracked()`:** init a real git repo, make a commit, write a new untracked file (do NOT `git add`), call `_pygit2_util.status_porcelain(repo_path, include_untracked=True)`, assert one line starting with `"??"`. Call again with `include_untracked=False`, assert result is `[]`.

  **`test_list_worktrees_single()`:** init a real git repo, make a commit, call `_pygit2_util.list_worktrees(repo_path)`, assert exactly one entry with `"path"` equal to `repo_path.as_posix()` and `"branch"` equal to the current branch name. (Use `.as_posix()` — not `str()` — because `list_worktrees` returns forward-slash paths on all platforms.)

  **`test_list_worktrees_with_linked()`:** init a real git repo, make a commit, run `git worktree add <linked_path> -b wt-branch` via subprocess, call `_pygit2_util.list_worktrees(repo_path)`, assert two entries: main worktree first, linked worktree second with `"branch"` == `"wt-branch"` and `"path"` == `linked_path.as_posix()`. (Use `.as_posix()` — not `str()` — for the same reason.)

- **Commit:** `test(scripts): add test-pygit2-util.py — unit tests for _pygit2_util`

## Batch Tests

Batch verify runs `test-pygit2-util.py` directly. All 13 test functions must print `PASS:` and the final summary must show 0 failures.
