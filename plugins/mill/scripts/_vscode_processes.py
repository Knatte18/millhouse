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
    # VS Code on Windows doesn't expose workspace paths via Win32_Process.CommandLine —
    # only renderer/extension args appear there. Workspace info lives in MainWindowTitle,
    # which our .vscode/settings.json sets to "<short_name>: <slug>" for worktrees.
    # Returned as Path objects for return-type compatibility; treat as opaque strings.
    argv = [
        "powershell",
        "-NoProfile",
        "-Command",
        "Get-Process Code -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -ne '' } | Select-Object -ExpandProperty MainWindowTitle",
    ]
    try:
        result = _subprocess_util.run(argv, timeout=5, check=False)
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
        return set()
    if result.returncode != 0:
        return set()
    titles: set[Path] = set()
    for line in result.stdout.split("\n"):
        line = line.rstrip("\r")
        if line.strip():
            titles.add(Path(line))
    return titles


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


def signature_matches(launch_path: Path, slug: str, signature: str) -> bool:
    """Return True iff signature represents an open VS Code window for the given worktree.

    Two complementary checks:

    1. POSIX cmdline-form: ``code /path/to/worktree`` — uses bounded path match
       via ``_path_matches_cmdline``.
    2. Windows title-form: ``<short_name>: <slug>`` from our ``.vscode/settings.json``
       window.title template — uses slug-substring match (case-insensitive on Windows).

    Either match passes. The two checks are independent: tests that mock signatures
    as paths still hit the cmdline branch; real Windows runtime hits the slug branch.
    """
    if _path_matches_cmdline(launch_path, signature):
        return True
    hay = signature.lower() if os.name == "nt" else signature
    needle = slug.lower() if os.name == "nt" else slug
    return needle in hay


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
