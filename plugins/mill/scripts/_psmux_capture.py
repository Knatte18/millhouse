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
    raise NotImplementedError("implemented in card 4")
