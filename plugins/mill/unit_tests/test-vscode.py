"""Unit tests for plugins/mill/scripts/_vscode.py."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _vscode import render_settings, write_settings  # noqa: E402


def main() -> int:
    errors = 0

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

    # render_settings: neither provided -> ValueError
    try:
        render_settings(color_hex="#000000")
        errors += 1
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

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All _vscode unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
