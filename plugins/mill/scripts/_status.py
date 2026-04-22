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
    render_initial(task_title, task_description, timestamp) -> str
        Return the rendered status.md body as a string.
"""
from __future__ import annotations

import re
from pathlib import Path

_TOKEN_RE = re.compile(r"<([A-Z][A-Z0-9_]*)>")

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

    Returns:
        The rendered status.md text, including trailing newline.
    """
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    body = _strip_leading_comment(template)
    tokens = {
        "TASK_TITLE": task_title,
        "TASK_DESCRIPTION": task_description,
        "TIMESTAMP": timestamp,
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


if __name__ == "__main__":
    out = render_initial(
        task_title="Fix bug in widget handler",
        task_description="Widgets throw on empty input.",
        timestamp="2026-04-22T14:32:05Z",
    )
    assert out.startswith("# Status\n"), "Leading HTML comment should be stripped"
    assert "Fix bug in widget handler" in out
    assert "2026-04-22T14:32:05Z" in out
    assert "<TASK_TITLE>" not in out and "<TIMESTAMP>" not in out
    print("PASS: render_initial() substitutes tokens and strips header")
    print("All _status smoke tests passed.")
