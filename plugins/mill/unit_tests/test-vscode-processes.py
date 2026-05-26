"""Unit tests for plugins/mill/scripts/_vscode_processes.py.

Only the _path_matches_cmdline helper is unit-tested here. _probe_windows now uses
the Win32 EnumWindows API directly (ctypes), and _probe_posix relies on the `ps`
command — both are environment-dependent and skipped from automated tests.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _vscode_processes import _path_matches_cmdline  # noqa: E402


def main() -> int:
    errors = 0

    # ------------------------------------------------------------------
    # Test: path_match_helper_bare — exact resolved path is a match.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        foo = Path(tmpdir) / "foo"
        foo.mkdir()
        resolved = str(foo.resolve())
        ok = _path_matches_cmdline(foo, f"code {resolved}")
    if not ok:
        print("FAIL: path_match_helper_bare: expected True", file=sys.stderr)
        errors += 1
    else:
        print("PASS: path_match_helper_bare")

    # ------------------------------------------------------------------
    # Test: path_match_helper_trailing_slash — path with trailing sep is a match.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        foo = Path(tmpdir) / "foo"
        foo.mkdir()
        resolved = str(foo.resolve())
        ok = _path_matches_cmdline(foo, f"code {resolved}{os.sep}")
    if not ok:
        print("FAIL: path_match_helper_trailing_slash: expected True", file=sys.stderr)
        errors += 1
    else:
        print("PASS: path_match_helper_trailing_slash")

    # ------------------------------------------------------------------
    # Test: path_match_helper_subpath_excluded — sub-path is NOT a match.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        foo = Path(tmpdir) / "foo"
        foo.mkdir()
        resolved = str(foo.resolve())
        ok = _path_matches_cmdline(foo, f"code {resolved}{os.sep}src")
    if ok:
        print("FAIL: path_match_helper_subpath_excluded: expected False, got True", file=sys.stderr)
        errors += 1
    else:
        print("PASS: path_match_helper_subpath_excluded")

    # ------------------------------------------------------------------
    # Test: path_match_helper_prefix_collision — longer path sharing prefix is NOT a match.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        foo = Path(tmpdir) / "foo"
        foo.mkdir()
        resolved = str(foo.resolve())
        ok = _path_matches_cmdline(foo, f"code {resolved}-bar")
    if ok:
        print("FAIL: path_match_helper_prefix_collision: expected False, got True", file=sys.stderr)
        errors += 1
    else:
        print("PASS: path_match_helper_prefix_collision")

    # ------------------------------------------------------------------
    # Test: path_match_helper_quoted_path — path in quotes with spaces is a match.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        foo_bar = Path(tmpdir) / "foo bar"
        foo_bar.mkdir()
        resolved = str(foo_bar.resolve())
        ok = _path_matches_cmdline(foo_bar, f'code "{resolved}"')
    if not ok:
        print("FAIL: path_match_helper_quoted_path: expected True", file=sys.stderr)
        errors += 1
    else:
        print("PASS: path_match_helper_quoted_path")

    # ------------------------------------------------------------------
    # Test: path_match_helper_end_of_string — end-of-string counts as a boundary.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        foo = Path(tmpdir) / "foo"
        foo.mkdir()
        resolved = str(foo.resolve())
        ok = _path_matches_cmdline(foo, f"code {resolved}")
    if not ok:
        print("FAIL: path_match_helper_end_of_string: expected True", file=sys.stderr)
        errors += 1
    else:
        print("PASS: path_match_helper_end_of_string")

    # ------------------------------------------------------------------
    # Test: path_match_helper_windows_case_insensitive (Windows only).
    # ------------------------------------------------------------------
    if os.name != "nt":
        print("SKIP: path_match_helper_windows_case_insensitive (not Windows)")
    else:
        with tempfile.TemporaryDirectory() as tmpdir:
            foo = Path(tmpdir) / "foo"
            foo.mkdir()
            upper = str(foo.resolve()).upper()
            ok = _path_matches_cmdline(foo, f"code {upper}")
        if not ok:
            print("FAIL: path_match_helper_windows_case_insensitive: expected True", file=sys.stderr)
            errors += 1
        else:
            print("PASS: path_match_helper_windows_case_insensitive")

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All _vscode_processes unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
