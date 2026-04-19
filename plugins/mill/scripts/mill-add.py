"""
mill-add — append a single task entry to the wiki's Home.md.

Reads the wiki clone path via the `.millhouse/wiki` junction in cwd, acquires
the shared `.mill-lock` (since Home.md is a multi-writer file per
`ref-formats.md`), appends a `## <slug>` section with the given description,
commits and pushes the wiki, then releases the lock.

Slug rules (`Home.schema.md`): kebab-case, must match `[a-z][a-z0-9-]*`,
unique within Home.md. Duplicate slugs are rejected before any write.

Usage:
    python plugins/mill/scripts/mill-add.py <slug> [--description "..."]

Exit codes:
    0 — task added and pushed
    1 — validation, environment, or duplicate-slug error
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import _wiki

_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]*$")


def _validate_slug(slug: str) -> None:
    """Reject anything that is not a valid v2 task slug."""
    if not _SLUG_RE.match(slug):
        raise SystemExit(
            f"Invalid slug {slug!r}: must match [a-z][a-z0-9-]* (kebab-case, lowercase, digits and hyphens)."
        )


def _resolve_wiki_path() -> Path:
    """Return the absolute wiki clone path via the .millhouse/wiki junction."""
    junction = Path(".millhouse/wiki")
    if not junction.exists():
        raise SystemExit(
            "No .millhouse/wiki junction found. Run /mill-setup from this clone first."
        )
    return junction.resolve()


def _has_slug(home_text: str, slug: str) -> bool:
    """True if Home.md already contains a `## <slug>` heading on its own line."""
    pattern = re.compile(rf"^##\s+{re.escape(slug)}\s*$", re.MULTILINE)
    return bool(pattern.search(home_text))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Append a task to the wiki Home.md.")
    parser.add_argument("slug", help="Task slug (kebab-case, e.g. 'fix-foo').")
    parser.add_argument("--description", default="", help="One-line task description (optional).")
    args = parser.parse_args(argv)

    _validate_slug(args.slug)
    wiki_path = _resolve_wiki_path()
    home_path = wiki_path / "Home.md"
    if not home_path.exists():
        raise SystemExit(f"Home.md not found at {home_path}. Run /mill-setup first.")

    # Acquire the shared wiki lock before any read or write — Home.md is a
    # multi-writer file, so another mill-add running concurrently must wait.
    _wiki.acquire_lock(wiki_path, args.slug)
    try:
        home_text = home_path.read_text(encoding="utf-8")
        if _has_slug(home_text, args.slug):
            raise SystemExit(f"Slug {args.slug!r} already present in Home.md.")

        # Ensure trailing newline before appending so the new section is
        # cleanly separated from existing content.
        if not home_text.endswith("\n"):
            home_text += "\n"
        new_section = f"\n## {args.slug}\n\n{args.description}\n"
        home_path.write_text(home_text + new_section, encoding="utf-8")

        _wiki.write_commit_push(wiki_path, ["Home.md"], f"add task: {args.slug}")
    finally:
        _wiki.release_lock(wiki_path)

    print(f"Added task {args.slug!r} to {home_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
