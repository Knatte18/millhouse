"""Detect and restore deleted tracked files under a subtree (e.g. _mill/)."""
from __future__ import annotations

import sys
from pathlib import Path

import _pygit2_util
import _subprocess_util
import _timestamp

# Porcelain status codes that represent a genuine deletion: worktree-deleted (" D") and staged-deleted ("D ").
# Every other code (untracked, modified, etc.) is left untouched -- see _mill/discussion.md's Testing section and 00-overview.md's "status codes and path-matching mirror _cleanliness.py's existing partition logic" Decision.
_DELETED_STATUS_CODES = frozenset({" D", "D "})


def _rebase_onto_hub(raw_path: str, hub_prefix: str) -> str | None:
    """Rebase a git-root-relative porcelain path onto the hub root.

    _pygit2_util.status_porcelain always returns paths relative to the git repository toplevel, never to whatever path was passed to it -- see _cleanliness.compute_scope_violations's docstring for this exact behavior.
    When hub_prefix is empty (flat layout, or git_root=None), raw_path passes through unchanged.
    Otherwise raw_path is dropped (returns None) unless it equals hub_prefix or starts with hub_prefix + "/", in which case the hub-relative remainder is returned.

    This mirrors _cleanliness.revert_out_of_scope_drift's private _rebase_onto_hub closure (_cleanliness.py:374-384) -- reimplemented here as a module-local helper since that closure is private to _cleanliness.py.
    """
    if not hub_prefix:
        return raw_path
    if raw_path != hub_prefix and not raw_path.startswith(hub_prefix + "/"):
        return None
    return raw_path[len(hub_prefix) + 1 :] if raw_path != hub_prefix else ""


def check_and_restore(worktree: Path, tracked_root: str = "_mill", *, git_root: Path | None = None) -> dict:
    """
    Detect deleted tracked files under tracked_root and restore them from HEAD.

    Queries whole-repo porcelain status via _pygit2_util.status_porcelain, rebases each git-root-relative path onto the hub (a no-op when git_root is None, i.e.
    a flat layout),
    and filters to lines whose hub-relative path is under tracked_root.
    Among those, only the two deletion status codes (" D" worktree-deleted, "D " staged-deleted) are treated as candidates for restore -- untracked ("??")
    and modified (" M"/"M "/"MM") lines are left completely alone, so a legitimate uncommitted edit is never swept into the restore.

    When there is nothing to restore, no subprocess call is made at all.
    Otherwise a single `git checkout HEAD -- <paths>` call restores every candidate in one shot,
    and the actual outcome is verified per path via on-disk existence checks rather than trusting the subprocess's overall return code -- git can partially succeed (some pathspecs restored, others not) while still reporting a non-zero exit.
    A restore that recovers nothing at all is reported as triggered: False, since callers treat that field as "a restore genuinely happened".

    Args:
        worktree: The hub root to operate against (never read from cwd()).
        tracked_root: Hub-relative subtree to guard, e.g. "_mill".
        git_root: The git repository toplevel, when it differs from worktree (nested-hub layout).
            None means either a flat layout or a caller that never resolved a git_root -- both behave identically (hub_prefix = "").

    Returns:
        A dict with keys "triggered" (bool), "restored_paths" (list[str], hub-relative, sorted), and "timestamp" (str | None, ISO-8601 UTC, set only when triggered is True).
    """
    lines = _pygit2_util.status_porcelain(worktree, include_untracked=False)

    # Compute the hub_prefix using the same technique as _cleanliness.revert_out_of_scope_drift: empty for a flat layout (git_root is None or equals worktree) or an unresolved git_root.
    if git_root is None:
        hub_prefix = ""
    else:
        hub_prefix = worktree.relative_to(git_root).as_posix()
        if hub_prefix == ".":
            hub_prefix = ""

    # Rebase each porcelain line onto the hub, then keep only the deletion lines whose hub-relative path falls under tracked_root.
    deleted_paths = []
    for line in lines:
        status_code = line[:2]
        raw_path = line[3:]

        path = _rebase_onto_hub(raw_path, hub_prefix)
        if path is None:
            # Belongs to a different subtree of the git root entirely.
            continue

        in_scope = path == tracked_root or path.startswith(tracked_root + "/")
        if not in_scope:
            continue

        if status_code in _DELETED_STATUS_CODES:
            deleted_paths.append(path)

    # Nothing deleted under tracked_root -- no git invocation needed.
    if not deleted_paths:
        return {"triggered": False, "restored_paths": [], "timestamp": None}

    # Restore every candidate in one shot.
    result = _subprocess_util.run(
        ["git", "checkout", "HEAD", "--", *deleted_paths],
        cwd=worktree,
    )

    # Verify the actual outcome per path -- a non-zero returncode does not necessarily mean every pathspec failed,
    # and a zero returncode does not guarantee every pathspec succeeded either.
    restored_paths = [path for path in deleted_paths if (worktree / path).exists()]

    still_missing = set(deleted_paths) - set(restored_paths)
    if still_missing:
        # Sanitize stderr and path list to ASCII only (Windows cp1252 crash risk).
        stderr_ascii = result.stderr.encode("ascii", errors="replace").decode("ascii")
        paths_ascii = str(sorted(still_missing)).encode("ascii", errors="replace").decode("ascii")
        print(
            f"[treeguard] failed to restore: {paths_ascii}; "
            f"git checkout stderr: {stderr_ascii}",
            file=sys.stderr,
        )

    # A total restore failure must never be reported as triggered: True -- callers log restored_paths as "a restore actually happened".
    if not restored_paths:
        return {"triggered": False, "restored_paths": [], "timestamp": None}

    return {
        "triggered": True,
        "restored_paths": sorted(restored_paths),
        "timestamp": _timestamp.now_utc_iso(),
    }
