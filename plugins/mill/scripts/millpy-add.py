"""
mill-add — append a task entry to the wiki's Home.md and regenerate the sidebar.

Resolves the wiki clone via ``_paths.resolve_wiki_path``. Note: ``.millhouse/wiki``
is a junction for IDE/terminal convenience only — scripts never use it as a
code path. Acquires the shared `.mill-lock` (Home.md is a multi-writer file per `ref-formats.md`),
appends a `## <Title> [<slug>]` section to Home.md — or `## <Title> [[<slug>]]
(proposal-<slug>)` with a companion ``proposal-<slug>.md`` when
``--proposal-body`` is given — then regenerates `_Sidebar.md` and commits all
wiki changes in ONE commit. Finally releases the lock and exits.

Slug rules (``Home.schema.md``): kebab-case matching ``[a-z][a-z0-9-]*``,
unique within Home.md. Duplicate slugs are rejected before any write.

Proposals live at wiki root as ``proposal-<slug>.md`` (flat namespace, per
``ref-formats.md`` — GitHub Wiki does not render subdirectory pages
reliably).

Usage:
    python plugins/mill/scripts/mill-add.py <slug> \\
        --title "Human-readable title" \\
        [--summary "one-paragraph summary for Home.md"] \\
        [--proposal-body "long-form background"]

Exit codes:
    0 — task added and pushed
    1 — validation, environment, or duplicate-slug error
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from wiki import _client as wiki
from _paths import resolve_git_root, resolve_wiki_path

_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]*$")


def _validate_slug(slug: str) -> None:
    """Reject anything that is not a valid task slug."""
    if not _SLUG_RE.match(slug):
        raise SystemExit(
            f"Invalid slug {slug!r}: must match [a-z][a-z0-9-]* "
            "(kebab-case, lowercase, digits and hyphens)."
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Append a task to the wiki Home.md (with optional proposal)."
    )
    parser.add_argument(
        "slug",
        help="Task slug — kebab-case, e.g. 'fix-foo'. Must be unique in Home.md.",
    )
    parser.add_argument(
        "--title",
        required=True,
        help="Human-readable task title shown as the heading.",
    )
    parser.add_argument(
        "--summary",
        default="",
        help="One-paragraph description written below the heading.",
    )
    body_group = parser.add_mutually_exclusive_group()
    body_group.add_argument(
        "--proposal-body",
        default=None,
        help=(
            "Long-form background as inline string. When provided, creates "
            "proposal-<slug>.md at wiki root and links the heading to it. "
            "For long bodies that may contain heredoc-fragile characters "
            "(backticks, quotes), prefer --proposal-body-file."
        ),
    )
    body_group.add_argument(
        "--proposal-body-file",
        default=None,
        type=Path,
        help=(
            "Path to a UTF-8 file whose contents become the proposal body. "
            "Use this for long bodies — it bypasses shell heredoc quoting "
            "issues that mangle backticks and quotes."
        ),
    )
    args = parser.parse_args(argv)

    if args.proposal_body_file is not None:
        if not args.proposal_body_file.exists():
            raise SystemExit(
                f"--proposal-body-file path does not exist: {args.proposal_body_file}"
            )
        proposal_body = args.proposal_body_file.read_text(encoding="utf-8")
    else:
        proposal_body = args.proposal_body

    _validate_slug(args.slug)
    git_root = resolve_git_root()
    wiki_path = resolve_wiki_path(git_root)
    home_path = wiki_path / "Home.md"
    if not home_path.exists():
        raise SystemExit(
            f"Wiki not found at {wiki_path}. Run /mill-setup to create it, "
            "or set paths.wiki: in .millhouse/config.local.yaml."
        )

    has_proposal = proposal_body is not None
    proposal_path = wiki_path / f"proposal-{args.slug}.md"
    # Guard against clobbering an existing proposal file even when the slug is
    # absent from Home.md (can happen after a bad abort): we'd overwrite the
    # user's content otherwise.
    if has_proposal and proposal_path.exists():
        raise SystemExit(
            f"Proposal file {proposal_path} already exists; refusing to overwrite."
        )

    # Check for duplicate slug before upserting
    existing = wiki.get_task(wiki_path, args.slug)
    if existing is not None:
        raise SystemExit(f"Slug {args.slug!r} already present in Home.md.")

    # Normalize proposal body: strip trailing newline and re-add exactly one
    body = None
    if has_proposal:
        body = proposal_body.rstrip("\n") + "\n"

    # Upsert the task. The daemon commits and renders automatically.
    wiki.upsert_task(
        wiki_path,
        args.slug,
        title=args.title,
        brief=args.summary,
        body=body,
    )

    print(f"Added task {args.slug!r} to {home_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
