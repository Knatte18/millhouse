# Batch: _pygit2_util foundation

```yaml
task: Replace git subprocess calls with pygit2
batch: _pygit2_util foundation
number: 1
cards: 2
verify: "uv run --project plugins/mill python -c \"import sys; sys.path.insert(0, 'plugins/mill/scripts'); import _pygit2_util; print('ok')\""
depends-on: []
```

## Batch Scope

Creates the `_pygit2_util.py` helper module and adds `pygit2` as a project dependency. This batch is the foundation all other batches depend on. It delivers `GitOpsError`, `open_repo`, `discover_workdir`, `resolve_common_dir_parent`, `head_sha`, `current_branch`, `status_porcelain`, and `list_worktrees`. Downstream batches import from this module; no existing production file is modified here.

## Cards

### Card 1: Add pygit2 dependency and regenerate lockfile

- **Context:**
  - `plugins/mill/pyproject.toml`
- **Edits:**
  - `plugins/mill/pyproject.toml`
  - `uv.lock`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - In `plugins/mill/pyproject.toml`, add `"pygit2>=1.14.0"` to the `dependencies` list alongside the existing `"pyyaml>=6.0"` entry.
  - Regenerate the lockfile by running: `uv lock --project plugins/mill`
  - Verify the lockfile now includes a `pygit2` entry.
- **Commit:** `feat(deps): add pygit2>=1.14.0 to mill dependencies`

### Card 2: Create _pygit2_util.py

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_cleanliness.py`
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_worktree.py`
  - `plugins/mill/scripts/_marker.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/_pygit2_util.py`
- **Deletes:** none
- **Requirements:**
  - Create `plugins/mill/scripts/_pygit2_util.py` with the following (in order):

  **Module docstring and imports:** import `pygit2`, `sys`, `pathlib.Path`. No other stdlib imports needed.

  **`GitOpsError(RuntimeError)`:** module-level exception class. Docstring: "Raised by all _pygit2_util helpers on failure. Subclass of RuntimeError so callers can use except Exception:."

  **`open_repo(path: Path) -> pygit2.Repository`:** calls `pygit2.discover_repository(str(path))` to get the git dir, then `pygit2.Repository(git_dir)`. On `pygit2.GitError` or `KeyError`, raises `GitOpsError(f"not a git repository: {path}")`.

  **`discover_workdir(start: Path | None = None) -> Path`:** calls `open_repo(start or Path.cwd())`, returns `Path(repo.workdir).resolve()`. On `GitOpsError`, re-raises. If `repo.workdir` is `None` (bare repo), raises `GitOpsError(f"bare repository has no working directory: {start or Path.cwd()}")`.

  **`resolve_common_dir_parent(git_root: Path) -> Path`:** calls `open_repo(git_root)`. Computes `git_dir = Path(repo.path).resolve()`. If `git_dir.parent.name == "worktrees"` (i.e., we are in a linked worktree whose git dir is at `<main>/.git/worktrees/<name>/`), return `git_dir.parent.parent.parent` (the main worktree root). Otherwise return `git_dir.parent` (the main worktree root when we are in the main worktree, where `repo.path` ends in `.git/`). On `GitOpsError`, re-raises.

  **`head_sha(path: Path) -> str`:** calls `open_repo(path)`. Returns `str(repo.head.target)`. On `pygit2.GitError` (e.g., unborn HEAD) or `GitOpsError`, raises `GitOpsError(f"could not read HEAD SHA in {path}: ...")` with the original error stringified (ASCII-only: replace any non-ASCII chars with `?`).

  **`current_branch(path: Path) -> str | None`:** calls `open_repo(path)`. If `repo.head_is_detached`, returns `None`. Otherwise returns `repo.head.shorthand`. On `pygit2.GitError` or `GitOpsError`, raises `GitOpsError(f"could not read current branch in {path}: ...")`.

  **`_flags_to_xy(flags: int) -> tuple[str, str]`:** private helper, not exported. Maps a pygit2 status integer to a `(X, Y)` porcelain v1 character pair.
  - If `flags & 32768` (GIT_STATUS_CONFLICTED): return `("U", "U")`.
  - If `flags & 16384` (GIT_STATUS_IGNORED): return `("!", "!")`.
  - X char (index axis, highest priority first): check in order — bit 1 → `"A"`, bit 2 → `"M"`, bit 4 → `"D"`, bit 8 → `"R"`, bit 16 → `"T"`. Default `" "`.
  - Y char (worktree axis, highest priority first): check in order — bit 128 → `"?"`, bit 256 → `"M"`, bit 512 → `"D"`, bit 1024 → `"T"`, bit 2048 → `"R"`. Default `" "`.
  - Return `(x, y)`.

  **`status_porcelain(path: Path, *, include_untracked: bool = True) -> list[str]`:** calls `open_repo(path)`. Calls `repo.status()` which returns `dict[str, int]` (path → flags). For each `(filepath, flags)` pair:
  - Call `_flags_to_xy(flags)` to get `(x, y)`.
  - If `x == "!" and y == "!"`: skip (ignored entry, never included).
  - If `x == " " and y == "?"` (untracked): if `not include_untracked`, skip; otherwise append `f"?? {filepath}"`.
  - Otherwise: append `f"{x}{y} {filepath}"`.
  - Return `sorted(lines)`. On `pygit2.GitError` or `GitOpsError`, raises `GitOpsError(f"could not get status in {path}: ...")`.

  **`list_worktrees(cwd: Path) -> list[dict[str, str | None]]`:** calls `open_repo(cwd)`. Computes `git_dir = Path(repo.path).resolve()`. If `git_dir.parent.name == "worktrees"`: the common git dir is `git_dir.parent.parent`. Otherwise the common git dir is `git_dir`. Reads all worktrees as follows:

  1. Main worktree: path = `common_git_dir.parent`. HEAD file = `common_git_dir / "HEAD"`. Read it; if it starts with `"ref: refs/heads/"`, branch = text after that prefix (stripped). Otherwise branch = `None` (detached).

  2. Linked worktrees: iterate `(common_git_dir / "worktrees").iterdir()` if that directory exists. For each subdirectory `wt_dir`: read `wt_dir / "gitdir"` to get the worktree path (it contains the path to the worktree's `.git` file; strip `"/.git"` suffix and resolve). Read `wt_dir / "HEAD"` for the branch (same `ref: refs/heads/` parsing as above).

  3. Return a list of `{"path": str(resolved_path), "branch": branch_or_None}` dicts, main worktree first, linked worktrees in iteration order.

  On any `OSError` or `GitOpsError`, raises `GitOpsError(f"could not list worktrees for {cwd}: ...")`.

  **`__all__`:** export `["GitOpsError", "open_repo", "discover_workdir", "resolve_common_dir_parent", "head_sha", "current_branch", "status_porcelain", "list_worktrees"]`.

  **ASCII-only error messages:** any exception message or file path included in a `GitOpsError` string must pass through `str(e).encode("ascii", errors="replace").decode("ascii")` if it comes from an external source (pygit2 exception, file system path). This prevents cp1252 codec crashes on Windows stdout.

- **Commit:** `feat(scripts): add _pygit2_util.py — in-process git operations via pygit2`

## Batch Tests

Batch verify imports `_pygit2_util` to confirm the module loads and `GitOpsError` is accessible. Full functional verification is in batch 2 (`test-pygit2-util.py`). Batch 1 has no runnable unit test yet — the verify is a smoke-import.
