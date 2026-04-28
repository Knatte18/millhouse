"""
mill-list — print the tasks in the wiki's Home.md, one per line.

Resolves the wiki clone via ``_paths.resolve_wiki_path`` (``.millhouse/wiki``
is a junction for IDE/terminal convenience only — scripts never use it as a
code path). Parses task headings out of ``Home.md`` using the shared helper in ``_sidebar``, and
prints one line per task. A leading ``[P]`` marker appears when a matching
``proposal-<slug>.md`` exists at wiki root; the marker column is padded so
tasks without a proposal still line up with those that have one.

No wiki lock is taken — this is a read-only command and Home.md is a
regular file that any concurrent writer will replace atomically (git's own
fsync guarantees). The worst case under a race is that we print the version
of Home.md that existed when we opened it; the caller can just re-run.

Usage:
    python plugins/mill/scripts/mill-list.py

Exit codes:
    0 — tasks printed (possibly zero of them)
    1 — environment error (no junction, Home.md missing)
"""
from __future__ import annotations

import sys
from pathlib import Path

import _sidebar
from _paths import resolve_git_root, resolve_wiki_path


def main(argv: list[str] | None = None) -> int:
    # argv is accepted for symmetry with mill-add and future entrypoint-style
    # calls even though mill-list takes no arguments today.
    del argv

    git_root = resolve_git_root()
    wiki_path = resolve_wiki_path(git_root)
    home_path = wiki_path / "Home.md"
    if not home_path.exists():
        raise SystemExit(
            f"Wiki not found at {wiki_path}. Run /mill-setup to create it, "
            "or set paths.wiki: in .millhouse/config.local.yaml."
        )

    tasks = _sidebar.parse_home_tasks(home_path)
    if not tasks:
        print("(no tasks)")
        return 0

    # Same source-of-truth check as _sidebar.regenerate: the presence of a
    # proposal-<slug>.md file on disk at wiki root is what decides the [P]
    # marker, not the heading form. Keeps the marker honest when a heading
    # uses the linked form but the proposal file was later deleted.
    proposal_slugs = {
        p.stem[len("proposal-"):]
        for p in wiki_path.glob("proposal-*.md")
    }

    # Pad the slug column to the longest slug so the title column aligns
    # regardless of slug length. Fixed two-space gutter after the slug.
    slug_width = max(len(task["slug"]) for task in tasks)

    for task in tasks:
        marker = "[P]" if task["slug"] in proposal_slugs else "   "
        slug_padded = task["slug"].ljust(slug_width)
        print(f"{marker} {slug_padded}  {task['title']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
