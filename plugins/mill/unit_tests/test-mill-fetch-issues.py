"""Unit tests for plugins/mill/scripts/mill-fetch-issues.py."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

# Load mill-fetch-issues.py via importlib (hyphenated name).
_SCRIPT = HUB / "plugins" / "mill" / "scripts" / "mill-fetch-issues.py"
_spec = importlib.util.spec_from_file_location("mill_fetch_issues", _SCRIPT)
mill_fetch_issues = importlib.util.module_from_spec(_spec)
sys.modules["mill_fetch_issues"] = mill_fetch_issues
_spec.loader.exec_module(mill_fetch_issues)

from _gh_issues import GhError  # noqa: E402


def _make_git_repo(tmp: Path) -> Path:
    """Initialise a minimal git repo under ``tmp`` and return its path."""
    subprocess.run(
        ["git", "init", str(tmp)], check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp), "commit", "--allow-empty", "-m", "init"],
        check=True, capture_output=True,
    )
    return tmp


_FIXTURE_ISSUES = [
    {"number": 1, "title": "First issue", "body": "body1", "labels": [], "createdAt": "2026-01-01"},
    {"number": 2, "title": "Second issue", "body": "body2", "labels": [], "createdAt": "2026-01-02"},
]


def main() -> int:
    errors = 0

    # ------------------------------------------------------------------
    # Test: happy path -- issues written to default path, path printed.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _make_git_repo(root)

        printed_lines: list[str] = []

        def mock_print(*args, **kwargs):
            if not kwargs.get("file"):
                printed_lines.append(str(args[0]) if args else "")

        with (
            patch("mill_fetch_issues.resolve_git_root", return_value=root),
            patch("mill_fetch_issues._gh_issues.fetch", return_value=_FIXTURE_ISSUES),
            patch("builtins.print", side_effect=mock_print),
        ):
            rc = mill_fetch_issues.main([])

        if rc != 0:
            print(f"FAIL: happy path returned {rc}, expected 0", file=sys.stderr)
            errors += 1
        else:
            default_out = root / ".scratch" / "issues.json"
            if not default_out.exists():
                print("FAIL: issues.json not written to default path", file=sys.stderr)
                errors += 1
            else:
                written = json.loads(default_out.read_text(encoding="utf-8"))
                if written != _FIXTURE_ISSUES:
                    print(
                        f"FAIL: written content mismatch: {written!r}",
                        file=sys.stderr,
                    )
                    errors += 1
                elif not printed_lines or str(default_out.resolve()) not in printed_lines[-1]:
                    print(
                        f"FAIL: path not printed as last stdout line; got {printed_lines!r}",
                        file=sys.stderr,
                    )
                    errors += 1
                else:
                    print("PASS: happy path -- issues written, path printed as last stdout line")

    # ------------------------------------------------------------------
    # Test: --out override writes to the specified path.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _make_git_repo(root)

        custom_out = root / "custom" / "out.json"

        with (
            patch("mill_fetch_issues.resolve_git_root", return_value=root),
            patch("mill_fetch_issues._gh_issues.fetch", return_value=_FIXTURE_ISSUES),
        ):
            rc = mill_fetch_issues.main(["--out", str(custom_out)])

        if rc != 0:
            print(f"FAIL: --out override returned {rc}, expected 0", file=sys.stderr)
            errors += 1
        elif not custom_out.exists():
            print("FAIL: --out path not created", file=sys.stderr)
            errors += 1
        else:
            print("PASS: --out override writes to specified path")

    # ------------------------------------------------------------------
    # Test: GhError from fetch -> returns exit code 1.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _make_git_repo(root)

        with (
            patch("mill_fetch_issues.resolve_git_root", return_value=root),
            patch("mill_fetch_issues._gh_issues.fetch", side_effect=GhError("auth failure")),
        ):
            rc = mill_fetch_issues.main([])

        if rc != 1:
            print(f"FAIL: GhError path returned {rc}, expected 1", file=sys.stderr)
            errors += 1
        else:
            print("PASS: GhError from fetch -> exit code 1")

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All mill-fetch-issues unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
