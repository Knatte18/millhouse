"""
Windows extended-length path prefixing.

NTFS enforces a legacy ``MAX_PATH`` (260 character) limit on any path passed through the
non-extended Win32 API surface. Deeply nested mill worktrees (task slug + `_mill/` + wiki-mirrored
subtrees) routinely exceed it, causing ``os.scandir``/``shutil``'s recursive-delete/junction-removal
calls to fail with ``WinError 145`` during verify-baseline teardown. Prefixing an absolute path with
the extended-length marker (``\\\\?\\``) tells the Win32 API to bypass ``MAX_PATH`` entirely. POSIX
has no such limit, so the prefix is a no-op there.

Public API:
    to_extended(path)
    Return the extended-length form of ``path`` on Windows, unchanged elsewhere.
"""
from __future__ import annotations

import sys
from pathlib import Path


def to_extended(path: Path) -> str:
    """
    Return the Windows extended-length ("\\\\?\\") form of ``path``.

    On any non-Windows platform (``sys.platform != "win32"``), returns ``str(path)`` unchanged.
    On Windows, the function is idempotent: a string already carrying the ``\\\\?\\`` prefix is
    returned unchanged.
    A UNC path (``\\\\server\\share\\...``) becomes ``\\\\?\\UNC\\server\\share\\...``;
    a drive-absolute path (``C:\\...``) becomes ``\\\\?\\C:\\...``.

    The caller is responsible for passing an already-resolved absolute path — this function performs
    no resolution or validation of its own, only the ``sys.platform``-gated string transform.
    """
    raw = str(path)
    if sys.platform != "win32":
        return raw
    if raw.startswith("\\\\?\\"):
        return raw
    if raw.startswith("\\\\"):
        return "\\\\?\\UNC\\" + raw[2:]
    return "\\\\?\\" + raw
