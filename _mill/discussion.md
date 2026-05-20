# Discussion: Replace git subprocess calls with pygit2

```yaml
task: Replace git subprocess calls with pygit2
slug: pygit2-git-ops
status: discussing
parent: None
```

## Problem

Mill scripts spawn a new git process per operation, costing ~150ms on Windows per call (process startup overhead plus potential Defender scanning). Scripts like `millpy-status.py` trigger two `git rev-parse` calls on every invocation before doing any actual work. Across a `mill-go` batch run — spawn, status, review, cleanup — this overhead accumulates to several seconds of pure process-spawning cost. pygit2 is a Python binding to libgit2, a C library that runs git operations in-process with zero subprocess overhead. It ships Windows wheels on PyPI, supports Python 3.10+, and has a worktree enumeration API covering the read-only hot paths.

## Scope

**In:**
- New `_pygit2_util.py` helper module in `plugins/mill/scripts/` exposing all read-only git operations the codebase needs.
- Replace subprocess git calls in `_paths.py` (`resolve_git_root`, `resolve_main_worktree_root`, `resolve_active_worktree`).
- Replace subprocess git calls in `_marker.py` (`slug_from_branch`, `task_data`).
- Replace subprocess git calls in `_cleanliness.py` (`capture_snapshot`, `compute_new_dirt`).
- Replace subprocess git calls in `_review_common.py` (`_capture_head_sha`, `_capture_porcelain`).
- Replace subprocess git calls in `_worktree.py` (`list_worktrees` only).
- Add `pygit2>=1.14.0` to `plugins/mill/pyproject.toml` dependencies.
- Unit tests for `_pygit2_util.py` in `plugins/mill/unit_tests/test-pygit2-util.py`.

**Out:**
- Write operations stay as subprocess: `git add`, `git commit`, `git push`, `git pull`, `git rebase`, `git clone`, `git init`, `git worktree add`, `git worktree remove`, `git worktree prune`. These are infrequent and benefit from no-touch approach.
- No changes to `_wiki.py`, `_spawn_core.py`, `millpy-wikipush.py`, `millpy-abandon.py`, `millpy-migrate-config.py`, `_gh_issues.py` — these only have write-path git calls.
- No changes to integration test setup code (tests create real git repos via subprocess and that is fine).
- No caching layer or daemon — pygit2 is fast enough per-call.
- No changes to `_subprocess_util.py` itself.

## Decisions

### new-helper-module

- **Decision:** Create `_pygit2_util.py` as the single location for all pygit2 wrapping logic. Callers import named helpers; no pygit2 import scattered across 6+ files.
- **Rationale:** Single point for error handling, flag-to-porcelain conversion, and future API changes. Keeps existing modules minimally modified (swap one import for another at each call site).
- **Rejected:** Inline pygit2 calls per-module — scatters boilerplate, duplicates XY-flag conversion logic, and makes future version upgrades harder.

### read-only-only

- **Decision:** Replace all read-only git calls (rev-parse, branch, status, worktree list) with pygit2. Keep all write-path calls (commit, push, add, pull, rebase, clone, worktree add/remove/prune) as subprocess.
- **Rationale:** Read calls are the hot paths called on every script startup and every batch. Write calls are infrequent and their subprocess error messages are helpful; no perf win justifies touching them.
- **Rejected:** Replacing write ops too — risk without benefit. Rejected "path/branch/HEAD only" (option 2) — `git status --porcelain` in `_cleanliness.py` is also hot (called twice per batch in mill-go) and worth replacing.

### porcelain-compat-converter

- **Decision:** `_pygit2_util.status_porcelain(path, *, include_untracked=True)` returns `list[str]` in porcelain v1 format (`XY path`), so callers in `_cleanliness.py` and `_review_common.py` are unchanged.
- **Rationale:** The callers do line-set arithmetic on porcelain strings (line content matters, not just presence). Keeping the string format means zero changes to `_filter_porcelain`, `_porcelain_diff`, and `compute_new_dirt`.
- **Rejected:** Changing callers to use pygit2 status dicts natively — would require touching `_review_common._filter_porcelain`, `_porcelain_diff`, `ReviewerOverstepError.porcelain_diff`, and `_cleanliness.compute_new_dirt`, all of which depend on the porcelain line format.

### pygit2-version-pin

- **Decision:** Require `pygit2>=1.14.0` (the version that added `repo.list_worktrees()` / `repo.lookup_worktree()`).
- **Rationale:** Latest stable is 1.19.2; any version from 1.14.0 onward has the full API we need. Pinning to `>=1.14.0` gives flexibility while ensuring the worktree API is present.
- **Rejected:** Pinning to `==1.19.2` — too strict for a library dependency. Rejected `>=1.0.0` — before 1.14.0 the worktree API is absent.

