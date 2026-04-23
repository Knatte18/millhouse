"""
Sibling-path resolver: maps a (role, repo_root) pair to the canonical
location of an adjacent sibling directory or repo.

Hub-form vs prefix-form
-----------------------
If ``repo_root.name == "hub"`` (exact, case-sensitive), the repo is in
*hub-form*: siblings live as bare names next to it.

    <container>/hub/
    <container>/worktrees/
    <container>/wiki/
    <container>/codeguide/

Otherwise (*prefix-form*) siblings carry the repo's name as a prefix so
multiple repos can share the same parent directory without collision.

    <container>/foo/
    <container>/foo.worktrees/
    <container>/foo.wiki/
    <container>/foo.codeguide/

Hub-form detection is deliberately literal — ``Hub/`` or ``HUB/`` fall
through to prefix-form. Zero heuristics keeps the rule predictable.

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
    resolve_path("worktrees", Path("/c/Code/millhouse/hub"))
    # -> Path("/c/Code/millhouse/worktrees")

CLI (for SKILL.md prose / subprocess callers)::

    python _sibling.py worktrees /c/Code/millhouse/hub
    # prints: /c/Code/millhouse/worktrees
"""
from __future__ import annotations

import sys
from pathlib import Path


def resolve_path(role: str, repo_root: Path) -> Path:
    repo_root = Path(repo_root)
    parent = repo_root.parent
    if repo_root.name == "hub":
        return parent / role
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
