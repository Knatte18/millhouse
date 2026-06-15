"""
Helpers for mill-finalize's stacked-branch cleanup logic.

Detects whether a PR base branch tracks the task state directory,
informing whether cleanup should restore the directory from the base
(stacked branch case) or remove it (normal case).
"""
from __future__ import annotations

from pathlib import Path

import _subprocess_util


def base_tracks_task_dir(worktree: Path, base_branch: str, task_dir: Path) -> bool:
    """
    Check whether ``base_branch`` tracks ``task_dir`` in the repository.

    Used by mill-finalize's PR cleanup to decide whether to restore
    task_dir from the base branch (stacked case) or remove it
    (normal case).

    Args:
        worktree: Absolute path to the task worktree.
        base_branch: The base branch name (e.g., "main" or "_mill/task-slug").
        task_dir: Absolute path to the task state directory (typically ``_mill/``).

    Returns:
        True if ``base_branch`` tracks a status.md file inside ``task_dir``;
        False otherwise (including errors).

    The check uses ``git ls-tree <base_branch> -- <task_dir-relative>/status.md``
    to avoid false positives from empty directories. Forward slashes are
    enforced for the pathspec via ``.as_posix()`` to handle Windows paths.
    """
    # Compute the worktree-relative form and convert to forward slashes for git.
    try:
        task_dir_rel = task_dir.relative_to(worktree)
        posix_path = task_dir_rel.as_posix()
    except ValueError:
        # task_dir is not under worktree
        return False

    status_file_path = f"{posix_path}/status.md"

    result = _subprocess_util.run(
        ["git", "ls-tree", base_branch, "--", status_file_path],
        cwd=worktree,
    )

    # Return True only if the command succeeded and produced output.
    return result.returncode == 0 and bool(result.stdout.strip())
