"""
Git-worktree creation and per-worktree state propagation.

mill-spawn creates a new worktree for every claimed task. Two pieces of
work sit behind a tiny API here:

    1. ``create`` — run ``git worktree add -b <branch> <target>`` in the
       repo the caller is in. This is the only place that calls the git
       CLI for worktree creation so the command's error surface is
       consistent (callers get ``WorktreeError`` on any non-zero exit).

    2. ``copy_millhouse`` — propagate per-clone ``.millhouse/`` state
       into the new worktree, minus directories that would alias wiki
       state (``wiki/``, ``active/``). We explicitly do NOT copy
       junctions — the new worktree recreates its own junction set via
       ``_junction.create``. (Scratch state lives at ``<cwd>/.scratch/``
       per ``CLAUDE.md ## Path invariants`` and is outside ``.millhouse/``
       entirely, so it is never propagated by this helper.)

Public API:
    WorktreeError                          — raised on any git failure.
    create(branch, target, cwd)            — git worktree add -b.
    copy_millhouse(src, dst, exclude)      — copy .millhouse/ minus exclude.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import _subprocess_util


class WorktreeError(RuntimeError):
    """Raised by ``create`` when ``git worktree add`` fails."""


def create(branch: str, target: Path, cwd: Path) -> None:
    """
    Create a new worktree at ``target`` on a fresh branch ``branch``.

    Runs ``git worktree add -b <branch> <target>`` with ``cwd`` set to
    the caller's repo root. The parent directory of ``target`` must
    exist; the worktree path itself must NOT exist (git would refuse
    otherwise).

    Args:
        branch: New branch name, e.g. ``"hanf/fix-widget"``. Passed
            verbatim; the caller is responsible for any prefix logic.
        target: Absolute path where the worktree should live. Typically
            a sibling of the git toplevel (``<repo>.worktrees/<slug>``).
        cwd: Directory from which to invoke ``git`` — must be inside the
            target repository so ``git worktree`` knows which repo to
            attach the new worktree to.

    Raises:
        WorktreeError: ``git worktree add`` returned non-zero. The
            exception message includes the captured stderr for the user
            to inspect (most common cause: target path already exists).
    """
    result = _subprocess_util.run(
        ["git", "-C", str(cwd), "worktree", "add", "-b", branch, str(target)],
    )
    if result.returncode != 0:
        raise WorktreeError(
            f"git worktree add failed (branch={branch!r}, target={target}): "
            f"{result.stderr.strip()!r}"
        )
    print(f"[worktree] create: branch={branch!r} target={target}", file=sys.stderr)


def copy_millhouse(src: Path, dst: Path, exclude: set[str]) -> None:
    """
    Copy contents of ``src`` (a ``.millhouse/`` directory) into ``dst``.

    Entries whose basename is in ``exclude`` are skipped. Existing files
    in ``dst`` are overwritten — v2's contract is that mill-spawn owns
    the new worktree's ``.millhouse/`` until it hands it back.

    The caller passes the exclude set explicitly so different callers
    (mill-spawn vs. future mill-revise-home / tests) can drop different
    subsets without this module needing policy decisions.

    Args:
        src: Source ``.millhouse/`` directory in the parent worktree.
        dst: Destination ``.millhouse/`` directory in the new worktree.
            Created if missing.
        exclude: Names (NOT paths) to skip. Typical mill-spawn call:
            ``{"wiki", "active"}`` (junction aliases that must not be
            copied).
    """
    dst.mkdir(parents=True, exist_ok=True)
    if not src.exists():
        return
    for item in src.iterdir():
        if item.name in exclude:
            continue
        # Skip junctions/symlinks — the new worktree creates its own via
        # _junction.create. copy_millhouse should never follow a junction
        # because that would pull the wiki clone (or worse, the previous
        # task's active dir) into the new worktree.
        if item.is_symlink() or _is_windows_junction(item):
            continue
        target = dst / item.name
        if item.is_dir():
            shutil.copytree(str(item), str(target), dirs_exist_ok=True)
        else:
            shutil.copy2(str(item), str(target))


def _is_windows_junction(path: Path) -> bool:
    """
    True if ``path`` is a directory junction on Windows.

    ``Path.is_symlink`` returns False for junctions (they are reparse
    points, not symlinks), so we probe the reparse attribute directly.
    On POSIX this always returns False — junctions do not exist there
    and ``is_symlink`` already catches the symlink case.
    """
    if sys.platform != "win32":
        return False
    try:
        import stat as _stat
        return bool(path.lstat().st_file_attributes & _stat.FILE_ATTRIBUTE_REPARSE_POINT)  # type: ignore[attr-defined]
    except (OSError, AttributeError):
        return False
