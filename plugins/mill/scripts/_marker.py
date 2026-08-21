"""
Branch-derived slug and task data for the current mill worktree.

Reads the git branch name and validates it against Home.md — no marker file required.
Replaces the subset of _active.read_all that callers need to identify which task this worktree is
working on.

Public API:
    MarkerError Raised on any slug-derivation failure.
    slug_from_branch(git_root: Path, wiki_path: Path, cfg: dict) -> str Derive and validate the slug
    from the current branch name.
    task_data(git_root: Path, wiki_path: Path, cfg: dict) -> dict Return {"slug": str, "branch":
    str, "task_title": str}.
"""
from __future__ import annotations

import sys
from pathlib import Path

import _pygit2_util
from wiki import _client as wiki


class MarkerError(RuntimeError):
    """Raised when slug derivation from branch + Home.md fails."""


def _list_tasks_brief_with_retry(wiki_path: Path) -> list[dict]:
    """Fetch the Home.md task list, retrying once after a cold-daemon wake.

    A machine sleep/resume cycle can leave the wiki daemon's socket stale, so the first
    `list_tasks_brief` call after resume raises `wiki.WikiStartupError` even though the daemon would
    start up fine on a fresh attempt.
    Force a wake via `health_check` and retry exactly once before giving up, since retrying
    indefinitely would mask a genuinely broken daemon.

    Args:
        wiki_path: Absolute path to the wiki clone root.

    Returns:
        List of task dicts, as returned by `wiki.list_tasks_brief`.

    Raises:
        wiki.WikiStartupError: If the daemon is still unreachable after the forced wake-up and
            retry.
            Propagated unwrapped -- callers must not see this collapsed into `MarkerError`.
    """
    try:
        return wiki.list_tasks_brief(wiki_path)
    except wiki.WikiStartupError:
        # Cold daemon: force a wake-up, then retry exactly once.
        wiki.health_check(wiki_path)
        return wiki.list_tasks_brief(wiki_path)


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
        try:
            sha = _pygit2_util.head_sha(git_root)
            matches = _pygit2_util.local_branches_at_sha(git_root, sha)
        except _pygit2_util.GitOpsError:
            raise MarkerError("detached HEAD or non-branch state")
        if matches:
            raise MarkerError(
                f"HEAD is detached at a commit matching branch(es) {', '.join(matches)} -- "
                f"run 'git checkout <name>', or use /mill-resume if this worktree was copied "
                f"from another machine."
            )
        raise MarkerError("detached HEAD or non-branch state")

    prefix = cfg.get("spawn", {}).get("branch_prefix", "")

    tasks = _list_tasks_brief_with_retry(wiki_path)

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

    tasks = _list_tasks_brief_with_retry(wiki_path)
    task = next(t for t in tasks if t["slug"] == slug)

    return {"slug": slug, "branch": branch, "task_title": task["title"]}
