"""
Home.md parser, claim helper, and renderer.

Home.md holds wiki tasks as level-2 headings. mill-spawn reads them to
pick a task; mill-spawn / mill-merge / mill-cleanup / mill-abandon
change the phase marker on an existing heading. This module is the
single source of truth for that heading syntax so every script sees
the same shape.

Heading syntax — two lines, title then slug (mill-add writes this form):
    ## <Title>
    [<slug>]
    ## <Title>
    [[<slug>]](proposal-<slug>)
Optionally with a phase marker on the slug line:
    ## <Title>
    [<slug>] [s]
    ## <Title>
    [<slug>] [active]
    ## <Title>
    [[<slug>]](proposal-<slug>) [done]

Phases: ``None`` (unmarked backlog), ``"s"`` (spawn-ready fast-path),
``"active"``, ``"done"``. ``[abandoned]`` is accepted on parse for
forward/backward compatibility but v2 does not produce it (mill-cleanup
returns abandoned work to unmarked instead).

Public API:
    Task                              dataclass.
    parse(text) -> list[Task]         parse Home.md body text.
    claim(text, slug) -> str          return text with slug set to [active].
    set_phase(text, slug, phase)      generalised claim; phase=None unmarks.
    set_phase_at(path, slug, phase)   read-write wrapper for set_phase.
    append_entry(text, slug, title, body, has_proposal=False) -> str
                                      append a new entry at end-of-file.
    remove_entry(text, slug) -> str   remove the entry for slug.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]*$")

_HEADING_RE = re.compile(
    r"^## (?P<title>.+?)\n"
    r"\[(?P<bracket>\[?)(?P<slug>[a-z][a-z0-9-]*)\]?\]"
    r"(?:\((?P<proposal>proposal-[^)]+)\))?"
    r"(?: \[(?P<phase>s|active|done|abandoned)\])?"
    r"[ \t]*$",
    re.MULTILINE,
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
    for match in _HEADING_RE.finditer(text):
        has_proposal = match.group("proposal") is not None
        line_no = text[:match.start()].count("\n") + 1
        tasks.append(Task(
            slug=match.group("slug"),
            title=match.group("title").strip(),
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

    found = False

    def _rewrite(match: re.Match) -> str:
        nonlocal found
        if match.group("slug") != slug:
            return match.group(0)
        found = True
        title = match.group("title")
        proposal = match.group("proposal")
        if match.group("bracket"):
            slug_line = f"[[{slug}]]({proposal})" if proposal else f"[[{slug}]]"
        else:
            slug_line = f"[{slug}]"
        if phase is not None:
            slug_line += f" [{phase}]"
        return f"## {title}\n{slug_line}"

    result = _HEADING_RE.sub(_rewrite, text)
    if not found:
        raise ValueError(f"Task with slug {slug!r} not found in Home.md")
    if not result.endswith("\n"):
        result += "\n"
    return result


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


def set_phase_at(path: Path, slug: str, phase: str | None) -> None:
    """
    Read ``path``, call ``set_phase``, and write the result back to ``path``.

    Convenience wrapper for callers that work with the file path rather
    than holding the text in memory (e.g. the mill-go orchestrator that
    flips a phase in one call instead of read → set_phase → write).

    Args:
        path: Path to Home.md (read and written in place).
        slug: Task slug to modify.
        phase: New phase marker, or ``None`` to clear.

    Raises:
        ValueError: ``phase`` is not valid, or no heading with that slug
            exists (delegates to ``set_phase``).
    """
    text = path.read_text(encoding="utf-8")
    result = set_phase(text, slug, phase)
    path.write_text(result, encoding="utf-8")


def append_entry(
    text: str,
    slug: str,
    title: str,
    body: str,
    has_proposal: bool = False,
) -> str:
    """
    Return ``text`` with a new task entry appended at end-of-file.

    Trailing whitespace in ``text`` is normalised to exactly one ``\\n``
    before appending. A blank line is always prepended before the new heading.

    Args:
        text: Current contents of Home.md.
        slug: Task slug. Must match ``[a-z][a-z0-9-]*``.
        title: Human-readable task title.
        body: Task body text. Empty string emits heading + slug line only,
            with no trailing blank line.
        has_proposal: Emit ``[[slug]](proposal-slug)`` link form when True.

    Returns:
        The updated text with the new entry appended.

    Raises:
        ValueError: ``slug`` fails validation.
    """
    if not _SLUG_RE.match(slug):
        raise ValueError(
            f"Invalid slug {slug!r}: must match [a-z][a-z0-9-]*"
        )

    slug_line = f"[[{slug}]](proposal-{slug}.md)" if has_proposal else f"[{slug}]"

    if body:
        new_entry = f"## {title}\n{slug_line}\n\n{body}\n"
    else:
        new_entry = f"## {title}\n{slug_line}\n"

    if text.strip():
        text = text.rstrip() + "\n"

    return text + "\n" + new_entry


def remove_entry(text: str, slug: str) -> str:
    """
    Return ``text`` with the task entry for ``slug`` removed.

    Deletes from the heading line through the line before the next ``##``
    heading (or EOF). Always terminates the result with exactly one trailing
    newline.

    Args:
        text: Current contents of Home.md.
        slug: Task slug to remove.

    Returns:
        The updated text.

    Raises:
        ValueError: No heading with that slug exists in ``text``.
    """
    matches = list(_HEADING_RE.finditer(text))
    target_index = None
    for i, m in enumerate(matches):
        if m.group("slug") == slug:
            target_index = i
            break
    if target_index is None:
        raise ValueError(f"Task with slug {slug!r} not found in Home.md")

    delete_start = matches[target_index].start()
    if target_index + 1 < len(matches):
        delete_end = matches[target_index + 1].start()
    else:
        delete_end = len(text)

    result = text[:delete_start] + text[delete_end:]
    stripped = result.rstrip()
    return (stripped + "\n") if stripped else "\n"
