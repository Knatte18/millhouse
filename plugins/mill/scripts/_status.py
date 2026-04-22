"""
Render the initial ``status.md`` for a freshly-spawned task.

mill-spawn writes one file after claiming a task: ``wiki/active/<slug>/
status.md``. This module renders that file from
``templates/status-discussing.md``, substituting title / description /
timestamp tokens and stripping the leading HTML comment that documents
the template for humans reading the repo.

Keeping the renderer separate from the spawner lets future scripts
(mill-start's "begin discussion" step, mill-resume's re-sync) reuse the
same surface without copy-pasting token maps.

Public API:
    render_initial(task_title, task_description, timestamp,
                   parent_branch) -> str
        Return the rendered status.md body as a string.
    update_field(status_path, key, value) -> None
        Mutate ``key:`` in the top ``` ```yaml ``` ``` block of status.md.
    append_phase(status_path, phase, timestamp) -> None
        Record a new phase transition: overwrite ``phase:`` in the yaml
        block and append a timeline row.
"""
from __future__ import annotations

import re
from pathlib import Path

_TOKEN_RE = re.compile(r"<([A-Z][A-Z0-9_]*)>")
_YAML_FENCE = "```yaml"
_TIMELINE_FENCE = "```text"

_TEMPLATE_PATH = (
    Path(__file__).resolve().parent.parent
    / "templates"
    / "status-discussing.md"
)


def _strip_leading_comment(text: str) -> str:
    """Drop the leading ``<!-- ... -->`` template header if present.

    The template file has a human-facing HTML comment describing its
    tokens; that comment is useful for anyone browsing the repo but
    would be noise in an actual ``status.md``. We strip only a comment
    that starts at the very first character of the file — trailing
    comments or comments mid-file are preserved.
    """
    stripped = text.lstrip()
    if not stripped.startswith("<!--"):
        return text
    close = stripped.find("-->")
    if close == -1:
        return text
    after = stripped[close + len("-->"):].lstrip("\r\n")
    return after


def render_initial(
    task_title: str,
    task_description: str,
    timestamp: str,
    parent_branch: str,
) -> str:
    """
    Render the phase=discussing status.md for ``task_title``.

    Reads the template once per call (cheap; the file is tiny), strips
    the leading documentation comment, and substitutes placeholders via
    ``_render.render``. Callers typically write the returned string to
    ``<wiki>/active/<slug>/status.md``.

    Args:
        task_title: Human-readable task name; appears as the YAML
            ``task:`` value.
        task_description: One-or-more-paragraph description; injected
            under the YAML ``task_description: |`` key so multi-line
            values render as a literal block. Newlines in the input are
            preserved as-is; the template's ``  `` indent applies to the
            first line only, so multi-line values remain valid YAML only
            when the caller does not include leading spaces.
        timestamp: ISO-8601 UTC timestamp for the timeline entry,
            e.g. ``"2026-04-22T14:32:05Z"``.
        parent_branch: The branch the hub was on at spawn time. mill-merge
            / mill-cleanup read this to know where to merge back to.

    Returns:
        The rendered status.md text, including trailing newline.
    """
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    body = _strip_leading_comment(template)
    tokens = {
        "TASK_TITLE": task_title,
        "TASK_DESCRIPTION": task_description,
        "TIMESTAMP": timestamp,
        "PARENT_BRANCH": parent_branch,
    }
    for key, value in tokens.items():
        body = body.replace(f"<{key}>", value)
    # Mirror _render.render's strictness: reject any unresolved token so a
    # template evolving under a caller's feet fails loudly instead of
    # emitting half-rendered status files.
    unresolved = sorted(set(_TOKEN_RE.findall(body)))
    if unresolved:
        raise KeyError(
            f"Unresolved tokens in status template: {unresolved!r}"
        )
    return body


def _split_fences(text: str, fence_open: str) -> tuple[int, int]:
    """
    Return ``(block_start, block_end)`` line indices for the first fenced
    block opened by ``fence_open``. Indices point at the content lines
    (between the open and close fences), i.e. ``text.splitlines()``
    slice ``[block_start:block_end]`` is the body.

    Raises ``ValueError`` if the block is missing or unterminated.
    """
    lines = text.splitlines()
    start: int | None = None
    for i, line in enumerate(lines):
        if line.strip() == fence_open:
            start = i + 1
            break
    if start is None:
        raise ValueError(f"No {fence_open} block in status file")
    for j in range(start, len(lines)):
        if lines[j].strip() == "```":
            return (start, j)
    raise ValueError(f"Unterminated {fence_open} block in status file")


