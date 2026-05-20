"""Pure-function output parser for psmux capture-pane text.

This module is the output parser for the claude-subscription wrapper
(millpy-claude-sub.py). It extracts Claude's response from a psmux
capture-pane snapshot using the dual-marker protocol.
"""
from __future__ import annotations


class MarkerNotFoundError(Exception):
    """Raised when a marker is missing or out of order in capture text."""


def extract_response(
    capture_text: str, begin_marker: str, end_marker: str
) -> str:
    """Extract response from capture text between begin and end markers.

    Args:
        capture_text: Full psmux capture-pane snapshot.
        begin_marker: Begin marker line (matched after whitespace strip).
        end_marker: End marker line (matched after whitespace strip).

    Returns:
        Text between the markers (joined with newlines).

    Raises:
        MarkerNotFoundError: If either marker is missing or end precedes begin.
    """
    lines = capture_text.split("\n")

    begin_idx = None
    for i, line in enumerate(lines):
        cleaned = line.strip()
        # Claude TUI prepends "● " to the first line of each response.
        if cleaned.startswith("● "):
            cleaned = cleaned[2:]
        if cleaned == begin_marker:
            begin_idx = i
            break

    if begin_idx is None:
        raise MarkerNotFoundError(
            f"begin marker {begin_marker!r} not found in capture"
        )

    end_idx = None
    for j in range(begin_idx + 1, len(lines)):
        if lines[j].strip() == end_marker:
            end_idx = j
            break

    if end_idx is None:
        raise MarkerNotFoundError(
            f"end marker {end_marker!r} not found after begin marker in capture"
        )

    return "\n".join(lines[begin_idx + 1 : end_idx])
