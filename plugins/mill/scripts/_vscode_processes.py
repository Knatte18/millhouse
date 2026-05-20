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
    # Uses ctypes Win32 API directly — avoids spawning powershell.exe (~1s startup cost).
    import ctypes
    import ctypes.wintypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

    titles: set[Path] = set()

    def _enum_callback(hwnd: int, _: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        title_buf = ctypes.create_unicode_buffer(256)
        if user32.GetWindowTextW(hwnd, title_buf, 256) == 0:
            return True
        title = title_buf.value
        if not title:
            return True
        pid = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        hproc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if not hproc:
            return True
        try:
            name_buf = ctypes.create_unicode_buffer(260)
            size = ctypes.wintypes.DWORD(260)
            if kernel32.QueryFullProcessImageNameW(hproc, 0, name_buf, ctypes.byref(size)):
                if "code" in name_buf.value.lower():
                    titles.add(Path(title))
        finally:
            kernel32.CloseHandle(hproc)
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    user32.EnumWindows(WNDENUMPROC(_enum_callback), 0)
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
