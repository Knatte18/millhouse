# Batch: migrate _cleanliness.py and _review_common.py

```yaml
task: Replace git subprocess calls with pygit2
batch: migrate _cleanliness.py and _review_common.py
number: 5
cards: 3
verify: "uv run --project plugins/mill python plugins/mill/unit_tests/test-cleanliness.py && uv run --project plugins/mill python plugins/mill/unit_tests/test-review-common-guard.py"
depends-on: [1]
```

## Batch Scope

Replaces the two subprocess calls in `_cleanliness.py` (`capture_snapshot` and `compute_new_dirt`) with `_pygit2_util.status_porcelain(path, include_untracked=False)`. Replaces the two subprocess calls in `_review_common.py` (`_capture_head_sha` and `_capture_porcelain`) with `_pygit2_util.head_sha` and `_pygit2_util.status_porcelain`. After migration, `import _subprocess_util` is removed from `_cleanliness.py` (no remaining calls). `_review_common.py` keeps its `import _subprocess_util` because `bulk_files_with_diff` (line ~769) still uses `git diff` via subprocess.

## Cards

### Card 10: Replace subprocess calls in _cleanliness.py

- **Context:**
  - `plugins/mill/scripts/_pygit2_util.py`
- **Edits:**
  - `plugins/mill/scripts/_cleanliness.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Add `import _pygit2_util` to `_cleanliness.py` at the top.

  - In `capture_snapshot(worktree: Path, snapshot_path: Path) -> None`: replace:
    ```python
    result = _subprocess_util.run(
        ["git", "-C", str(worktree), "status", "--porcelain", "--untracked-files=no"],
        check=True,
    )
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(result.stdout, encoding="utf-8")
    ```
    with:
    ```python
    lines = _pygit2_util.status_porcelain(worktree, include_untracked=False)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    ```
    The trailing newline preserves the same file format as `result.stdout` from `subprocess.run` (which includes a trailing newline).

  - In `compute_new_dirt(worktree: Path, snapshot_path: Path) -> list[str]`: replace:
    ```python
    result = _subprocess_util.run(
        ["git", "-C", str(worktree), "status", "--porcelain", "--untracked-files=no"],
        check=True,
    )
    post_text = result.stdout
    ```
    with:
    ```python
    lines = _pygit2_util.status_porcelain(worktree, include_untracked=False)
    post_text = "\n".join(lines) + ("\n" if lines else "")
    ```
    The rest of `compute_new_dirt` (the line-set diff) is unchanged.

  - Remove `import _subprocess_util` from `_cleanliness.py` (no remaining subprocess calls).
- **Commit:** `refactor(_cleanliness): replace subprocess status calls with _pygit2_util; remove _subprocess_util import`

### Card 11: Replace subprocess calls in _review_common.py

- **Context:**
  - `plugins/mill/scripts/_pygit2_util.py`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Add `import _pygit2_util` to `_review_common.py` at the top alongside existing imports.

  - Replace `_capture_head_sha(project_root: Path) -> str` (currently lines ~158-168):
    ```python
    def _capture_head_sha(project_root: Path) -> str:
        """Return the current HEAD SHA as a hex string. Raises ReviewError on git failure."""
        try:
            return _pygit2_util.head_sha(project_root)
        except _pygit2_util.GitOpsError as e:
            raise ReviewError(
                f"worktree_snapshot_guard: HEAD SHA read failed in {project_root}: {e}"
            ) from e
    ```

  - Replace `_capture_porcelain(project_root: Path) -> list[str]` (currently lines ~171-181):
    ```python
    def _capture_porcelain(project_root: Path) -> list[str]:
        """Return git status as porcelain v1 lines (one per entry). Raises ReviewError on failure."""
        try:
            return _pygit2_util.status_porcelain(project_root, include_untracked=True)
        except _pygit2_util.GitOpsError as e:
            raise ReviewError(
                f"worktree_snapshot_guard: status read failed in {project_root}: {e}"
            ) from e
    ```

  - Keep `import _subprocess_util` in `_review_common.py` — `bulk_files_with_diff` at line ~769 still uses `_subprocess_util.run(["git", "diff", ...])`.
- **Commit:** `refactor(_review_common): replace subprocess HEAD/status calls with _pygit2_util`

### Card 12: Update test-cleanliness.py mock tests for pygit2 migration

- **Context:**
  - `plugins/mill/scripts/_pygit2_util.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-cleanliness.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  After migration, `_cleanliness.py` calls `_pygit2_util.status_porcelain` instead of `_subprocess_util.run`. All nine tests in `test-cleanliness.py` patch `_subprocess_util.run` and pass a plain `tempfile.TemporaryDirectory()` (not a git repo) as the worktree — after migration they will raise `GitOpsError` because pygit2 requires a real repository.

  **Tests 1–8 (`compute_new_dirt`, lines ~24–152):** For each test, replace:
  ```python
  with unittest.mock.patch("_subprocess_util.run", return_value=_mock_run("<stdout>")):
      result = compute_new_dirt(Path(tmp), snapshot_path)
  ```
  with:
  ```python
  with unittest.mock.patch("_cleanliness._pygit2_util.status_porcelain", return_value=[<list>]):
      result = compute_new_dirt(Path(tmp), snapshot_path)
  ```
  The mock `return_value` must be `list[str]` — each element is a porcelain line without a trailing `\n`. Translate each `_mock_run(stdout)` to the equivalent list: e.g. `_mock_run(" M b.txt\n M a.txt\n")` → `[" M a.txt", " M b.txt"]` (already sorted, no trailing newlines). For CRLF test 8, the mock returns `[" M file.txt"]` — no CRLF handling is needed since pygit2 returns clean strings; the test still verifies that a CRLF snapshot file produces no false-positive new dirt.

  **Test 9 (`capture_snapshot`, lines ~154–173):** Replace:
  ```python
  with unittest.mock.patch("_subprocess_util.run", return_value=_mock_run(" M file.txt\n")) as mock:
      capture_snapshot(Path(tmp), snapshot_path)
  called_argv = mock.call_args.args[0]
  assert called_argv[:3] == ["git", "-C", str(Path(tmp))], ...
  assert snapshot_path.exists(), ...
  assert content == " M file.txt\n", ...
  ```
  with:
  ```python
  with unittest.mock.patch("_cleanliness._pygit2_util.status_porcelain", return_value=[" M file.txt"]):
      capture_snapshot(Path(tmp), snapshot_path)
  assert snapshot_path.exists(), ...
  assert content == " M file.txt\n", ...
  ```
  Remove the `called_argv` variable and its assertion — they tested subprocess argument format which is no longer applicable. Keep the file existence and content assertions: the output file format (`" M file.txt\n"` with trailing newline) is preserved by the new implementation's `"\n".join(lines) + "\n"` logic.

  **Cleanup:** Remove the `_mock_run` helper function if no tests reference it after the replacements. Add `import _pygit2_util` at the top of the test file only if a test directly calls `_pygit2_util` API (the string-based patch `"_cleanliness._pygit2_util.status_porcelain"` does not require it). Remove `import _subprocess_util` if it is no longer used.
- **Commit:** `test(_cleanliness): update mock patches for pygit2 migration`

## Batch Tests

Batch verify runs `test-cleanliness.py` (covers `capture_snapshot`, `compute_new_dirt`, and the line-set diff arithmetic) and `test-review-common-guard.py` (covers `worktree_snapshot_guard` — the context manager that calls `_capture_head_sha` and `_capture_porcelain`). `test-review-common-guard.py` uses `subprocess.run` (stdlib) for real git fixture setup only — it has no mock patches on `_capture_head_sha` or `_capture_porcelain`, so it requires no update card.
