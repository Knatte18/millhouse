# Batch: foundation

```yaml
task: mill-cleanup script
batch: foundation
cards: 2
verify: python plugins/mill/unit_tests/test-worktree.py
depends-on: []
```

## Batch Scope

Extend `plugins/mill/scripts/_worktree.py` with two new public functions: `list_worktrees(cwd)` (parses `git worktree list --porcelain` → list of dicts) and `remove(path, cwd, force=True)` (wraps `git worktree remove --force`). Add tests for both to `test-worktree.py`.

No callers are wired in this batch — `mill-cleanup.py` in batch 02 imports these.

## Cards

### Card 1: `plugins/mill/scripts/_worktree.py` — add `list_worktrees()` and `remove()`

- **Reads:** `plugins/mill/scripts/_worktree.py` (full file — understand existing API + docstring shape), `plugins/mill/scripts/_subprocess_util.py` (subprocess invocation pattern).
- **Modifies:** `plugins/mill/scripts/_worktree.py`
- **Creates:** (none)
- **Requirements:**
  - Update the module docstring's "Public API:" block to add:
    - `list_worktrees(cwd) -> list[dict]` — enumerate all worktrees for the repo at `cwd`.
    - `remove(path, cwd, force=True) -> None` — remove a registered worktree.
  - **`def list_worktrees(cwd: Path) -> list[dict[str, str | None]]:`**
    - Runs `["git", "-C", str(cwd), "worktree", "list", "--porcelain"]` via `_subprocess_util.run`.
    - Raises `WorktreeError` on non-zero exit.
    - Parses the output: blocks are separated by blank lines. Each block contains lines like `worktree /abs/path`, `HEAD <sha>`, `branch refs/heads/<name>` (or `detached` for detached HEAD).
    - Returns a list of dicts with keys:
      - `"path"` — the absolute path string from the `worktree` line.
      - `"branch"` — short branch name (strip `refs/heads/` prefix), or `None` if the block contains the `detached` line instead of a `branch` line.
    - The main worktree (first block) is included — callers filter it if needed.
    - Empty output returns `[]`.
  - **`def remove(path: Path, cwd: Path, force: bool = True) -> None:`**
    - Builds command: `["git", "-C", str(cwd), "worktree", "remove"]`. If `force` is True, appends `"--force"`. Appends `str(path)`.
    - Runs via `_subprocess_util.run`. Raises `WorktreeError` on non-zero exit with message: `f"git worktree remove failed (path={path}): {result.stderr.strip()!r}"`.
    - Logs `f"[worktree] remove: path={path}"` to stderr (matches `create`'s logging pattern).
  - No `if __name__ == "__main__":` block — helper-only per CLAUDE.md convention.
- **Commit:** `feat(worktree): add list_worktrees() and remove() helpers`

### Card 2: `plugins/mill/unit_tests/test-worktree.py` — extend with tests for new functions

- **Reads:** `plugins/mill/unit_tests/test-worktree.py` (existing tests — understand fixture pattern and main() structure), `plugins/mill/scripts/_worktree.py` (post-Card-1).
- **Modifies:** `plugins/mill/unit_tests/test-worktree.py`
- **Creates:** (none)
- **Requirements:**
  - All new tests live inside the existing `main()` function, after the existing tests. Follow the same `try/except AssertionError` + PASS print pattern.
  - **Fixture helper** (add near top of file or inline): `_git_init(path)` — runs `git init -b main` (requires Git ≥ 2.28; if the CI image is older, follow up with `git symbolic-ref HEAD refs/heads/main`), `git config user.email`, `git config user.name`, creates an empty initial commit. Reuse across tests.
  - **Test `list_worktrees` — main worktree only:**
    - `tempfile.TemporaryDirectory` → `_git_init(hub)`.
    - Call `list_worktrees(hub)`. Assert result has exactly 1 entry. Assert `entry["path"] == str(hub)`. Assert `entry["branch"] == "main"`.
    - PASS print: `"PASS list_worktrees — single main worktree"`.
  - **Test `list_worktrees` — two worktrees:**
    - New `TemporaryDirectory`, same `_git_init` setup. Add second worktree: `subprocess.run(["git", "-C", str(hub), "worktree", "add", "-b", "wt-branch", str(wt_path)], check=True)`.
    - Call `list_worktrees(hub)`. Assert 2 entries. Assert the second entry has `"branch" == "wt-branch"` and `"path" == str(wt_path)`.
    - PASS print: `"PASS list_worktrees — two worktrees"`.
  - **Test `list_worktrees` — detached HEAD:**
    - On the wt from previous fixture, checkout a detached HEAD: get sha via `git rev-parse HEAD`, then `git -C <wt_path> checkout --detach <sha>`. Or create a new worktree with `--detach` (requires a commit sha). Simplest: add worktree with `git worktree add --detach <path> HEAD`.
    - Assert that the detached worktree entry has `"branch" == None`.
    - PASS print: `"PASS list_worktrees — detached HEAD branch is None"`.
  - **Test `remove`:**
    - Fresh fixture with two worktrees. Call `remove(wt_path, cwd=hub)`. Assert `list_worktrees(hub)` now has 1 entry (main only). Assert `wt_path` does not exist on disk.
    - PASS print: `"PASS remove — worktree removed from git and disk"`.
  - **Test `remove` non-existent path raises WorktreeError:**
    - Call `remove(hub / "nonexistent", cwd=hub, force=True)`. Catch `WorktreeError`. Assert exception is raised.
    - PASS print: `"PASS remove — nonexistent path raises WorktreeError"`.
  - Do NOT mock git — all tests use real `git` in `tempfile.TemporaryDirectory`.
- **Commit:** `test(worktree): tests for list_worktrees() and remove()`

## Batch Tests

`python plugins/mill/unit_tests/test-worktree.py` must pass on its own. Uses real `git` but no network. Batch 02 depends on this batch passing before wiring the new functions into `mill-cleanup.py`.
