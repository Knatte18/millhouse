"""
Helpers for mill-finalize's stacked-branch cleanup logic.

Detects whether a PR base branch tracks the task state directory, informing whether cleanup should
restore the directory from the base (stacked branch case) or remove it (normal case).
"""
from __future__ import annotations

import sys
from pathlib import Path

import _subprocess_util


def checkpoint_branch_name(branch: str) -> str:
    """
    Return the name of the checkpoint branch that mill-merge-in creates for ``branch``.

    Slashes become dashes, matching mill-merge-in's ``tr '/' '-'``.
    """
    return "mill-checkpoint-" + branch.replace("/", "-")


def delete_checkpoint_branch(repo: Path, branch: str) -> bool:
    """
    Delete the mill-merge-in checkpoint branch belonging to task branch ``branch``.

    A missing checkpoint counts as success.
    Any other git failure is reported on stderr and ignored, so teardown is never halted.

    Returns:
        True when the checkpoint is gone afterwards, False when deletion failed.
    """
    name = checkpoint_branch_name(branch)
    probe = _subprocess_util.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", f"refs/heads/{name}"],
        quiet_nonzero=True,
    )
    if probe.returncode != 0:
        return True
    result = _subprocess_util.run(["git", "-C", str(repo), "branch", "-D", name])
    if result.returncode != 0:
        print(
            f"[finalize-cleanup] could not delete checkpoint branch {name}: "
            f"{result.stderr.strip()}",
            file=sys.stderr,
        )
        return False
    return True


def stash_pr_notes(worktree: Path, task_dir: Path, slug: str) -> bool:
    """
    Copy the task's pr-notes file to ``<worktree>/.scratch/pr-notes-<slug>.md`` so it survives cleanup.

    A non-empty source always overwrites the scratch copy;
    a missing or blank source leaves any existing scratch copy untouched.

    Returns:
        True when a scratch copy exists afterwards.
    """
    source = task_dir / "pr-notes.md"
    destination = worktree / ".scratch" / f"pr-notes-{slug}.md"
    if source.exists():
        text = source.read_text(encoding="utf-8")
        if text.strip():
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(text, encoding="utf-8")
            return True
    return destination.exists()


def base_tracks_task_dir(worktree: Path, base_branch: str, task_dir: Path) -> bool:
    """
    Check whether ``base_branch`` tracks ``task_dir`` in the repository.

    Used by mill-finalize's PR cleanup to decide whether to restore task_dir from the base branch
    (stacked case) or remove it (normal case).

    Args:
        worktree: Absolute path to the task worktree.
        base_branch: The base branch name (e.g., "main" or "_mill/task-slug").
        task_dir: Absolute path to the task state directory (typically ``_mill/``).

    Returns:
        True if ``base_branch`` tracks a status.md file inside ``task_dir``;
        False otherwise (including errors).

    The check uses ``git ls-tree <base_branch> -- <task_dir-relative>/status.md`` to avoid false
    positives from empty directories.
    Forward slashes are enforced for the pathspec via ``.as_posix()`` to handle Windows paths.
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