def update_field(status_path: Path, key: str, value: str) -> None:
    """
    Rewrite ``<key>:`` in the top ``` ```yaml ``` ``` block of ``status_path``.

    Only single-line ``key: value`` rows are supported — multi-line
    ``task_description: |`` style blocks cannot be updated via this
    helper because the indent rules require awareness of the surrounding
    block-scalar shape. Callers that need multi-line updates should
    re-render the whole file.

    Args:
        status_path: Absolute path to the status.md file.
        key: YAML key to mutate (must already exist in the block).
        value: New value. Written verbatim after ``key: ``; embed quotes
            if the value contains colons or hash characters.

    Raises:
        ValueError: the file lacks a yaml block, the block is
            unterminated, or ``key`` is not present at a scalar row.
    """
    text = status_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    start, end = _split_fences(text, _YAML_FENCE)
    key_pattern = re.compile(rf"^({re.escape(key)}:\s*).*$")
    for i in range(start, end):
        stripped = lines[i].rstrip("\r\n")
        match = key_pattern.match(stripped)
        if match is None:
            continue
        eol = lines[i][len(stripped):]
        lines[i] = f"{key}: {value}{eol}"
        status_path.write_text("".join(lines), encoding="utf-8")
        return
    raise ValueError(f"Key {key!r} not found in yaml block of {status_path}")


def append_phase(status_path: Path, phase: str, timestamp: str) -> None:
    """
    Record a phase transition in ``status.md``.

    Two mutations happen atomically from the caller's viewpoint:

    1. ``phase:`` in the top yaml block is overwritten with the new value.
    2. A ``<phase>  <timestamp>`` row is appended to the ``## Timeline``
       code block.

    The function reads, rewrites, and writes the file once — we don't use
    ``update_field`` for step 1 because it would re-read and re-write the
    file, doubling I/O for no gain.

    Args:
        status_path: Absolute path to the status.md file.
        phase: New phase name (e.g. ``"discussed"``, ``"planning"``,
            ``"done"``).
        timestamp: ISO-8601 UTC timestamp for the timeline row.

    Raises:
        ValueError: yaml block is missing / malformed, ``phase:`` key is
            absent from the yaml block, or the timeline block is absent.
    """
    text = status_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    y_start, y_end = _split_fences(text, _YAML_FENCE)
    updated_phase = False
    for i in range(y_start, y_end):
        stripped = lines[i].rstrip("\r\n")
        match = re.match(r"^(phase:\s*).*$", stripped)
        if match is None:
            continue
        eol = lines[i][len(stripped):]
        lines[i] = f"phase: {phase}{eol}"
        updated_phase = True
        break
    if not updated_phase:
        raise ValueError(f"phase: key missing from yaml block of {status_path}")

    # Timeline block: insert a new row at the end of the ```text block.
    # We need to find the fences in the rewritten text, not the original,
    # since the yaml-block edit above changed offsets.
    rewritten = "".join(lines)
    tl_lines = rewritten.splitlines(keepends=True)
    tl_text = "".join(tl_lines)
    t_start, t_end = _split_fences(tl_text, _TIMELINE_FENCE)
    # Aligned columns — phase name padded so timestamps line up in common
    # phases ("discussing" / "discussed" / "planning" / "coding" / "done").
    # We use two spaces as the separator; callers can post-fix alignment
    # if a new phase breaks the visual column.
    new_row = f"{phase}  {timestamp}\n"
    tl_lines.insert(t_end, new_row)
    status_path.write_text("".join(tl_lines), encoding="utf-8")


if __name__ == "__main__":
    out = render_initial(
        task_title="Fix bug in widget handler",
        task_description="Widgets throw on empty input.",
        timestamp="2026-04-22T14:32:05Z",
        parent_branch="main",
    )
    assert out.startswith("# Status\n"), "Leading HTML comment should be stripped"
    assert "Fix bug in widget handler" in out
    assert "2026-04-22T14:32:05Z" in out
    assert "parent: main" in out
    assert "<TASK_TITLE>" not in out and "<TIMESTAMP>" not in out
    print("PASS: render_initial() substitutes tokens and strips header")

    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        sp = Path(tmp) / "status.md"
        sp.write_text(out, encoding="utf-8")

        update_field(sp, "task", "Updated title")
        assert "task: Updated title" in sp.read_text(encoding="utf-8")
        print("PASS: update_field rewrites a scalar yaml row")

        append_phase(sp, "discussed", "2026-04-22T15:00:00Z")
        contents = sp.read_text(encoding="utf-8")
        assert "phase: discussed" in contents, "phase yaml row not updated"
        assert "discussed  2026-04-22T15:00:00Z" in contents, "timeline row not appended"
        print("PASS: append_phase updates phase yaml + appends timeline row")

    print("All _status smoke tests passed.")
