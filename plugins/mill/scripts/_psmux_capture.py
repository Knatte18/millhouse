"""Pure-function output parser for psmux capture-pane text.

This module is the output parser for the claude-subscription wrapper
(millpy-claude-sub.py). It extracts Claude's response from a psmux
capture-pane snapshot by finding the response between a bullet-prefixed
first line and the idle prompt character (❯).
"""
from __future__ import annotations


class MarkerNotFoundError(Exception):
    """Raised when idle prompt or bullet prefix is missing in capture text."""


def extract_response(snapshot: str) -> str:
    """Extract response from a psmux capture-pane snapshot.

    Finds the idle prompt character (❯) at the end and the bullet prefix (● )
    at the start, extracts the response between them, and returns it stripped.

    Args:
        snapshot: Full psmux capture-pane snapshot.

    Returns:
        Text from the bullet-prefixed first line through the line before idle.

    Raises:
        MarkerNotFoundError: If idle char or bullet prefix is missing.
    """
    lines = snapshot.split("\n")

    # Find the last line starting with idle prompt (after stripping)
    idle_prompt = "❯"
    idle_idx = None
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip().startswith(idle_prompt):
            idle_idx = i
            break

    if idle_idx is None:
        raise MarkerNotFoundError("idle char not found in snapshot")

    # Find the first line (searching backwards) starting with bullet prefix
    bullet_prefix = "● "
    bullet_idx = None
    for i in range(idle_idx - 1, -1, -1):
        if lines[i].strip().startswith(bullet_prefix):
            bullet_idx = i
            break

    if bullet_idx is None:
        raise MarkerNotFoundError("bullet prefix not found before idle char in snapshot")

    # Extract and process the response lines
    response_lines = lines[bullet_idx:idle_idx]

    # Strip bullet prefix from the first line
    first_line = response_lines[0].strip()[2:]  # [2:] removes "● "

    # Reassemble: first line + remaining lines verbatim
    if len(response_lines) > 1:
        result = first_line + "\n" + "\n".join(response_lines[1:])
    else:
        result = first_line

    return result.strip()
