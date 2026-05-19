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
_PSMUX_PREFIX: list[str] = []


class PsmuxError(Exception):
    """Raised when a psmux subprocess call fails."""

    pass


def new_session(
    name: str, *, cols: int = 200, rows: int = 50, shell_argv: list[str]
) -> None:
    """Create a detached psmux session with the given name and dimensions."""
    argv = [
        *_PSMUX_PREFIX, "psmux",
        "new-session",
        "-d",
        "-s",
        name,
        "-x",
        str(cols),
        "-y",
        str(rows),
        "--",
        *shell_argv,
    ]
    result = _subprocess_util.run(argv, timeout=PSMUX_COMMAND_TIMEOUT_S)
    if result.returncode != 0:
        excerpt = (result.stderr or result.stdout)[:200]
        raise PsmuxError(f"psmux new-session failed: {excerpt}")


def set_history_limit(name: str, limit: int) -> None:
    """Set the pane scrollback history limit."""
    argv = [*_PSMUX_PREFIX, "psmux", "set-option", "-t", name, "-g", "history-limit", str(limit)]
    try:
        result = _subprocess_util.run(argv, timeout=PSMUX_COMMAND_TIMEOUT_S)
        if result.returncode != 0:
            excerpt = (result.stderr or result.stdout)[:200]
            raise PsmuxError(f"psmux set-option failed: {excerpt}")
    except PsmuxError:
        print(
            "[psmux] history-limit unsupported, using default", file=sys.stderr
        )
        return


def send_keys(name: str, keys: str, *, enter: bool = False) -> None:
    """Send keys to the pane."""
    if keys == "" and not enter:
        raise ValueError("send_keys called with no keys and enter=False")
    argv = [*_PSMUX_PREFIX, "psmux", "send-keys", "-t", name, keys]
    if enter:
        argv.append("Enter")
    result = _subprocess_util.run(argv, timeout=PSMUX_COMMAND_TIMEOUT_S)
    if result.returncode != 0:
        excerpt = (result.stderr or result.stdout)[:200]
        raise PsmuxError(f"psmux send-keys failed: {excerpt}")


def load_buffer(name: str, buffer_name: str, file_path: Path) -> None:
    """Load file contents into a named paste buffer."""
    argv = [*_PSMUX_PREFIX, "psmux", "load-buffer", "-b", buffer_name, str(file_path)]
    result = _subprocess_util.run(argv, timeout=PSMUX_COMMAND_TIMEOUT_S)
    if result.returncode != 0:
        excerpt = (result.stderr or result.stdout)[:200]
        raise PsmuxError(f"psmux load-buffer failed: {excerpt}")


def paste_buffer(name: str, buffer_name: str) -> None:
    """Paste buffer contents into the pane."""
    argv = [*_PSMUX_PREFIX, "psmux", "paste-buffer", "-t", name, "-b", buffer_name]
    result = _subprocess_util.run(argv, timeout=PSMUX_COMMAND_TIMEOUT_S)
    if result.returncode != 0:
        excerpt = (result.stderr or result.stdout)[:200]
        raise PsmuxError(f"psmux paste-buffer failed: {excerpt}")


def capture_pane(name: str, *, scrollback: int = 50000) -> str:
    """Capture pane output from scrollback."""
    argv = [*_PSMUX_PREFIX, "psmux", "capture-pane", "-t", name, "-S", f"-{scrollback}", "-p"]
    result = _subprocess_util.run(argv, timeout=PSMUX_COMMAND_TIMEOUT_S)
    if result.returncode != 0:
        excerpt = (result.stderr or result.stdout)[:200]
        raise PsmuxError(f"psmux capture-pane failed: {excerpt}")
    return result.stdout


def kill_session(name: str) -> None:
    """Kill a psmux session."""
    argv = [*_PSMUX_PREFIX, "psmux", "kill-session", "-t", name]
    try:
        result = _subprocess_util.run(argv, timeout=PSMUX_COMMAND_TIMEOUT_S)
        if result.returncode != 0:
            excerpt = (result.stderr or result.stdout)[:200]
            raise PsmuxError(f"psmux kill-session failed: {excerpt}")
    except PsmuxError as e:
        if "no such session" in str(e).lower():
            return
        raise


def list_sessions() -> list[str]:
    """List all active psmux sessions."""
    argv = [*_PSMUX_PREFIX, "psmux", "ls"]
    try:
        result = _subprocess_util.run(argv, timeout=PSMUX_COMMAND_TIMEOUT_S)
        if result.returncode != 0:
            excerpt = (result.stderr or result.stdout)[:200]
            raise PsmuxError(f"psmux ls failed: {excerpt}")
    except PsmuxError as e:
        if "no server running" in str(e).lower():
            return []
        raise

    if not result.stdout:
        return []

    sessions = []
    for line in result.stdout.split("\n"):
        line = line.strip()
        if line:
            session_name = line.split(":")[0]
            sessions.append(session_name)
    return sessions