### worktree-list-head-reading

- **Decision:** For `list_worktrees()`, read `HEAD` files directly from the git object database instead of opening a second `pygit2.Repository` per linked worktree.
- **Rationale:** Main worktree HEAD lives at `<common_git_dir>/HEAD`; each linked worktree's HEAD lives at `<common_git_dir>/worktrees/<name>/HEAD`. Both are plain text files (`ref: refs/heads/<branch>` or a bare SHA). Reading them avoids opening N additional Repository objects.
- **Rejected:** Opening `pygit2.Repository(worktree.path)` per linked worktree — creates N repo objects purely to read HEAD; marginally simpler but slower for repos with many worktrees.

### testing

- **Decision:** Add `test-pygit2-util.py` unit tests for `_pygit2_util.py` using `tempfile` real git repos (init + commit via subprocess in test setup). Run existing integration tests to verify regressions.
- **Rationale:** The helper functions have non-obvious logic (XY-flag mapping, commondir detection, HEAD file parsing). Unit tests catch edge cases without relying on mill's full fixture stack.
- **Rejected:** Integration tests only — they exercise real flows but don't cover edge cases like detached HEAD, linked worktree commondir resolution, or conflicted status flags in isolation.

## Technical context

### `_pygit2_util.py` public API

```python
# All helpers raise SystemExit or specific errors on failure (matching
# the existing _subprocess_util pattern so callers behave identically).

def open_repo(path: Path) -> pygit2.Repository:
    """Open the repo whose working tree contains `path`. Handles both
    main worktrees and linked worktrees. Raises SystemExit if not a git repo."""

def discover_workdir(start: Path | None = None) -> Path:
    """Return the working-tree root (replaces `git rev-parse --show-toplevel`).
    Uses pygit2.discover_repository() then repo.workdir."""

def resolve_common_dir_parent(git_root: Path) -> Path:
    """Return the main worktree root (replaces `git rev-parse --git-common-dir`).
    Uses repo.path to determine whether git_root is a linked worktree:
    if Path(repo.path).parent.name == 'worktrees' -> linked -> go up 3 levels.
    Otherwise -> main -> go up 1 level from repo.path."""

def head_sha(path: Path) -> str:
    """Return HEAD commit SHA as hex string. Raises SystemExit on detached or error."""

def current_branch(path: Path) -> str | None:
    """Return current branch shortname, or None on detached HEAD."""

def status_porcelain(path: Path, *, include_untracked: bool = True) -> list[str]:
    """Return git status as porcelain v1 lines (XY path), sorted.
    include_untracked=False excludes entries where the only flag is WT_NEW."""

def list_worktrees(cwd: Path) -> list[dict[str, str | None]]:
    """Return list of {path, branch} dicts for all worktrees (main + linked).
    Reads HEAD files from the git object database; no subprocess."""
```

### pygit2 flag-to-XY mapping

pygit2 status flags are a bitfield. Only the highest-priority flag per axis applies (order matters for multi-flag entries):

| Flag constant | Bit | XY X char |
|---|---|---|
| `GIT_STATUS_INDEX_NEW` | 1 | `A` |
| `GIT_STATUS_INDEX_MODIFIED` | 2 | `M` |
| `GIT_STATUS_INDEX_DELETED` | 4 | `D` |
| `GIT_STATUS_INDEX_RENAMED` | 8 | `R` |
| `GIT_STATUS_INDEX_TYPECHANGE` | 16 | `T` |

| Flag constant | Bit | XY Y char |
|---|---|---|
| `GIT_STATUS_WT_NEW` | 128 | `?` (untracked) |
| `GIT_STATUS_WT_MODIFIED` | 256 | `M` |
| `GIT_STATUS_WT_DELETED` | 512 | `D` |
| `GIT_STATUS_WT_TYPECHANGE` | 1024 | `T` |
| `GIT_STATUS_WT_RENAMED` | 2048 | `R` |
| `GIT_STATUS_CONFLICTED` | 32768 | both `U` |
| `GIT_STATUS_IGNORED` | 16384 | omit entirely |

Untracked-only entries: `x == ' '` and `y == '?'` → formatted as `?? path` (porcelain v1 convention). Ignored entries are always omitted.

### `resolve_git_root()` wiki guard

`resolve_git_root()` has a safety check: if the resolved working directory is the wiki clone, it raises `SystemExit`. This guard must be preserved verbatim when rewriting with pygit2. The check compares `repo.workdir` against `resolve_wiki_path(repo_root)` the same way the existing code does.

