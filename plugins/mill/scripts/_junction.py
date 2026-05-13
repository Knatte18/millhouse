"""
Cross-platform directory-junction helpers.

Mill places junctions inside ``.millhouse/`` to stitch each working clone
to a single shared wiki clone (``.millhouse/wiki``) and to the currently
active task directory (``.millhouse/.active``). We need one abstraction
that works on both Windows (the primary dev platform) and POSIX
(CI, macOS contributors).

Platform mapping:
    * Windows → directory junction, created with ``mklink /J``. Junctions
      are chosen over symlinks because they don't require developer-mode
      or elevation, and because Git for Windows follows them transparently.
    * POSIX   → directory symlink, created with ``os.symlink``.

Public API:
    create(target, link_path)
        Create a junction/symlink at ``link_path`` pointing to ``target``.
        Raises ``ValueError`` if ``link_path`` already exists.

    remove(link_path)
        Remove a junction/symlink at ``link_path``. Idempotent; refuses to
        touch a path that is a regular file or directory to prevent
        accidentally deleting real content.

    points_to(link_path, target) -> bool
        True iff ``link_path`` is a junction/symlink resolving to ``target``.
        Returns False for broken junctions (``OSError`` from ``resolve()``).

    resolve_target(template, tokens)
        Substitute ``<name>`` tokens in a junction target template. Used by
        mill-setup and mill-spawn to turn entries from the wiki config's
        ``junctions:`` block into concrete paths.

    has_slug_token(template)
        True if a target template contains the ``<SLUG>`` task-variable.
        Used to decide scope: present → per-worktree (mill-spawn), absent →
        hub/worktree-wide (mill-setup).
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import _subprocess_util


_TOKEN_RE = re.compile(r"<([A-Za-z][A-Za-z0-9_]*)>")


def resolve_target(template: str, tokens: dict[str, str]) -> str:
    """Substitute ``<NAME>`` tokens in ``template`` using ``tokens``.

    All tokens are UPPERCASE. Path tokens carry a ``_PATH`` suffix
    (``<HUB_PATH>``, ``<WIKI_PATH>``, ...); plain names do not
    (``<REPO>``, ``<SLUG>``). Matching is case-sensitive.

    Raises ``ValueError`` if the template references a token that is not
    in ``tokens``. This is a hard error: mill-setup should surface it so
    the user can correct the config, rather than silently creating a
    junction with a literal ``<UNKNOWN>`` segment in its path.
    """
    missing: list[str] = []

    def _replace(m: re.Match[str]) -> str:
        name = m.group(1)
        if name not in tokens:
            missing.append(name)
            return m.group(0)
        return tokens[name]

    substituted = _TOKEN_RE.sub(_replace, template)
    if missing:
        known = ", ".join(sorted(tokens)) or "(none)"
        raise ValueError(
            f"Unknown token(s) in junction target {template!r}: "
            f"{', '.join(sorted(set(missing)))}. Known tokens: {known}."
        )
    return substituted


def has_slug_token(template: str) -> bool:
    """True if ``template`` contains the ``<SLUG>`` task-variable token."""
    return "<SLUG>" in template


def _is_junction_or_symlink(link_path: Path) -> bool:
    """Return True iff *link_path* is a junction or symlink (never raises).

    Uses ``lexists`` so a broken junction/symlink whose target was deleted is
    still recognised as present rather than silently falling through to the
    "is a regular directory" branch.
    """
    if not os.path.lexists(str(link_path)):
        return False
    if os.name == "nt":
        is_junction = False
        if hasattr(os.path, "isjunction"):
            is_junction = os.path.isjunction(str(link_path))
        else:
            try:
                attrs = os.lstat(str(link_path)).st_file_attributes
                is_junction = bool(attrs & 0x400)
            except (OSError, AttributeError):
                is_junction = False
        return is_junction or os.path.islink(str(link_path))
    else:
        return os.path.islink(str(link_path))


def create(target: Path, link_path: Path) -> None:
    """
    Create a directory junction (Windows) or symlink (POSIX) at ``link_path``.

    The parent of ``link_path`` is created if missing, so callers don't
    have to pre-mkdir ``.millhouse/`` before adding a junction inside it.
    Both arguments should be absolute paths — relative paths work but make
    the resulting junction harder to reason about on Windows.

    Args:
        target: Existing directory the junction will point at.
        link_path: Location where the junction/symlink will be created.
            Must not already exist.

    Raises:
        ValueError: If ``link_path`` already exists as any kind of
            file-system object. The caller is expected to remove stale
            links explicitly (via ``remove``) before creating a new one.
        OSError: If ``mklink /J`` returns non-zero on Windows.
    """
    # Refuse to clobber an existing path. ``is_symlink`` is checked
    # separately because a broken symlink makes ``exists()`` return False.
    if link_path.exists() or link_path.is_symlink():
        raise ValueError(f"{link_path} already exists — remove it before creating a junction")

    # Ensure the parent directory exists. Lets callers create
    # ``.millhouse/.active`` without a separate mkdir step.
    link_path.parent.mkdir(parents=True, exist_ok=True)

    if os.name == "nt":
        # ``mklink /J`` is a cmd.exe builtin and requires backslash-form
        # paths. Forward slashes confuse the parser on some Windows
        # versions, so normalise both ends.
        win_link = str(link_path).replace("/", "\\")
        win_target = str(target).replace("/", "\\")
        result = _subprocess_util.run(
            ["cmd", "/c", "mklink", "/J", win_link, win_target],
        )
        if result.returncode != 0:
            raise OSError(
                f"mklink /J failed (exit {result.returncode}): {result.stderr.strip()}"
            )
        print(f"[junction] created junction {link_path} -> {target}", file=sys.stderr)
    else:
        # POSIX path — plain symlink. No elevation considerations here.
        os.symlink(str(target), str(link_path))
        print(f"[junction] created symlink {link_path} -> {target}", file=sys.stderr)


def remove(link_path: Path) -> None:
    """
    Remove a directory junction (Windows) or symlink (POSIX) at ``link_path``.

    Idempotent: if ``link_path`` does not exist, returns silently. This
    lets mill-cleanup run safely regardless of whether a junction was
    actually created.

    The function never recurses into the target. A regular file or
    non-empty directory at ``link_path`` raises ``ValueError`` rather than
    being silently deleted — this guardrail exists because an earlier
    version of mill once wiped a real ``.millhouse/wiki/`` directory that
    had been promoted to a full clone instead of a junction.

    Args:
        link_path: Path of the junction or symlink to remove.

    Raises:
        ValueError: If ``link_path`` exists but is neither a junction nor
            a symlink.
    """
    if not os.path.lexists(str(link_path)):
        return
    if not _is_junction_or_symlink(link_path):
        raise ValueError(
            f"{link_path} is not a junction or symlink — refusing to remove"
        )
    if os.name == "nt":
        if os.path.islink(str(link_path)):
            os.unlink(str(link_path))
            print(f"[junction] removed symlink {link_path}", file=sys.stderr)
        else:
            os.rmdir(str(link_path))
            print(f"[junction] removed junction {link_path}", file=sys.stderr)
    else:
        os.unlink(str(link_path))
        print(f"[junction] removed symlink {link_path}", file=sys.stderr)


def points_to(link_path: Path, target: Path) -> bool:
    """Return True iff *link_path* is a junction/symlink that resolves to *target*.

    Returns False if *link_path* is not a junction or symlink, or if either
    ``Path.resolve()`` call raises ``OSError`` — this covers broken Windows
    junctions whose target directory was deleted after the junction was created
    (``Path.resolve()`` raises ``OSError`` on such paths rather than returning
    the dangling target path).
    """
    if not _is_junction_or_symlink(link_path):
        return False
    try:
        return link_path.resolve() == target.resolve()
    except OSError:
        return False


def strip_all_in_worktree(worktree_path: Path, junctions_cfg: dict[str, str]) -> list[Path]:
    """
    Unlink every junction declared in ``junctions_cfg`` inside ``worktree_path``.

    This is the mandatory safety prelude to any recursive removal of a
    worktree on Windows. ``rmdir /s`` (cmd.exe) and ``shutil.rmtree``
    (Python) follow NTFS directory junctions by default — running either
    against a worktree without first stripping junctions risks deleting
    the wiki (`.millhouse/wiki -> <WIKI_PATH>`), the portals dir
    (`.others -> <CONTAINER_PATH>/portals/`), or sibling worktrees
    (`.active -> <CONTAINER_PATH>/portals/<SLUG>/`).

    Removes ALL junctions regardless of token scope — both hub-scope
    (no ``<SLUG>``) and per-worktree (with ``<SLUG>``) entries are stripped,
    because mill-spawn creates both inside every task worktree.

    Idempotent: missing junctions are silently skipped via ``remove``.

    Args:
        worktree_path: Absolute path to the worktree being torn down.
        junctions_cfg: The ``junctions:`` block from ``wiki/config.yaml``,
            as returned by ``_wiki.read_junctions``. Caller passes this
            in to avoid a circular import on ``_wiki``.

    Returns:
        List of link paths that were stripped (or attempted; ``remove`` is
        idempotent on missing paths).
    """
    removed: list[Path] = []
    for link_relative in junctions_cfg.keys():
        abs_link = worktree_path / link_relative
        remove(abs_link)
        removed.append(abs_link)
    return removed
