"""
Psmux subprocess driver shim.

This module wraps psmux commands used by millpy-claude-sub.py to automate
an interactive Claude session. All subprocess calls go through _subprocess_util
for consistent logging and timeout enforcement. Public API: eight functions
(new_session, set_history_limit, send_keys, load_buffer, paste_buffer,
capture_pane, kill_session, list_sessions) and the PsmuxError exception.
"""
from __future__ import annotations

import sys  # noqa: F401
from pathlib import Path

import _subprocess_util  # noqa: F401

PSMUX_COMMAND_TIMEOUT_S = 30


class PsmuxError(Exception):
    """Raised when a psmux subprocess call fails."""

    pass


def new_session(
    name: str, *, cols: int = 200, rows: int = 50, shell_argv: list[str]
) -> None:
    """Create a detached psmux session with the given name and dimensions."""
    raise NotImplementedError("implemented in card 7")


def set_history_limit(name: str, limit: int) -> None:
    """Set the pane scrollback history limit."""
    raise NotImplementedError("implemented in card 7")


def send_keys(name: str, keys: str, *, enter: bool = False) -> None:
    """Send keys to the pane."""
    raise NotImplementedError("implemented in card 7")


def load_buffer(name: str, buffer_name: str, file_path: Path) -> None:
    """Load file contents into a named paste buffer."""
    raise NotImplementedError("implemented in card 7")


def paste_buffer(name: str, buffer_name: str) -> None:
    """Paste buffer contents into the pane."""
    raise NotImplementedError("implemented in card 7")


def capture_pane(name: str, *, scrollback: int = 50000) -> str:
    """Capture pane output from scrollback."""
    raise NotImplementedError("implemented in card 7")


def kill_session(name: str) -> None:
    """Kill a psmux session."""
    raise NotImplementedError("implemented in card 7")


def list_sessions() -> list[str]:
    """List all active psmux sessions."""
    raise NotImplementedError("implemented in card 7")
