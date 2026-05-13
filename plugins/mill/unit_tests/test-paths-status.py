"""Unit tests for _paths.status_path (TDD — written before the implementation)."""
from __future__ import annotations

import contextlib
import io
import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS_DIR = HUB / "plugins" / "mill" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import _paths  # noqa: E402


def test_status_path() -> None:
    cfg = {"paths": {"status_md": "_mill/status.md"}}

    # Case 1: file exists -> returns configured path, no [compat] in stderr
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "_mill").mkdir()
        (root / "_mill" / "status.md").write_text("", encoding="utf-8")
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            got = _paths.status_path(root, cfg)
        assert got == root / "_mill" / "status.md", f"case 1: got {got}"
        assert "[compat]" not in buf.getvalue(), "case 1: unexpected [compat] in stderr"
    print("PASS status_path case 1: _mill/status.md exists -> configured path, no stderr")

    # Case 2: _mill/status.md missing, task/status.md present -> compat fallback with [compat] in stderr
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "task").mkdir()
        (root / "task" / "status.md").write_text("", encoding="utf-8")
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            got = _paths.status_path(root, cfg)
        assert got == root / "task" / "status.md", f"case 2: got {got}"
        assert "[compat]" in buf.getvalue(), "case 2: expected [compat] in stderr"
    print("PASS status_path case 2: _mill/ absent, task/status.md present -> task/ path, [compat] stderr")

    # Case 3: neither file exists -> returns configured path, no [compat]
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            got = _paths.status_path(root, cfg)
        assert got == root / "_mill" / "status.md", f"case 3: got {got}"
        assert "[compat]" not in buf.getvalue(), "case 3: unexpected [compat] in stderr"
    print("PASS status_path case 3: neither file exists -> configured path, no stderr")

    # Case 4: cfg has no 'paths' key -> KeyError naming paths.status_md
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        try:
            _paths.status_path(root, {})
            raise AssertionError("case 4: expected KeyError, got none")
        except KeyError as exc:
            assert "paths.status_md" in str(exc), f"case 4: KeyError message missing 'paths.status_md': {exc}"
    print("PASS status_path case 4: cfg={} -> KeyError naming paths.status_md")

    # Case 5: cfg has 'paths' but no 'status_md' key -> KeyError naming paths.status_md
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        try:
            _paths.status_path(root, {"paths": {}})
            raise AssertionError("case 5: expected KeyError, got none")
        except KeyError as exc:
            assert "paths.status_md" in str(exc), f"case 5: KeyError message missing 'paths.status_md': {exc}"
    print("PASS status_path case 5: cfg={'paths': {}} -> KeyError naming paths.status_md")


if __name__ == "__main__":
    try:
        test_status_path()
        print("All status_path tests passed.")
        sys.exit(0)
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
