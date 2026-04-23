"""
Home.md parser, claim helper, and renderer.

Home.md holds wiki tasks as level-2 headings. mill-spawn reads them to
pick a task; mill-spawn / mill-merge / mill-cleanup / mill-abandon
change the phase marker on an existing heading. This module is the
single source of truth for that heading syntax so every script sees
the same shape.

Heading syntax (mill-add writes; this module parses both forms):
    ## <Title> [<slug>]
    ## <Title> [[<slug>]](proposal-<slug>)
Optionally suffixed with a phase marker:
    ## <Title> [<slug>] [s]
    ## <Title> [<slug>] [active]
    ## <Title> [[<slug>]](proposal-<slug>) [done]

Phases: ``None`` (unmarked backlog), ``"s"`` (spawn-ready fast-path),
``"active"``, ``"done"``. ``[abandoned]`` is accepted on parse for
forward/backward compatibility but v2 does not produce it (mill-cleanup
returns abandoned work to unmarked instead).

Public API:
    Task                              dataclass.
    parse(text) -> list[Task]         parse Home.md body text.
    claim(text, slug) -> str          return text with slug set to [active].
    set_phase(text, slug, phase)      generalised claim; phase=None unmarks.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_HEADING_RE = re.compile(
    r"^## (?P<title>.+?) "
    r"\[(?P<bracket>\[?)(?P<slug>[a-z][a-z0-9-]*)\]?\]"
    r"(?:\((?P<proposal>proposal-[^)]+)\))?"
    r"(?: \[(?P<phase>s|active|done|abandoned)\])?"
    r"\s*$"
)

_VALID_PHASES = (None, "s", "active", "done", "abandoned")


@dataclass(frozen=True)
class Task:
    """One Home.md task entry parsed from a ``##`` heading."""
    slug: str
    title: str
    phase: str | None         # None | "s" | "active" | "done" | "abandoned"
    has_proposal: bool
    heading_line_no: int      # 1-indexed line number of the heading


def parse(text: str) -> list[Task]:
    """
    Return every task heading in ``text`` as a Task, in file order.

    Non-heading lines are ignored. Malformed headings (e.g. stray ``##``
    lines that don't match the expected form) are silently skipped —
    callers that want to enforce structure should validate separately.

    Args:
        text: Full contents of Home.md.

    Returns:
        A list of Task instances in the order they appear.
    """
    tasks: list[Task] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        match = _HEADING_RE.match(line)
        if match is None:
            continue
        # Verify the bracket shape is consistent: "[[" requires "]](...)"
        # shape with a proposal; "[" requires no double-close. Mis-shaped
        # headings (e.g. "[[slug]" with no closing-bracket pair) fail the
        # regex above, so by this point we trust the match.
        has_proposal = match.group("proposal") is not None
        tasks.append(Task(
            slug=match.group("slug"),
            title=match.group("title"),
            phase=match.group("phase"),
            has_proposal=has_proposal,
            heading_line_no=line_no,
        ))
    return tasks


def set_phase(text: str, slug: str, phase: str | None) -> str:
    """
    Return ``text`` with the heading for ``slug`` rewritten to ``phase``.

    When ``phase`` is ``None`` any existing phase marker is stripped
    (task returns to unmarked backlog). When non-None, any existing
    marker is replaced and, if absent, appended after the slug/proposal.

    Args:
        text: Full contents of Home.md.
        slug: Task slug to modify.
        phase: New phase marker, or ``None`` to clear.

    Returns:
        The rewritten text. Always terminated with a single trailing newline.

    Raises:
        ValueError: ``phase`` is not one of the accepted values, or no
            heading with that slug exists in ``text``.
    """
    if phase not in _VALID_PHASES:
        raise ValueError(
            f"Invalid phase {phase!r}; expected one of {_VALID_PHASES!r}"
        )

    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        match = _HEADING_RE.match(line.rstrip("\r\n"))
        if match is None or match.group("slug") != slug:
            continue
        # Rebuild the heading line with the new phase marker.
        title = match.group("title")
        proposal = match.group("proposal")
        if match.group("bracket"):
            slug_part = f"[[{slug}]]({proposal})" if proposal else f"[[{slug}]]"
        else:
            slug_part = f"[{slug}]"
        new_line = f"## {title} {slug_part}"
        if phase is not None:
            new_line += f" [{phase}]"
        # Preserve the line's original line ending.
        eol = line[len(line.rstrip("\r\n")):]
        lines[i] = new_line + eol
        out = "".join(lines)
        if not out.endswith("\n"):
            out += "\n"
        return out
    raise ValueError(f"Task with slug {slug!r} not found in Home.md")


def claim(text: str, slug: str) -> str:
    """
    Return ``text`` with the heading for ``slug`` set to ``[active]``.

    Convenience wrapper around ``set_phase`` used by mill-spawn. Raises
    when the slug is unknown; the caller is expected to have picked the
    slug out of ``parse(text)`` immediately before calling this.

    Args:
        text: Full contents of Home.md.
        slug: Task slug to claim.

    Returns:
        The rewritten text.

    Raises:
        ValueError: slug not found (see ``set_phase``).
    """
    return set_phase(text, slug, "active")
