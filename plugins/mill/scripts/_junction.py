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
    # Absent path is a no-op. Checking ``is_symlink`` covers the broken-
    # symlink case where ``exists()`` alone returns False.
    if not link_path.exists() and not link_path.is_symlink():
        return

    if os.name == "nt":
        # Determine whether this is actually a junction before touching
        # it. ``os.path.isjunction`` only exists on Python 3.12+; on 3.10
        # and 3.11 we inspect FILE_ATTRIBUTE_REPARSE_POINT (0x400) via
        # ``os.lstat``'s Windows-only ``st_file_attributes`` field.
        is_junction = False
        if hasattr(os.path, "isjunction"):
            is_junction = os.path.isjunction(str(link_path))
        else:
            try:
                attrs = os.lstat(str(link_path)).st_file_attributes
                is_junction = bool(attrs & 0x400)
            except (OSError, AttributeError):
                is_junction = False

        if is_junction:
            # Junctions are directory entries — remove with rmdir, not unlink.
            os.rmdir(str(link_path))
            print(f"[junction] removed junction {link_path}", file=sys.stderr)
        elif os.path.islink(str(link_path)):
            # Plain symlink (rare on Windows but possible in dev-mode setups).
            os.unlink(str(link_path))
            print(f"[junction] removed symlink {link_path}", file=sys.stderr)
        else:
            # Regular file or directory — refuse. See docstring for why.
            raise ValueError(
                f"{link_path} is not a junction or symlink — refusing to remove"
            )
    else:
        if os.path.islink(str(link_path)):
            os.unlink(str(link_path))
            print(f"[junction] removed symlink {link_path}", file=sys.stderr)
        else:
            raise ValueError(
                f"{link_path} is not a symlink — refusing to remove"
            )


if __name__ == "__main__":
    print("Usage: import _junction; _junction.create(target, link_path); _junction.remove(link_path)", file=sys.stderr)
    sys.exit(0)
