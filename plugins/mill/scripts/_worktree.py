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
    WorktreeLockedError                    — raised when a worktree is in use (NTFS CWD lock or PermissionError).
    create(branch, target, cwd)            — git worktree add -b.
    copy_millhouse(src, dst, exclude)      — copy .millhouse/ minus exclude.
    list_worktrees(cwd) -> list[dict]      — enumerate all worktrees for the repo at cwd.
    remove(path, cwd, force=True) -> None  — remove a registered worktree.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import _pygit2_util
import _safe_rmtree
import _subprocess_util


class WorktreeError(RuntimeError):
    """Raised by ``create`` when ``git worktree add`` fails."""


class WorktreeLockedError(WorktreeError):
    """Raised when a worktree directory cannot be removed because it is in use (NTFS CWD lock, PermissionError, or Windows 'Invalid argument' on locked handles)."""


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
    in ``dst`` are overwritten — mill-spawn owns
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


def list_worktrees(cwd: Path) -> list[dict[str, str | None]]:
    """
    Return all worktrees registered for the repo at ``cwd``.

    Runs ``git worktree list --porcelain`` and parses its output into a
    list of dicts. Each dict has two keys:

    - ``"path"`` — absolute path string from the ``worktree`` line.
    - ``"branch"`` — short branch name (``refs/heads/`` prefix stripped),
      or ``None`` when the block contains a ``detached`` line.

    The main worktree (first block) is included. Callers filter if needed.
    Returns ``[]`` for empty output (bare repo with no worktrees is unusual
    but not an error).

    Raises:
        WorktreeError: git returned non-zero.
    """
    try:
        return _pygit2_util.list_worktrees(cwd)
    except _pygit2_util.GitOpsError as e:
        raise WorktreeError(f"git worktree list failed (cwd={cwd}): {e}") from e


def remove(path: Path, cwd: Path, force: bool = True) -> None:
    """
    Remove a registered worktree at ``path``.

    Runs ``git worktree remove [--force] <path>`` with ``cwd`` set to the
    repo root. With ``force=True`` (default) git removes the worktree even
    if it has untracked or modified files.

    Note: this function does NOT strip junctions. Prefer ``remove_safe`` for
    callers that need long-path fallback or operate on worktrees with
    junctions inside (which is every mill task worktree). This raw form
    exists for callers that have already handled junction-stripping or
    operate on junction-free worktrees.

    Args:
        path: Absolute path to the worktree directory to remove.
        cwd: Repo root from which to invoke ``git`` (same as ``create``).
        force: When True, passes ``--force`` so git removes dirty trees.

    Raises:
        WorktreeError: git returned non-zero.
    """
    cmd = ["git", "-C", str(cwd), "worktree", "remove"]
    if force:
        cmd.append("--force")
    cmd.append(str(path))
    result = _subprocess_util.run(cmd)
    if result.returncode != 0:
        raise WorktreeError(
            f"git worktree remove failed (path={path}): {result.stderr.strip()!r}"
        )
    print(f"[worktree] remove: path={path}", file=sys.stderr)


def remove_safe(
    path: Path,
    cwd: Path,
    junctions_cfg: dict[str, str],
    force: bool = True,
) -> None:
    """
    Junction-safe worktree teardown with long-path fallback.

    Sequence:
        1. Strip every junction declared in ``junctions_cfg`` inside ``path``
           via ``_junction.strip_all_in_worktree``. Mandatory: any subsequent
           recursive removal would otherwise follow `.millhouse/wiki`,
           `.others`, and `.active` and wipe the wiki, the portals dir,
           or sibling worktrees.
        2. Try ``git worktree remove --force``. Junction-safe by design.
        3. If git fails with a long-path error (Windows, common when
           ``.scratch/`` has deep claude session JSONs), fall back to
           ``_safe_rmtree.safe_rmtree`` — safe NOW because junctions are already gone —
           then ``git worktree prune`` to clear git's internal registry.
        4. Any other git failure is re-raised; callers handle "in use"
           messages etc.

    See GitHub issue #100 for the data-loss incident this guards against.

    Args:
        path: Absolute path to the worktree directory to remove.
        cwd: Repo root from which to invoke ``git``.
        junctions_cfg: The ``junctions:`` block from ``mill-config.yaml``,
            as returned by ``_junction.read_junctions``.
        force: Forwarded to ``git worktree remove`` and to the fallback's
            ``_safe_rmtree.safe_rmtree(ignore_errors=...)`` decision.

    Raises:
        WorktreeError: git worktree remove failed for a reason other than long-path or "not a working tree" (e.g., "is in use"), and the fallback was not attempted.
    """
    import _junction

    if path.exists():
        stripped = _junction.strip_all_in_worktree(path, junctions_cfg)
        for abs_link in stripped:
            print(f"[worktree] stripped junction: {abs_link}", file=sys.stderr)

    cmd = ["git", "-C", str(cwd), "worktree", "remove"]
    if force:
        cmd.append("--force")
    cmd.append(str(path))
    result = _subprocess_util.run(cmd)
    if result.returncode == 0:
        print(f"[worktree] remove_safe: removed via git ({path})", file=sys.stderr)
        return

    stderr = result.stderr.strip()
    _rmtree_fallback_patterns = (
        "Filename too long",
        "filename too long",
        "is not a working tree",
        "Directory not empty",   # Windows: nested .scratch/ test fixtures
        "directory not empty",
    )
    rmtree_fallback = any(p in stderr for p in _rmtree_fallback_patterns)
    _lock_patterns = ("Permission denied", "is in use", "Access is denied", "Invalid argument")
    if any(p in stderr for p in _lock_patterns):
        raise WorktreeLockedError(f"worktree is locked (path={path}): {stderr!r}")
    if not rmtree_fallback:
        raise WorktreeError(
            f"git worktree remove failed (path={path}): {stderr!r}"
        )

    # Long-path / not-a-working-tree fallback. Junctions are stripped, so _safe_rmtree is safe.
    print(
        "[worktree] remove_safe: git failed; falling back to _safe_rmtree (junctions already stripped)",
        file=sys.stderr,
    )
    if path.exists():
        try:
            _safe_rmtree.safe_rmtree(path, allowed_root=path)
        except PermissionError as exc:
            raise WorktreeLockedError(
                f"worktree is locked via rmtree fallback (path={path}): {exc}"
            ) from exc

    prune = _subprocess_util.run(
        ["git", "-C", str(cwd), "worktree", "prune"],
    )
    if prune.returncode != 0:
        print(
            f"[worktree] remove_safe: git worktree prune warning: "
            f"{prune.stderr.strip()!r}",
            file=sys.stderr,
        )
    print(f"[worktree] remove_safe: removed via fallback ({path})", file=sys.stderr)


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
