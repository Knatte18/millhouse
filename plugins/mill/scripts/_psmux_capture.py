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

    Finds the response text between a bullet-prefixed first line (● ) and the
    last line before the idle prompt (❯), excluding the completion marker
    (✻ Verb for Ns) and separator line (────) that appear after the response.

    Walks backwards from the idle prompt, skipping empty lines, lines starting
    with the completion marker (✻), and separator lines (all ─ characters).
    The first non-skipped line is the end of response content. Then searches
    backwards from that point to find the bullet prefix (● ).

    Args:
        snapshot: Full psmux capture-pane snapshot.

    Returns:
        Text from the bullet-prefixed first line through the last line of
        actual response content (before separator/completion marker).

    Raises:
        MarkerNotFoundError: If idle char, content boundary, or bullet prefix is missing.
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

    # Walk backwards from idle_idx - 1, skipping:
    # (a) empty lines
    # (b) lines starting with ✻ (completion marker)
    # (c) separator lines (all ─ characters when stripped)
    content_end_idx = None
    for i in range(idle_idx - 1, -1, -1):
        stripped = lines[i].strip()

        # Skip empty lines
        if not stripped:
            continue

        # Skip completion marker lines
        if stripped.startswith("✻"):
            continue

        # Skip separator lines (all ─ characters)
        if stripped and all(c == "─" for c in stripped):
            continue

        # Found the last line of actual content
        content_end_idx = i
        break

    if content_end_idx is None:
        raise MarkerNotFoundError("no response content found before idle char")

    # Find the first line (searching backwards from content_end_idx) starting with bullet prefix
    bullet_prefix = "● "
    bullet_idx = None
    for i in range(content_end_idx, -1, -1):
        if lines[i].strip().startswith(bullet_prefix):
            bullet_idx = i
            break

    if bullet_idx is None:
        raise MarkerNotFoundError("bullet prefix not found before idle char in snapshot")

    # Extract and process the response lines
    response_lines = lines[bullet_idx:content_end_idx + 1]

    # Strip bullet prefix from the first line
    first_line = response_lines[0].strip()[2:]  # [2:] removes "● "

    # Reassemble: first line + remaining lines verbatim
    if len(response_lines) > 1:
        result = first_line + "\n" + "\n".join(response_lines[1:])
    else:
        result = first_line

    return result.strip()
