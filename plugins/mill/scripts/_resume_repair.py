"""
Small orchestration helper for mill-resume's off-canonical worktree repair.

``mill-resume`` Phase 1b calls this module when it finds a genuine task worktree (``_mill/status.md`` present) that was hand-created outside any mill skill at a non-canonical path and is missing its ``.millhouse``/ ``.wiki`` scaffolding.
The two functions here are the pure orchestration steps that Phase 1b's embedded Python snippets call directly;
they hold no CLI parsing or user-prompting of their own.

Public API:
    check_uncommitted_changes(worktree) -> list[str]
    Return ``_pygit2_util.status_porcelain(worktree, include_untracked=True)``
    verbatim. An empty list means the worktree is clean.
    relocate_and_scaffold(old_worktree, canonical_path, hub_root, wiki_path) -> None
    Idempotent, retry-safe: move the worktree to its canonical path
    (skipped if already there), copy the hub's ``.millhouse/`` state
    in (minus ``wiki``/``active``), and create the ``.wiki`` junction
    (skipped if already present).
"""
from __future__ import annotations

from pathlib import Path

import _junction
import _pygit2_util
import _worktree


def check_uncommitted_changes(worktree: Path) -> list[str]:
    """Return the porcelain status lines for ``worktree`` (empty list == clean)."""
    return _pygit2_util.status_porcelain(worktree, include_untracked=True)


def relocate_and_scaffold(
    old_worktree: Path, canonical_path: Path, hub_root: Path, wiki_path: Path
) -> None:
    """
    Relocate ``old_worktree`` to ``canonical_path`` and scaffold its ``.millhouse``/``.wiki``.

    Idempotent and retry-safe across three independent steps, so calling this again with the same arguments after a partial failure (e.g.
    the move succeeded but a scaffold step didn't) completes only the remaining work rather than re-raising or re-attempting an already-done step:

    1. Move the worktree via ``_worktree.move(old_worktree, canonical_path, cwd=hub_root)`` -- ``hub_root`` is passed as ``cwd`` (not ``old_worktree``) since ``old_worktree`` is the directory being relocated by the very command being run.
        Skipped entirely if ``canonical_path`` is already registered as a worktree (a retry after a prior call's move already succeeded).
    2. Copy the hub's ``.millhouse/`` state into the relocated worktree via ``_worktree.copy_millhouse``, excluding ``wiki``/``active`` (same exclude set mill-spawn uses).
        Runs unconditionally -- already safe to re-run since existing files in the destination are overwritten.
    3. Create the ``.wiki`` junction at ``canonical_path / ".wiki"``, only
    if not already present -- ``_junction.create`` itself raises
    ``ValueError`` on an existing ``link_path``, so this guard is what
    makes the step retry-safe.

    ``hub_root`` MUST be the directory that actually contains ``.millhouse/`` for the hub, resolved by the caller via ``_paths.resolve_hub_path(cwd=_paths.resolve_main_worktree_root(git_root))`` so the resolution never consults ``old_worktree``'s own ``.millhouse/`` (``old_worktree`` is, by construction, the under-scaffolded worktree being relocated) and is ``hub_relative_path``-aware.
    Passing ``_paths.resolve_main_worktree_root``'s result directly, with no ``resolve_hub_path`` step, is NOT sufficient -- it is not ``hub_relative_path``-aware, and ``_worktree.copy_millhouse`` silently no-ops (does not raise) when its ``src`` argument does not exist, turning a wrong ``hub_root`` into a silent empty-``.millhouse`` scaffold rather than a visible error.

    This function does not re-verify cleanliness itself,
    and does not by itself distinguish "canonical_path is a resumable interrupted repair for this same task" from "canonical_path is a genuine collision with an unrelated worktree" -- that distinction is the caller's responsibility (``mill-resume/SKILL.md`` Phase 1b Step 2).

    Raises:
        _worktree.WorktreeError: propagated uncaught from ``move``.
        ValueError: propagated uncaught from ``_junction.create`` when ``link_path`` already exists despite the guard (e.g.
            a non-junction file at that path).
        OSError: propagated uncaught from ``copy_millhouse``.
    """
    # Step 1: move, unless canonical_path is already registered -- an interrupted prior run whose move already succeeded.
    registered_paths = {
        Path(entry["path"]).resolve() for entry in _worktree.list_worktrees(cwd=hub_root)
    }
    if canonical_path.resolve() not in registered_paths:
        _worktree.move(old_worktree, canonical_path, cwd=hub_root)

    # Step 2: propagate hub .millhouse/ state, minus the junction aliases the new worktree recreates for itself.
    # Safe to re-run -- existing files at the destination are overwritten.
    _worktree.copy_millhouse(
        hub_root / ".millhouse", canonical_path / ".millhouse", exclude={"wiki", "active"}
    )

    # Step 3: recreate the .wiki junction, only if not already present.
    wiki_link = canonical_path / ".wiki"
    if not wiki_link.exists():
        _junction.create(wiki_path, wiki_link)
