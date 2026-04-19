"""
Regenerate ``wiki/_Sidebar.md`` from ``Home.md`` + the set of proposal files.

The wiki sidebar is a static navigation panel GitHub Wiki renders next to every
page. We keep it authored so every wiki-mutating command (``mill-add`` today,
``mill-merge``/``mill-abandon``/``mill-groom`` in Layer 04) can rewrite it from
the current state of ``Home.md``. Per ``ref-formats.md`` the canonical shape is
a Navigation section first and a Tasks section after. Tasks get a link when a
matching ``proposal-<slug>.md`` file exists at wiki root, and stay as plain
text otherwise — this matters because GitHub Wiki does not render markdown
pages in subdirectories reliably, so proposals live in the flat wiki root.

The regenerator is intentionally idempotent: callers hold the wiki lock around
it (we do not acquire a lock ourselves), pass in the wiki clone path, and
commit the resulting ``_Sidebar.md`` alongside whatever else they changed in
the same commit. It performs no git operations.

Public API:
    parse_home_tasks(home_path) -> list[dict]
        Return ``[{"slug": ..., "title": ...}, ...]`` for every ``## <Title>
        [<slug>]`` heading in ``Home.md``. Preserves document order.
    render_sidebar(tasks) -> str
        Render the ``_Sidebar.md`` body. Each task dict must carry
        ``slug``, ``title`` and ``has_proposal`` — the flag decides whether
        the entry is a link or plain text.
    regenerate(wiki_path) -> None
        Top-level entry: read ``Home.md``, detect ``proposal-*.md`` files at
        wiki root, write ``_Sidebar.md``. No commit, no push, no lock.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Single regex parses both heading forms per ``ref-formats.md``:
#   ## <Title> [<slug>]                         -> plain (no proposal)
#   ## <Title> [[<slug>]](proposal-<slug>)      -> linked (proposal exists)
# Group 1 = human-readable title, group 2 = kebab-case slug. The inner ``[?``
# and ``]?`` make the extra brackets of the linked form optional; the trailing
# ``(?:\([^)]+\))?`` consumes the ``(proposal-<slug>)`` link target when
# present. Anchored to start-of-line + end-of-line (multiline mode at call
# site) so prose body lines cannot masquerade as task headings.
_TASK_HEADING_RE = re.compile(
    r"^##\s+(.+?)\s+\[\[?([a-z][a-z0-9-]*)\]?\](?:\([^)]+\))?\s*$",
    re.MULTILINE,
)


def parse_home_tasks(home_path: Path) -> list[dict]:
    """
    Extract task entries from ``Home.md``.

    Scans the file for every ``## <Title> [<slug>]`` or
    ``## <Title> [[<slug>]](proposal-<slug>)`` heading and returns them in
    document order. The heading is the only source of truth for a task's slug
    and title — body text beneath the heading is ignored.

    Args:
        home_path: Path to the wiki's ``Home.md``. Read as UTF-8.

    Returns:
        List of ``{"slug": str, "title": str}`` dicts, ordered as they
        appear in ``Home.md``. Empty list if no task headings match.
    """
    text = home_path.read_text(encoding="utf-8")
    return [
        {"title": match.group(1).strip(), "slug": match.group(2)}
        for match in _TASK_HEADING_RE.finditer(text)
    ]


def render_sidebar(tasks: list[dict]) -> str:
    """
    Render ``_Sidebar.md`` content from parsed + enriched task list.

    Each task dict must carry three keys: ``slug``, ``title``, and
    ``has_proposal``. ``has_proposal`` controls link vs. plain-text rendering
    of the entry in the Tasks section. The Navigation section is fixed — it
    currently just points at ``Home`` — so the function accepts only the task
    list and hard-codes the nav items.

    Args:
        tasks: List of dicts with ``slug``, ``title``, ``has_proposal``.
            Order is preserved in the rendered output.

    Returns:
        The complete ``_Sidebar.md`` body as a single string, terminated
        with a trailing newline.
    """
    lines: list[str] = [
        "### Navigation",
        "",
        "- [Home](Home)",
        "",
        "### Tasks",
        "",
    ]
    for task in tasks:
        if task["has_proposal"]:
            lines.append(f"- [{task['title']}](proposal-{task['slug']})")
        else:
            lines.append(f"- {task['title']}")
    lines.append("")  # trailing newline
    return "\n".join(lines)


def regenerate(wiki_path: Path) -> None:
    """
    Rewrite ``<wiki_path>/_Sidebar.md`` from ``Home.md`` + on-disk proposals.

    Reads ``Home.md``, parses out every task heading, then checks the wiki
    root for matching ``proposal-<slug>.md`` files to decide which entries
    should be rendered as links. The file-on-disk check is the authority:
    if the heading uses the linked form but the proposal file is missing the
    entry renders as plain text, and vice versa. This keeps the sidebar
    accurate even if a caller forgot to update the heading.

    The function performs no git operations. Callers are expected to already
    hold the wiki lock and commit the resulting ``_Sidebar.md`` alongside
    their own wiki writes in the same commit.

    Args:
        wiki_path: Directory containing the wiki clone. Must contain
            ``Home.md``; will be written to ``_Sidebar.md``.
    """
    home_path = wiki_path / "Home.md"
    tasks = parse_home_tasks(home_path)

    # Build the set of slugs that actually have a proposal file on disk.
    # ``proposal-*.md`` at wiki root is the flat-namespace convention from
    # ``ref-formats.md`` (GitHub Wiki does not render subdirectory pages).
    proposal_slugs = {
        p.stem[len("proposal-"):]
        for p in wiki_path.glob("proposal-*.md")
    }
    enriched = [
        {**task, "has_proposal": task["slug"] in proposal_slugs}
        for task in tasks
    ]

    sidebar_path = wiki_path / "_Sidebar.md"
    sidebar_path.write_text(render_sidebar(enriched), encoding="utf-8")
    print(
        f"[sidebar] regenerate: wrote {sidebar_path} "
        f"({len(enriched)} task(s), "
        f"{sum(1 for t in enriched if t['has_proposal'])} with proposal)",
        file=sys.stderr,
    )


if __name__ == "__main__":
    print(
        "Usage: import _sidebar; "
        "_sidebar.regenerate(Path('/path/to/wiki'))",
        file=sys.stderr,
    )
    sys.exit(0)
