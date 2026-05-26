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

import sys
from pathlib import Path

import _pygit2_util
from wiki import _client as wiki


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
        MarkerError: On detached HEAD, prefix mismatch, or missing slug.
    """
    try:
        branch = _pygit2_util.current_branch(git_root)
    except _pygit2_util.GitOpsError as e:
        raise MarkerError(f"could not read branch in {git_root}: {e}") from e
    if branch is None:
        raise MarkerError("detached HEAD or non-branch state")

    prefix = cfg.get("spawn", {}).get("branch_prefix", "")

    tasks = wiki.list_tasks_brief(wiki_path)

    if prefix and not branch.startswith(prefix):
        task = next((t for t in tasks if t["slug"] == branch), None)
        if task is not None:
            print(f"[_marker] warning: branch {branch!r} does not match prefix {prefix!r} but slug exists in Home.md; accepting", file=sys.stderr)
            return branch
        raise MarkerError(f"branch {branch!r} does not start with configured prefix {prefix!r} and is not a known slug")
    slug = branch.removeprefix(prefix)

    task = next((t for t in tasks if t["slug"] == slug), None)
    if task is None:
        if "/" in branch and not prefix:
            stripped_slug = branch.split("/", 1)[1]
            task = next((t for t in tasks if t["slug"] == stripped_slug), None)
            if task is not None:
                return stripped_slug
            raise MarkerError(f"branch slugs {slug!r} and {stripped_slug!r} not found in Home.md")
        raise MarkerError(f"branch slug {slug!r} not present in Home.md")
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

    try:
        branch = _pygit2_util.current_branch(git_root) or ""
    except _pygit2_util.GitOpsError as e:
        raise MarkerError(f"could not read branch in {git_root}: {e}") from e

    tasks = wiki.list_tasks_brief(wiki_path)
    task = next(t for t in tasks if t["slug"] == slug)

    return {"slug": slug, "branch": branch, "task_title": task["title"]}
