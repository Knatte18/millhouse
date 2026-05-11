"""
Branch-derived slug and task data for the current mill worktree.

Reads the git branch name and validates it against Home.md — no
marker file required. Replaces the subset of _active.read_all that
callers need to identify which task this worktree is working on.

Public API:
    MarkerError
        Raised on any slug-derivation failure.
    slug_from_branch(git_root: Path, wiki_path: Path, cfg: dict) -> str
        Derive and validate the slug from the current branch name.
    task_data(git_root: Path, wiki_path: Path, cfg: dict) -> dict
        Return {"slug": str, "branch": str, "task_title": str}.
"""
from __future__ import annotations

from pathlib import Path

import _subprocess_util
import _tasks_md


class MarkerError(RuntimeError):
    """Raised when slug derivation from branch + Home.md fails."""


def slug_from_branch(git_root: Path, wiki_path: Path, cfg: dict) -> str:
    """Derive and validate the task slug from the current git branch.

    Args:
        git_root: Absolute path to the worktree's git checkout root.
        wiki_path: Absolute path to the wiki clone root (contains Home.md).
        cfg: Deep-merged config dict (wiki config.yaml + config.local.yaml).

    Returns:
        The validated task slug.

    Raises:
        MarkerError: On detached HEAD, prefix mismatch, missing slug, or
            slug not in [active] phase.
    """
    result = _subprocess_util.run(
        ["git", "-C", str(git_root), "branch", "--show-current"]
    )
    branch = result.stdout.strip()
    if not branch:
        raise MarkerError("detached HEAD or non-branch state")

    prefix = cfg.get("spawn", {}).get("branch_prefix", "")
    if prefix and not branch.startswith(prefix):
        raise MarkerError(
            f"branch {branch!r} does not start with configured prefix {prefix!r}"
        )
    slug = branch.removeprefix(prefix)

    home_text = (wiki_path / "Home.md").read_text(encoding="utf-8")
    tasks = _tasks_md.parse(home_text)

    task = next((t for t in tasks if t.slug == slug), None)
    if task is None:
        raise MarkerError(f"branch slug {slug!r} not present in Home.md")
    if task.phase != "active":
        raise MarkerError(
            f"task {slug!r} is not [active] in Home.md (phase={task.phase!r})"
        )
    return slug


def task_data(git_root: Path, wiki_path: Path, cfg: dict) -> dict:
    """Return task identity data for the current worktree.

    Args:
        git_root: Absolute path to the worktree's git checkout root.
        wiki_path: Absolute path to the wiki clone root (contains Home.md).
        cfg: Deep-merged config dict (wiki config.yaml + config.local.yaml).

    Returns:
        dict with exactly three keys: "slug", "branch", and "task_title".

    Raises:
        MarkerError: When slug_from_branch raises (propagated).
    """
    slug = slug_from_branch(git_root, wiki_path, cfg)

    branch = _subprocess_util.run(
        ["git", "-C", str(git_root), "branch", "--show-current"]
    ).stdout.strip()

    home_text = (wiki_path / "Home.md").read_text(encoding="utf-8")
    tasks = _tasks_md.parse(home_text)
    task = next(t for t in tasks if t.slug == slug)

    return {"slug": slug, "branch": branch, "task_title": task.title}
