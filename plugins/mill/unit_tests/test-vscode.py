"""Unit tests for plugins/mill/scripts/_vscode.py and _vscode_processes.py.

Two small helpers consolidated into one file (was test-vscode.py +
test-vscode-processes.py, merged 2026-05-28 for #388).
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _vscode import render_settings, write_settings  # noqa: E402
from _vscode_processes import _path_matches_cmdline  # noqa: E402


def _test_render_settings(errors: list[int]) -> None:
    """Tests for _vscode.render_settings / write_settings."""
    # render_settings: short_name only -> hub form title
    result = render_settings(color_hex="#000000", short_name="MH")
    assert '"window.title": "MH"' in result, f"hub form FAIL: {result}"
    print('PASS: render_settings(short_name="MH") -> "window.title": "MH"')

    # render_settings: short_name + slug -> worktree form title
    result = render_settings(color_hex="#000000", short_name="MH", slug="foo")
    assert '"window.title": "MH: foo"' in result, f"worktree form FAIL: {result}"
    print('PASS: render_settings(short_name="MH", slug="foo") -> "window.title": "MH: foo"')

    # render_settings: window_title wins over short_name
    result = render_settings(color_hex="#000000", window_title="custom", short_name="MH")
    assert '"window.title": "custom"' in result, f"window_title wins FAIL: {result}"
    assert '"window.title": "MH"' not in result
    print("PASS: render_settings window_title wins over short_name")

    # render_settings: explicit window_title
    result = render_settings(color_hex="#000000", window_title="custom")
    assert '"window.title": "custom"' in result, f"explicit title FAIL: {result}"
    print('PASS: render_settings(window_title="custom") -> "window.title": "custom"')

    # render_settings: files.watcherExclude contains junction globs
    result = render_settings(color_hex="#000000", window_title="test")
    assert '"files.watcherExclude"' in result, f"watcherExclude key missing FAIL: {result}"
    assert '"**/.portals/**": true' in result, f"portals glob missing FAIL: {result}"
    assert '"**/.wiki/**": true' in result, f"wiki glob missing FAIL: {result}"
    assert '"**/.active/**": true' in result, f"active glob missing FAIL: {result}"
    print("PASS: render_settings includes files.watcherExclude with junction globs")

    # render_settings: neither provided -> ValueError
    try:
        render_settings(color_hex="#000000")
        errors[0] += 1
        print("FAIL: expected ValueError when neither window_title nor short_name given", file=sys.stderr)
    except ValueError as exc:
        assert "window_title" in str(exc) or "short_name" in str(exc)
        print("PASS: render_settings() neither arg -> ValueError")

    # write_settings: writes to target, creates parent dirs
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "nested" / "dir" / "settings.json"
        write_settings(color_hex="#abcdef", target=target, window_title="Test Title")
        assert target.exists()
        contents = target.read_text(encoding="utf-8")
        assert '"window.title": "Test Title"' in contents
        assert "#abcdef" in contents
        print("PASS: write_settings writes to target and creates parent dirs")


def _test_path_matches_cmdline(errors: list[int]) -> None:
    """Tests for _vscode_processes._path_matches_cmdline."""
    with tempfile.TemporaryDirectory() as tmpdir:
        foo = Path(tmpdir) / "foo"
        foo.mkdir()
        resolved = str(foo.resolve())
        ok = _path_matches_cmdline(foo, f"code {resolved}")
    if not ok:
        print("FAIL: path_match_helper_bare: expected True", file=sys.stderr)
        errors[0] += 1
    else:
        print("PASS: path_match_helper_bare")

    with tempfile.TemporaryDirectory() as tmpdir:
        foo = Path(tmpdir) / "foo"
        foo.mkdir()
        resolved = str(foo.resolve())
        ok = _path_matches_cmdline(foo, f"code {resolved}{os.sep}")
    if not ok:
        print("FAIL: path_match_helper_trailing_slash: expected True", file=sys.stderr)
        errors[0] += 1
    else:
        print("PASS: path_match_helper_trailing_slash")

    with tempfile.TemporaryDirectory() as tmpdir:
        foo = Path(tmpdir) / "foo"
        foo.mkdir()
        resolved = str(foo.resolve())
        ok = _path_matches_cmdline(foo, f"code {resolved}{os.sep}src")
    if ok:
        print("FAIL: path_match_helper_subpath_excluded: expected False, got True", file=sys.stderr)
        errors[0] += 1
    else:
        print("PASS: path_match_helper_subpath_excluded")

    with tempfile.TemporaryDirectory() as tmpdir:
        foo = Path(tmpdir) / "foo"
        foo.mkdir()
        resolved = str(foo.resolve())
        ok = _path_matches_cmdline(foo, f"code {resolved}-bar")
    if ok:
        print("FAIL: path_match_helper_prefix_collision: expected False, got True", file=sys.stderr)
        errors[0] += 1
    else:
        print("PASS: path_match_helper_prefix_collision")

    with tempfile.TemporaryDirectory() as tmpdir:
        foo_bar = Path(tmpdir) / "foo bar"
        foo_bar.mkdir()
        resolved = str(foo_bar.resolve())
        ok = _path_matches_cmdline(foo_bar, f'code "{resolved}"')
    if not ok:
        print("FAIL: path_match_helper_quoted_path: expected True", file=sys.stderr)
        errors[0] += 1
    else:
        print("PASS: path_match_helper_quoted_path")

    with tempfile.TemporaryDirectory() as tmpdir:
        foo = Path(tmpdir) / "foo"
        foo.mkdir()
        resolved = str(foo.resolve())
        ok = _path_matches_cmdline(foo, f"code {resolved}")
    if not ok:
        print("FAIL: path_match_helper_end_of_string: expected True", file=sys.stderr)
        errors[0] += 1
    else:
        print("PASS: path_match_helper_end_of_string")

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
            errors[0] += 1
        else:
            print("PASS: path_match_helper_windows_case_insensitive")


def main() -> int:
    errors = [0]
    _test_render_settings(errors)
    _test_path_matches_cmdline(errors)
    if errors[0]:
        print(f"\n{errors[0]} test(s) FAILED", file=sys.stderr)
        return 1
    print("All _vscode + _vscode_processes unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