### `resolve_active_worktree()` branch call

`resolve_active_worktree()` at `_paths.py:341` calls `git -C <worktree> branch --show-current` to validate the linked worktree's branch. Replace with `current_branch(worktree)` from `_pygit2_util`. The `None` (detached HEAD) path falls through to the `dir_slug != slug` check, which rejects it the same way.

### `_marker.task_data()` double call

`task_data()` calls `slug_from_branch()` (which calls `branch --show-current` internally) and then calls `branch --show-current` again redundantly. After the migration, `slug_from_branch()` will use pygit2; `task_data()` should call `_pygit2_util.current_branch(git_root)` directly for the second call, eliminating the double open (or just call `open_repo(git_root)` once and pass the repo in).

### `pyproject.toml` location

`plugins/mill/pyproject.toml` — add `pygit2>=1.14.0` to `dependencies`. The uv lockfile (`uv.lock` alongside the pyproject.toml) must be regenerated: `uv lock --project plugins/mill`.

### `_cleanliness.py` `--untracked-files=no` flag

Both `capture_snapshot()` and `compute_new_dirt()` use `--untracked-files=no`. Map to `status_porcelain(path, include_untracked=False)`.

### `_review_common._capture_porcelain()` uses plain `--porcelain`

No `--untracked-files=no` flag — use `status_porcelain(path, include_untracked=True)` (the default).

### pygit2 Windows notes

pygit2 ships Windows wheels via PyPI. `pygit2.discover_repository()` handles Windows long paths. The `repo.path` and `repo.workdir` return forward-slash paths on Windows (libgit2 internal representation); callers should use `Path(repo.workdir)` which normalises separators.

## Constraints

- `requires-python = ">=3.10"` in pyproject.toml — pygit2 1.14+ supports Python 3.10+, no conflict.
- All Python output is ASCII-only (`print()` / `_log()`) — error messages in `_pygit2_util.py` must not include non-ASCII. pygit2 exception messages from libgit2 may include file paths with non-ASCII; strip or encode safely.
- No `cd` to wiki clone from scripts — unaffected (pygit2 never needs cwd).
- Scripts directory is flat (no submodules) — `_pygit2_util.py` goes in `plugins/mill/scripts/`.

## Testing

### `test-pygit2-util.py`

Unit tests using `tempfile.TemporaryDirectory` + real git repos (setup via subprocess `git init`, `git commit` — tests are allowed to use subprocess for fixture creation). Cover:

- `discover_workdir(start)` — happy path from working dir; raises SystemExit on non-repo path.
- `resolve_common_dir_parent(git_root)` — called from main worktree (returns itself); called from a linked worktree (returns main). Test with a real `git worktree add` to create a linked fixture.
- `head_sha(path)` — returns a 40-char hex string; matches `git rev-parse HEAD` output.
- `current_branch(path)` — returns branch name on named branch; returns `None` on detached HEAD.
- `status_porcelain(path)` — empty clean repo returns `[]`; modified file appears as `' M path'`; new untracked file as `'?? path'`; `include_untracked=False` suppresses it; staged new file as `'A  path'`.
- `list_worktrees(cwd)` — single main worktree; main + one linked worktree (check both entries present with correct path and branch).

### Existing tests (regression check)

Run `uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py` after the change. Key tests that exercise the replaced code paths: `test-paths.py`, `test-marker.py`, `test-cleanliness.py`, `test-review-common-guard.py`, `test-worktree.py`, `test-paths-status.py`.

No changes to test fixtures or test helpers — existing tests already use real git repos.

## Q&A log

- **Q:** Which git calls to migrate — only startup path or include status/worktree/HEAD? **A:** [auto-pick] All read-only ops. **Why:** Maximises perf win; `git status --porcelain` in `_cleanliness.py` is also in the hot batch path.
- **Q:** Helper module strategy — new `_pygit2_util.py` or inline? **A:** [auto-pick] New `_pygit2_util.py`. **Why:** Single place for XY-flag conversion and error handling; existing modules change minimally.
- **Q:** `git status --porcelain` format — XY converter or change callers? **A:** [auto-pick] XY converter producing porcelain v1 strings. **Why:** Callers' line-set arithmetic and the `porcelain_diff` display string are both format-dependent.
- **Q:** Testing approach? **A:** [auto-pick] New `test-pygit2-util.py` unit tests + run existing integration tests for regression. **Why:** Edge cases (detached HEAD, linked worktree commondir) need isolated unit tests; integration tests verify real flows.
