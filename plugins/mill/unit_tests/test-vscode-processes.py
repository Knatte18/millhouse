"""Unit tests for plugins/mill/scripts/_vscode_processes.py."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _vscode_processes import _path_matches_cmdline, find_open_vscode_paths  # noqa: E402


def main() -> int:
    errors = 0

    # ------------------------------------------------------------------
    # Test: windows_parser_basic — two distinct paths + one duplicate.
    # ------------------------------------------------------------------
    with (
        patch("_vscode_processes.os.name", "nt"),
        patch(
            "_vscode_processes._subprocess_util.run",
            return_value=subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="code C:\\wts\\foo\r\ncode C:\\wts\\bar\r\ncode C:\\wts\\foo\r\n",
                stderr="",
            ),
        ),
    ):
        result = find_open_vscode_paths()
    result_strs = {str(p).lower() for p in result}
    if len(result) != 2:
        print(f"FAIL: windows_parser_basic: expected 2 elements, got {len(result)}", file=sys.stderr)
        errors += 1
    elif "code c:\\wts\\foo" not in result_strs or "code c:\\wts\\bar" not in result_strs:
        print(f"FAIL: windows_parser_basic: expected paths not in {result_strs!r}", file=sys.stderr)
        errors += 1
    else:
        print("PASS: windows_parser_basic")

    # ------------------------------------------------------------------
    # Test: windows_parser_quoted_paths — path with spaces, verbatim round-trip.
    # ------------------------------------------------------------------
    quoted_line = '"C:\\Program Files\\Microsoft VS Code\\Code.exe" "C:\\wts\\foo bar"'
    with (
        patch("_vscode_processes.os.name", "nt"),
        patch(
            "_vscode_processes._subprocess_util.run",
            return_value=subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout=quoted_line + "\r\n",
                stderr="",
            ),
        ),
    ):
        result = find_open_vscode_paths()
    if len(result) != 1:
        print(f"FAIL: windows_parser_quoted_paths: expected 1 element, got {len(result)}", file=sys.stderr)
        errors += 1
    elif str(next(iter(result))) != quoted_line:
        got = str(next(iter(result)))
        print(f"FAIL: windows_parser_quoted_paths: expected {quoted_line!r}, got {got!r}", file=sys.stderr)
        errors += 1
    else:
        print("PASS: windows_parser_quoted_paths")

    # ------------------------------------------------------------------
    # Test: windows_parser_empty_output — empty stdout returns empty set.
    # ------------------------------------------------------------------
    with (
        patch("_vscode_processes.os.name", "nt"),
        patch(
            "_vscode_processes._subprocess_util.run",
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            ),
        ),
    ):
        result = find_open_vscode_paths()
    if result != set():
        print(f"FAIL: windows_parser_empty_output: expected empty set, got {result}", file=sys.stderr)
        errors += 1
    else:
        print("PASS: windows_parser_empty_output")

    # ------------------------------------------------------------------
    # Test: posix_parser_basic — code lines kept, firefox dropped.
    # ------------------------------------------------------------------
    if os.name != "nt":
        posix_stdout = (
            "/usr/bin/code /home/u/wts/foo\n"
            "firefox --headless\n"
            "/opt/visual-studio-code/code /home/u/wts/bar\n"
        )
        with (
            patch("_vscode_processes.os.name", "posix"),
            patch(
                "_vscode_processes._subprocess_util.run",
                return_value=subprocess.CompletedProcess(
                    args=[], returncode=0, stdout=posix_stdout, stderr=""
                ),
            ),
        ):
            result = find_open_vscode_paths()
        if len(result) != 2:
            print(f"FAIL: posix_parser_basic: expected 2 elements, got {len(result)}", file=sys.stderr)
            errors += 1
        elif any("firefox" in str(p) for p in result):
            print(f"FAIL: posix_parser_basic: firefox not excluded from {result}", file=sys.stderr)
            errors += 1
        else:
            print("PASS: posix_parser_basic")
    else:
        print("SKIP: posix_parser_basic (Windows)")

    # ------------------------------------------------------------------
    # Test: posix_parser_no_code_processes — no code basename -> empty set.
    # ------------------------------------------------------------------
    if os.name != "nt":
        with (
            patch("_vscode_processes.os.name", "posix"),
            patch(
                "_vscode_processes._subprocess_util.run",
                return_value=subprocess.CompletedProcess(
                    args=[],
                    returncode=0,
                    stdout="firefox --headless\n/usr/bin/python script.py\n",
                    stderr="",
                ),
            ),
        ):
            result = find_open_vscode_paths()
        if result != set():
            print(f"FAIL: posix_parser_no_code_processes: expected empty set, got {result}", file=sys.stderr)
            errors += 1
        else:
            print("PASS: posix_parser_no_code_processes")
    else:
        print("SKIP: posix_parser_no_code_processes (Windows)")

    # ------------------------------------------------------------------
    # Test: probe_subprocess_nonzero_exit — rc=1 returns empty set.
    # ------------------------------------------------------------------
    with patch(
        "_vscode_processes._subprocess_util.run",
        return_value=subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="boom"
        ),
    ):
        result = find_open_vscode_paths()
    if result != set():
        print(f"FAIL: probe_subprocess_nonzero_exit: expected empty set, got {result}", file=sys.stderr)
        errors += 1
    else:
        print("PASS: probe_subprocess_nonzero_exit")

    # ------------------------------------------------------------------
    # Test: probe_subprocess_timeout — TimeoutExpired returns empty set.
    # ------------------------------------------------------------------
    with patch(
        "_vscode_processes._subprocess_util.run",
        side_effect=subprocess.TimeoutExpired(cmd=[], timeout=5),
    ):
        result = find_open_vscode_paths()
    if result != set():
        print(f"FAIL: probe_subprocess_timeout: expected empty set, got {result}", file=sys.stderr)
        errors += 1
    else:
        print("PASS: probe_subprocess_timeout")

    # ------------------------------------------------------------------
    # Test: probe_subprocess_oserror — FileNotFoundError returns empty set.
    # ------------------------------------------------------------------
    with patch(
        "_vscode_processes._subprocess_util.run",
        side_effect=FileNotFoundError("powershell missing"),
    ):
        result = find_open_vscode_paths()
    if result != set():
        print(f"FAIL: probe_subprocess_oserror: expected empty set, got {result}", file=sys.stderr)
        errors += 1
    else:
        print("PASS: probe_subprocess_oserror")

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
        # Cmdline ends immediately after the path — no trailing whitespace.
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
