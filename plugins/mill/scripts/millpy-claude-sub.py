"""
Drop-in replacement for `claude -p` that routes through interactive `claude` via psmux
for subscription billing instead of API credits. Accepts prompt on stdin, returns Claude's
response on stdout, emits one-line JSON metadata `{session_id, duration_s, mode}` on stderr.

Four modes with hardcoded tool sets per Shared Decision in discussion.md: `bulk`
(--tools ""), `tool-use` (--allowedTools "Read,Grep,Glob"), `implementer`
(--allowedTools "Read,Edit,Write,Bash,Grep,Glob,Skill"). See _psmux.py (driver)
and _psmux_capture.py (parser) for the psmux automation and response extraction.
"""
from __future__ import annotations

import argparse
import json
import secrets
import shlex
import sys
import time
import uuid
from pathlib import Path

import _paths
import _psmux
import _psmux_capture
import _subprocess_util

# Boot and polling constants
BOOT_READY_TIMEOUT_S = 20
PSMUX_COMMAND_TIMEOUT_S = 30  # Synchronized with _psmux.py; keep in sync
POLL_INTERVAL_S = 1.0
RESPONSE_POLL_TIMEOUT_S: dict[str, int] = {
    "bulk": 300,
    "tool-use": 600,
    "implementer": 1800,
}

# Mode-implicit tool sets
MODE_TOOL_FLAGS: dict[str, list[str]] = {
    "bulk": ["--tools", ""],
    "tool-use": ["--allowedTools", "Read,Grep,Glob"],
    "implementer": ["--allowedTools", "Read,Edit,Write,Bash,Grep,Glob,Skill"],
}


def _make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Drop-in replacement for 'claude -p' using subscription billing via psmux"
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=["bulk", "tool-use", "implementer"],
        help="Mode determines tool set: bulk (no tools), tool-use (Read/Grep/Glob), implementer (all)",
    )
    parser.add_argument(
        "--model",
        required=True,
        help="Claude model name (e.g. claude-opus-4-1)",
    )
    parser.add_argument(
        "--effort",
        choices=["low", "medium", "high", "xhigh", "max"],
        help="Optional effort level passed to claude",
    )
    parser.add_argument(
        "--session-id",
        default=str(uuid.uuid4()),
        help="Session ID (default: generated UUID)",
    )
    return parser


def main() -> int:
    raise NotImplementedError("implemented in card 9")


if __name__ == "__main__":
    sys.exit(main())
