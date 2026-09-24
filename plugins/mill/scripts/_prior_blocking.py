"""
Builds a cumulative, cross-round digest of prior rounds' `### [BLOCKING...]` findings from
`_mill/reviews/` code-review files.

The digest feeds a `--nits-only` fixer dispatch (`millpy-fix.py --prior-blocking`) so the fixer has
context on what BLOCKING problems earlier rounds already fixed, and does not blindly undo one of
those fixes while addressing NIT-only findings.
This is distinct from the pre-existing prose-driven `prior-nonblocking-*` NIT digest documented in
mill-go/SKILL.md, which this module does not touch or unify with.

Public API:
    build_digest() -- scan every holistic code-review file on disk and return a
    newline-joined digest of BLOCKING finding titles (and their first context line), or "" when
    no such file or finding exists.
"""
from __future__ import annotations

import re
from pathlib import Path

import _review_common

# Matches a finding heading in the class-aware syntax: "### [BLOCKING:design] <title>".
# The class group is optional -- "### [BLOCKING] <title>" has cls=None.
# Same shape as _review_common.py's own _RE_FINDING_HEADING, scoped locally here rather than
# importing that private (leading-underscore) name.
_BLOCKING_HEADING_RE = re.compile(
    r"^###\s+\[(?P<sev>[A-Z0-9-]+)(?::(?P<cls>[a-z-]+))?\]\s+(?P<title>.*)$",
    re.MULTILINE,
)


def build_digest(reviews_dir: Path) -> str:
    """
    Scan every holistic code-review file on disk and extract every BLOCKING finding.

    Per the digest-scans-current-disk-state-no-round-boundary decision, this function takes no
    round parameter: it scans every review file currently on disk and extracts every
    `### [BLOCKING...]` heading found, full stop.
    A `--nits-only` fixer dispatch only ever fires on a round whose own review already contains
    zero BLOCKING headings, so scanning everything on disk right now naturally excludes that
    round's own contribution with no explicit boundary math.

    Args:
        reviews_dir: the `_mill/reviews/` directory to scan.
            Leftover per-batch code-review files (`<ts>-code-review-<batch>-r<N>.md`) are ignored.

    Returns:
        A newline-joined string of "- <title>: <context>" (or "- <title>" when no context line
        exists) lines, one per BLOCKING finding, in file-then-heading order.
        "" when reviews_dir does not exist or no selected file contributes a BLOCKING heading.
    """
    if not reviews_dir.exists():
        return ""

    selected_files: list[Path] = []
    for candidate in sorted(reviews_dir.iterdir()):
        simple_match = _review_common.RE_SIMPLE.match(candidate.name)
        if simple_match and simple_match.group("type") == "code":
            selected_files.append(candidate)

    # Extract every BLOCKING heading from each selected file, in file-then-heading order.
    lines: list[str] = []
    for review_file in selected_files:
        text = review_file.read_text(encoding="utf-8")
        file_lines = text.splitlines()
        for match in _BLOCKING_HEADING_RE.finditer(text):
            # A demoted finding is rewritten on disk as "### [NIT...]" with a
            # "**Demoted-from:** BLOCKING" marker line beneath it, so filtering on sev ==
            # BLOCKING_SEVERITY here already excludes demoted findings with no separate detection.
            if match.group("sev") != _review_common.BLOCKING_SEVERITY:
                continue
            title = match.group("title").strip()

            # Find the first non-empty line strictly after the heading's own line.
            heading_line_index = text.count("\n", 0, match.start())
            context = ""
            for candidate_line in file_lines[heading_line_index + 1 :]:
                stripped = candidate_line.strip()
                if stripped:
                    context = stripped
                    break

            formatted = f"- {title}: {context}" if context else f"- {title}"
            # ASCII-fold to guard against Windows cp1252 stdout crashes downstream.
            lines.append(formatted.encode("ascii", errors="replace").decode("ascii"))

    return "\n".join(lines)
