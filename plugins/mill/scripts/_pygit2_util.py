"""In-process git operations using pygit2 instead of subprocess calls.

Provides access to git repository state (HEAD, current branch, status, worktrees)
without spawning git subprocesses. All failures raise GitOpsError; callers in
different modules re-raise as their layer's exception type.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pygit2


class GitOpsError(RuntimeError):
    """Raised by all _pygit2_util helpers on failure. Subclass of RuntimeError so callers can use except Exception:."""


def open_repo(path: Path) -> pygit2.Repository:
    """Open a git repository.

    Args:
        path: Any path inside or at the root of the repository.

    Returns:
        The opened pygit2.Repository.

    Raises:
        GitOpsError: If the path is not inside a git repository.
    """
    try:
        git_dir = pygit2.discover_repository(str(path))
        if git_dir is None:
            raise KeyError("not a git directory")
        return pygit2.Repository(git_dir)
    except (pygit2.GitError, KeyError) as e:
        raise GitOpsError(f"not a git repository: {path}") from e


def discover_workdir(start: Path | None = None) -> Path:
    """Discover the working directory of a git repository.

    Args:
        start: Starting path for discovery (default: current working directory).

    Returns:
        The absolute path to the working directory.

    Raises:
        GitOpsError: If not in a git repository or the repository is bare.
    """
    repo = open_repo(start or Path.cwd())
    if repo.workdir is None:
        raise GitOpsError(f"bare repository has no working directory: {start or Path.cwd()}")
    return Path(repo.workdir).resolve()


def resolve_common_dir_parent(git_root: Path) -> Path:
    """Resolve the root of the main worktree from any worktree.

    When in a linked worktree, git_dir is at <main>/.git/worktrees/<name>/.
    Return the main worktree root (git_dir.parent.parent.parent).
    When in the main worktree, git_dir is at <main>/.git/.
    Return the main worktree root (git_dir.parent).

    Args:
        git_root: Absolute path to any worktree's git checkout root.

    Returns:
        The absolute path to the main worktree root.

    Raises:
        GitOpsError: If unable to open the repository.
    """
    repo = open_repo(git_root)
    git_dir = Path(repo.path).resolve()

    if git_dir.parent.name == "worktrees" and git_dir.parent.parent.name == ".git":
        return git_dir.parent.parent.parent
    return git_dir.parent


def head_sha(path: Path) -> str:
    """Get the SHA of the current HEAD.

    Args:
        path: Path inside the repository.

    Returns:
        The HEAD SHA as a string.

    Raises:
        GitOpsError: If unable to read HEAD (e.g., unborn HEAD, detached in invalid state).
    """
    try:
        repo = open_repo(path)
        return str(repo.head.target)
    except (pygit2.GitError, GitOpsError) as e:
        error_msg = str(e).encode("ascii", errors="replace").decode("ascii")
        raise GitOpsError(f"could not read HEAD SHA in {path}: {error_msg}") from e


def current_branch(path: Path) -> str | None:
    """Get the current branch name, or None if HEAD is detached.

    Args:
        path: Path inside the repository.

    Returns:
        The branch name, or None if detached.

    Raises:
        GitOpsError: If unable to read the current branch.
    """
    try:
        repo = open_repo(path)
        if repo.head_is_detached:
            return None
        return repo.head.shorthand
    except (pygit2.GitError, GitOpsError) as e:
        error_msg = str(e).encode("ascii", errors="replace").decode("ascii")
        raise GitOpsError(f"could not read current branch in {path}: {error_msg}") from e


def _flags_to_xy(flags: int) -> tuple[str, str]:
    """Convert pygit2 status flags to porcelain v1 (X, Y) character pair.

    Args:
        flags: pygit2 status flags integer.

    Returns:
        A tuple of (X, Y) where X is index status and Y is worktree status.
    """
    GIT_STATUS_CONFLICTED = 32768
    GIT_STATUS_IGNORED = 16384

    if flags & GIT_STATUS_CONFLICTED:
        return ("U", "U")
    if flags & GIT_STATUS_IGNORED:
        return ("!", "!")

    x = " "
    if flags & 1:
        x = "A"
    elif flags & 2:
        x = "M"
    elif flags & 4:
        x = "D"
    elif flags & 8:
        x = "R"
    elif flags & 16:
        x = "T"

    y = " "
    if flags & 128:
        y = "?"
    elif flags & 256:
        y = "M"
    elif flags & 512:
        y = "D"
    elif flags & 1024:
        y = "T"
    elif flags & 2048:
        y = "R"

    return (x, y)


def status_porcelain(path: Path, *, include_untracked: bool = True) -> list[str]:
    """Get the git status in porcelain v1 format.

    Returns status as a list of strings in the format "XY path" where X is the
    index status and Y is the worktree status. Sorted output.

    Note: For index-renamed files, repo.status() returns only the new path
    (bit 8 set, no "oldpath -> newpath" format). Callers that do line-set
    arithmetic (e.g. _cleanliness.compute_new_dirt, _review_common._filter_porcelain)
    are unaffected because they compare sets of opaque strings; within-session
    comparisons are self-consistent.

    Args:
        path: Path inside the repository.
        include_untracked: When False, skip untracked files (?? entries).

    Returns:
        Sorted list of status lines in porcelain v1 format.

    Raises:
        GitOpsError: If unable to get status.
    """
    try:
        repo = open_repo(path)
        status_dict = repo.status()
        lines = []
        for filepath, flags in status_dict.items():
            x, y = _flags_to_xy(flags)
            if x == "!" and y == "!":
                continue
            if x == " " and y == "?":
                if not include_untracked:
                    continue
                lines.append(f"?? {filepath}")
            else:
                lines.append(f"{x}{y} {filepath}")
        return sorted(lines)
    except (pygit2.GitError, GitOpsError) as e:
        error_msg = str(e).encode("ascii", errors="replace").decode("ascii")
        raise GitOpsError(f"could not get status in {path}: {error_msg}") from e


def list_worktrees(cwd: Path) -> list[dict[str, str | None]]:
    """List all git worktrees for the repository.

    Returns a list of dicts with "path" (absolute, forward-slash format) and
    "branch" (name or None if detached) keys. Main worktree is listed first,
    followed by linked worktrees in iteration order.

    Args:
        cwd: Any path inside the repository.

    Returns:
        List of {"path": str, "branch": str | None} dicts.

    Raises:
        GitOpsError: If unable to list worktrees.
    """
    try:
        repo = open_repo(cwd)
        git_dir = Path(repo.path).resolve()

        if git_dir.parent.name == "worktrees" and git_dir.parent.parent.name == ".git":
            common_git_dir = git_dir.parent.parent
        else:
            common_git_dir = git_dir

        result = []

        main_worktree_root = common_git_dir.parent
        main_head_file = common_git_dir / "HEAD"
        main_branch = None
        try:
            head_content = main_head_file.read_text(encoding="utf-8").strip()
            if head_content.startswith("ref: refs/heads/"):
                main_branch = head_content[len("ref: refs/heads/") :]
        except (OSError, UnicodeDecodeError):
            pass

        result.append({"path": main_worktree_root.as_posix(), "branch": main_branch})

        worktrees_dir = common_git_dir / "worktrees"
        if worktrees_dir.exists():
            try:
                for wt_dir in worktrees_dir.iterdir():
                    if not wt_dir.is_dir():
                        continue

                    gitdir_file = wt_dir / "gitdir"
                    try:
                        gitdir_content = gitdir_file.read_text(encoding="utf-8").strip()
                        wt_git_path = Path(gitdir_content).resolve()
                        if wt_git_path.is_file():
                            wt_root = wt_git_path.parent
                        else:
                            wt_root = wt_git_path.parent
                    except (OSError, UnicodeDecodeError):
                        continue

                    wt_branch = None
                    wt_head_file = wt_dir / "HEAD"
                    try:
                        head_content = wt_head_file.read_text(encoding="utf-8").strip()
                        if head_content.startswith("ref: refs/heads/"):
                            wt_branch = head_content[len("ref: refs/heads/") :]
                    except (OSError, UnicodeDecodeError):
                        pass

                    result.append({"path": wt_root.as_posix(), "branch": wt_branch})
            except OSError:
                pass

        return result
    except (OSError, GitOpsError) as e:
        error_msg = str(e).encode("ascii", errors="replace").decode("ascii")
        raise GitOpsError(f"could not list worktrees for {cwd}: {error_msg}") from e


__all__ = [
    "GitOpsError",
    "open_repo",
    "discover_workdir",
    "resolve_common_dir_parent",
    "head_sha",
    "current_branch",
    "status_porcelain",
    "list_worktrees",
]
