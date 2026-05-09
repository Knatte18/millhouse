"""
VS Code open-window process probe.

Detects which paths are currently open in a running VS Code editor by
examining OS process tables, then provides a boundary-safe predicate for
testing whether a given launch path appears in a VS Code process cmdline.

Public API:
    find_open_vscode_paths() -> set[Path]
        Return the set of paths derived from running VS Code process cmdlines.
        Returns an empty set on any probe failure.
    _path_matches_cmdline(launch_path: Path, cmdline: str) -> bool
        Return True iff launch_path appears in cmdline, bounded by whitespace,
        quotes, or string start/end. Case-insensitive on Windows.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import _subprocess_util


def find_open_vscode_paths() -> set[Path]:
    """Return paths from running VS Code process cmdlines, or empty set on failure."""
    try:
        if os.name == "nt":
            return _probe_windows()
        return _probe_posix()
    except Exception:
        return set()


def _probe_windows() -> set[Path]:
    argv = [
        "powershell",
        "-NoProfile",
        "-Command",
        "Get-CimInstance Win32_Process -Filter \"Name='Code.exe'\" | Select-Object -ExpandProperty CommandLine",
    ]
    try:
        result = _subprocess_util.run(argv, timeout=5, check=False)
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
        return set()
    if result.returncode != 0:
        return set()
    paths: set[Path] = set()
    for line in result.stdout.split("\n"):
        line = line.rstrip("\r")
        if line.strip():
            paths.add(Path(line))
    return paths


def _probe_posix() -> set[Path]:
    argv = ["ps", "-ww", "-A", "-o", "command="]
    try:
        result = _subprocess_util.run(argv, timeout=5, check=False)
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
        return set()
    if result.returncode != 0:
        return set()
    paths: set[Path] = set()
    for line in result.stdout.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        token = stripped.split(maxsplit=1)[0]
        if Path(token).name.startswith("code"):
            paths.add(Path(line))
    return paths


def _path_matches_cmdline(launch_path: Path, cmdline: str) -> bool:
    """Return True iff launch_path appears in cmdline bounded by whitespace, quotes, or string edges."""
    s = str(launch_path.resolve())
    hay = str(cmdline)
    if os.name == "nt":
        s = s.lower()
        hay = hay.lower()
    boundaries = {"", " ", "\t", '"', "'"}
    for needle in (s, s + os.sep):
        idx = hay.find(needle)
        while idx != -1:
            left = hay[idx - 1] if idx > 0 else ""
            right_index = idx + len(needle)
            right = hay[right_index] if right_index < len(hay) else ""
            if left in boundaries and right in boundaries:
                return True
            idx = hay.find(needle, idx + 1)
    return False
