"""
Central safe-rmtree helper for mill.

Exposes safe_rmtree(path, *, allowed_root, ignore_errors=False) as the single
audited entry point for recursive directory deletion in mill scripts and tests.

Guards against the wiki-wipe incident (GitHub issue #100): shutil.rmtree on a
worktree that still contains NTFS directory junctions follows those junctions
into shared state (wiki, portals, hub root). This helper walks the tree first,
stripping every junction and symlink via _junction.remove, then calls
shutil.rmtree on the cleaned tree.

Hard refusals (SystemExit) protect the four shared-state paths derived from
the millhouse container layout: the container root, container/wiki,
container/portals, and container/wts/<main-repo-name>.

Relationship to _junction.strip_all_in_worktree: that function is config-driven
named-junction CRUD (used by mill-cleanup for the predictable .wiki/.active set).
This helper is FS-level walk-and-detect, independent of junctions_cfg.
Complementary, not duplicate.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import _junction
import _paths


def _is_reparse_point(p: Path) -> bool:
    if os.name != "nt":
        return False
    if hasattr(os.path, "isjunction"):
        return os.path.isjunction(str(p))
    try:
        attrs = os.lstat(str(p)).st_file_attributes
        return bool(attrs & 0x400)
    except (OSError, AttributeError):
        return False


def _walk_strip_reparse_points(root: Path) -> None:
    with os.scandir(str(root)) as it:
        for entry in it:
            ep = Path(entry.path)
            if entry.is_symlink() or _is_reparse_point(ep):
                _junction.remove(ep)
                continue
            if entry.is_dir(follow_symlinks=False):
                _walk_strip_reparse_points(ep)


def _blacklist_for(allowed_root: Path) -> list[Path]:
    try:
        container = _paths.resolve_container_path(allowed_root)
    except (Exception, SystemExit):
        return []
    return [
        container.resolve(),
        (container / "wiki").resolve(),
        (container / "portals").resolve(),
        (container / "wts" / container.name).resolve(),
    ]


def safe_rmtree(path: Path, *, allowed_root: Path, ignore_errors: bool = False) -> None:
    """Remove a directory tree safely, stripping junctions/symlinks before deletion.

    Args:
        path: Directory to remove. Must not itself be a junction or symlink.
        allowed_root: Containment scope declared by the caller. path must equal
            allowed_root or be a descendant of it.
        ignore_errors: When True, OSError from shutil.rmtree is suppressed.
            When False (default), errors propagate to the caller.

    Refusal cases (all raise SystemExit):
        - path is a symlink: "[safe-rmtree] path is itself a symlink -- use _junction.remove instead: <path>"
        - path is a junction: "[safe-rmtree] path is itself a junction -- use _junction.remove instead: <path>"
        - resolved path matches or is an ancestor of a blacklisted shared-state path
          (container root, wiki, portals, main-repo worktree):
          "[safe-rmtree] refuses to delete shared-state path: <path>"
        - resolved path is outside allowed_root:
          "[safe-rmtree] path outside allowed_root: <path>"

    Strip-then-rmtree sequence:
        1. Validate path is not itself a junction or symlink.
        2. Check resolved path against blacklist and allowed_root.
        3. If path does not exist, return silently (no-op).
        4. Walk tree stripping all junctions/symlinks via _junction.remove.
        5. Call shutil.rmtree.

    Platform differences:
        _is_reparse_point is a no-op on POSIX (always returns False).
        entry.is_symlink() runs cross-platform -- POSIX symlinks inside a tree
        are stripped before shutil.rmtree, keeping cross-platform behaviour symmetric.
    """
    print(f"[safe-rmtree] starting: path={path} allowed_root={allowed_root}", file=sys.stderr)

    original = Path(path)

    # Steps 2-3: junction/symlink check BEFORE resolve (see module docstring).
    if original.is_symlink():
        raise SystemExit(
            f"[safe-rmtree] path is itself a symlink -- use _junction.remove instead: {original}"
        )
    if _is_reparse_point(original):
        raise SystemExit(
            f"[safe-rmtree] path is itself a junction -- use _junction.remove instead: {original}"
        )

    # Steps 4-5: resolve for containment and blacklist checks.
    resolved_path = original.resolve()
    resolved_allowed = Path(allowed_root).resolve()

    blacklist = _blacklist_for(allowed_root)
    for entry in blacklist:
        if resolved_path == entry or resolved_path in entry.parents:
            raise SystemExit(
                f"[safe-rmtree] refuses to delete shared-state path: {original}"
            )

    if resolved_path != resolved_allowed and resolved_allowed not in resolved_path.parents:
        raise SystemExit(
            f"[safe-rmtree] path outside allowed_root: {original}"
        )

    # Step 6: silent no-op when path does not exist.
    if not original.exists() and not original.is_symlink():
        return

    # Step 7: strip junctions/symlinks recursively before rmtree.
    _walk_strip_reparse_points(original)

    # Step 8: rmtree with defense-in-depth for ignore_errors.
    try:
        shutil.rmtree(str(original), ignore_errors=ignore_errors)
    except OSError:
        if not ignore_errors:
            raise

    print(f"[safe-rmtree] removed: {resolved_path}", file=sys.stderr)
