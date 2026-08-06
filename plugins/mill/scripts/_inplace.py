"""
Detect whether a task is running in-place (no separate worktree directory).

An *in-place* task is one that was claimed via ``mill-claim`` from the hub itself — the task branch
IS the hub's current branch, so ``git_root`` for the running session IS the main worktree root.

``mill-merge`` and ``mill-cleanup`` call ``is_inplace`` to decide whether to run ``git worktree
remove`` (worktree mode) or only ``git branch -d`` (in-place mode).

Public API:
    is_inplace(slug, git_root, cfg) -> bool
    Returns True when ``git_root`` IS the main worktree root (a
    git-topology comparison, not a directory-existence check). The
    slug is already derived from the current branch by the caller
    (via ``_marker.slug_from_branch``), so no branch re-fetch is
    needed here.

    prompt_stale_worktree(slug, worktree_path) -> str
    Interactive numbered prompt for the stale-worktree edge case (branch
    matches cwd AND the worktree directory exists). Returns ``"inplace"``,
    ``"worktree"``, or ``"abort"``.
"""
from __future__ import annotations

import sys
from pathlib import Path

from _paths import resolve_main_worktree_root


def is_inplace(slug: str, git_root: Path, cfg: dict) -> bool:
    """Return True when this task is running in-place (no separate worktree dir).

    Detection criterion: ``git_root`` IS the main worktree root — a git-topology comparison rather
    than a check for directory existence at some canonical path.
    This is immune to the task's worktree having been parked at a non-canonical location (see issue
    #735).

    The slug is already validated against the current branch by the caller via
    ``_marker.slug_from_branch``, so no branch re-fetch is required. ``slug`` and ``cfg`` are
    retained in the signature only for API compatibility with existing call sites — neither
    participates in the check below.

    Args:
        slug: Task slug derived from the current branch name.
        Unused.
        git_root: Absolute path to the hub git checkout.
        cfg: Deep-merged config dict (wiki config.yaml + config.local.yaml).
        Unused.

    Returns:
        True if the task is in-place;
        False otherwise.
    """
    main_root = resolve_main_worktree_root(git_root)
    try:
        return git_root.samefile(main_root)
    except OSError:
        return git_root.resolve() == main_root.resolve()


def prompt_stale_worktree(slug: str, worktree_path: Path) -> str:
    """Prompt the user to resolve the stale-worktree ambiguity.

    Called when the current branch matches the active task's recorded branch AND a worktree
    directory already exists at ``worktree_path``.
    This is ambiguous: the task could legitimately be in-place (the directory is stale) or still
    have a live worktree.

    Presents a numbered list per ``mill:conversation`` conventions:

        1) Abort (Recommended)
        2) Treat as in-place — skip worktree remove
        3) Treat as worktree — run git worktree remove

    Args:
        slug: Task slug; used in the prompt text for clarity.
        worktree_path: Absolute path to the suspected stale worktree dir.

    Returns:
        ``"abort"`` when the user picks 1, ``"inplace"`` when 2, ``"worktree"`` when 3;
        ``"abort"`` also on invalid / EOF input (the fail-safe default).
    """
    print(
        f"[inplace] Stale-worktree ambiguity for {slug!r}:\n"
        f"  Branch matches current cwd AND {worktree_path} exists.\n"
        "Choose how to proceed:",
        file=sys.stderr,
    )
    print("  1) Abort (Recommended)", file=sys.stderr)
    print("  2) Treat as in-place -- skip worktree remove", file=sys.stderr)
    print("  3) Treat as worktree -- run git worktree remove", file=sys.stderr)

    try:
        raw = input("Choice [1/2/3]: ").strip()
    except EOFError:
        print("[inplace] No input available; aborting.", file=sys.stderr)
        return "abort"

    if raw == "1":
        return "abort"
    if raw == "2":
        return "inplace"
    if raw == "3":
        return "worktree"

    print(
        f"[inplace] Unrecognised choice {raw!r}; aborting to be safe.",
        file=sys.stderr,
    )
    return "abort"
