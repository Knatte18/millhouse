"""
Sibling-path resolver: maps a (role, repo_root) pair to the canonical
location of an adjacent sibling directory or repo.

Container-form vs prefix-form
------------------------------
If ``repo_root.parent.name == "wts"`` (exact, case-sensitive), the repo
is in *container-form*: the main worktree lives at
``<container>/wts/<repo-name>/`` and siblings live next to ``wts/``.

    <container>/wts/
    <container>/wiki/
    <container>/codeguide/
    <container>/portals/

Otherwise (*prefix-form*) siblings carry the repo's name as a prefix so
multiple repos can share the same parent directory without collision.

    <container>/foo/
    <container>/foo.worktrees/
    <container>/foo.wiki/
    <container>/foo.codeguide/

Container-form detection is deliberately literal — ``Wts/`` or ``WTS/``
fall through to prefix-form. Zero heuristics keeps the rule predictable.
Old hub-form (``repo_root.name == "hub"``) is intentionally no longer
recognised; it falls through to prefix-form and produces ``hub.wiki``,
``hub.worktrees``, etc. Run ``millpy-migrate-layout.py`` to upgrade.

Identical-twin rule
-------------------
``plugins/codeguide/scripts/_sibling.py`` is a byte-for-byte copy of
this module (modulo plugin-specific docstring). If you change one,
grep for the other and apply the same change. Each plugin carries
its own copy so neither imports across plugin boundaries (plugin
install paths are not guaranteed to be relative siblings).

Usage
-----
Python::

    from _sibling import resolve_path
    resolve_path("wiki", Path("/c/Code/wts/millhouse"))
    # -> Path("/c/Code/wiki")

CLI (for SKILL.md prose / subprocess callers)::

    python _sibling.py wiki /c/Code/wts/millhouse
    # prints: /c/Code/wiki
"""
from __future__ import annotations

import sys
from pathlib import Path


def resolve_path(role: str, repo_root: Path) -> Path:
    repo_root = Path(repo_root)
    if repo_root.name == "wiki":
        raise ValueError("resolve_path called from wiki repo — wiki cannot resolve its own wiki path")
    parent = repo_root.parent
    if parent.name == "wts":
        # Container-form: main worktree is <container>/wts/<repo-name>;
        # siblings live next to wts/, not next to <repo-name>.
        return parent.parent / role
    # Prefix-form: <container>/<repo-name>; siblings carry repo-name prefix.
    return parent / f"{repo_root.name}.{role}"


def _main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: _sibling.py <role> <repo_root>", file=sys.stderr)
        return 2
    role = argv[1]
    repo_root = Path(argv[2])
    print(resolve_path(role, repo_root))
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
