"""Unit tests for plugins/mill/scripts/_preflight.py.

Covers:
  - missing_helpers: returns missing names from a temp scripts dir
  - missing_helpers: returns [] when all present
  - check_helpers: returns non-zero + prints ASCII actionable message when missing
  - check_helpers: returns 0 when all present
  - check_helpers: with CLAUDE_PLUGIN_ROOT unset, falls back to _preflight.py's own dir
"""
from __future__ import annotations

import io
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS_DIR = HUB / "plugins" / "mill" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import _preflight  # noqa: E402


def test_missing_helpers_all_present() -> None:
    """missing_helpers returns [] when all files exist in scripts_dir."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # Create dummy helper files
        (tmp_path / "_archive_tag.py").write_text("# dummy\n")
        (tmp_path / "_other_helper.py").write_text("# dummy\n")

        result = _preflight.missing_helpers(["_archive_tag", "_other_helper"], tmp_path)
        assert result == [], f"Expected [], got {result!r}"

    print("PASS missing_helpers — returns [] when all files present")


def test_missing_helpers_some_missing() -> None:
    """missing_helpers returns names of missing files."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # Create only one file
        (tmp_path / "_archive_tag.py").write_text("# dummy\n")

        result = _preflight.missing_helpers(["_archive_tag", "_missing_helper"], tmp_path)
        assert result == ["_missing_helper"], (
            f"Expected ['_missing_helper'], got {result!r}"
        )

    print("PASS missing_helpers — returns missing names")


def test_missing_helpers_all_missing() -> None:
    """missing_helpers returns all names when none of the files exist."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # Create no files

        result = _preflight.missing_helpers(["_archive_tag", "_other_helper"], tmp_path)
        assert set(result) == {"_archive_tag", "_other_helper"}, (
            f"Expected both missing, got {result!r}"
        )

    print("PASS missing_helpers — returns all names when all missing")


def test_check_helpers_all_present() -> None:
    """check_helpers returns 0 when all helpers are present."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # Create dummy helper files
        (tmp_path / "_archive_tag.py").write_text("# dummy\n")

        with patch.dict(os.environ, {"CLAUDE_PLUGIN_ROOT": str(tmp_path.parent)}):
            # Adjust: CLAUDE_PLUGIN_ROOT points to parent, so scripts is a subdir
            scripts_dir = tmp_path.parent / "scripts"
            scripts_dir.mkdir(exist_ok=True)
            (scripts_dir / "_archive_tag.py").write_text("# dummy\n")

            rc = _preflight.check_helpers(["_archive_tag"])
            assert rc == 0, f"Expected 0, got {rc}"

    print("PASS check_helpers — returns 0 when all helpers present")


def test_check_helpers_missing_prints_message() -> None:
    """check_helpers returns non-zero + prints ASCII actionable message when missing."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # Create scripts dir but leave it empty (no _archive_tag.py)
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()

        with patch.dict(os.environ, {"CLAUDE_PLUGIN_ROOT": str(tmp_path)}):
            # Capture stderr
            stderr_capture = io.StringIO()
            with patch("sys.stderr", stderr_capture):
                rc = _preflight.check_helpers(["_archive_tag"])

            assert rc != 0, f"Expected non-zero exit code, got {rc}"
            stderr_output = stderr_capture.getvalue()
            # Check for ASCII-only actionable message
            assert "error" in stderr_output.lower(), (
                f"Expected 'error' in message, got: {stderr_output!r}"
            )
            assert "_archive_tag" in stderr_output, (
                f"Expected '_archive_tag' in message, got: {stderr_output!r}"
            )
            assert "cache" in stderr_output.lower(), (
                f"Expected 'cache' in message, got: {stderr_output!r}"
            )
            # Verify ASCII-only (no non-ASCII bytes)
            stderr_output.encode("ascii")

    print("PASS check_helpers — returns non-zero + prints actionable message")


def test_check_helpers_fallback_to_own_dir() -> None:
    """check_helpers falls back to _preflight.py's own dir when CLAUDE_PLUGIN_ROOT unset."""
    # When CLAUDE_PLUGIN_ROOT is unset, check_helpers should use _preflight.py's own directory
    # and find _preflight.py itself there, so check_helpers(["_preflight"]) should return 0.

    with patch.dict(os.environ, {}, clear=False):
        # Make sure CLAUDE_PLUGIN_ROOT is not set
        if "CLAUDE_PLUGIN_ROOT" in os.environ:
            del os.environ["CLAUDE_PLUGIN_ROOT"]

        rc = _preflight.check_helpers(["_preflight"])
        assert rc == 0, (
            f"Expected 0 when checking for _preflight in fallback dir, got {rc}"
        )

    print("PASS check_helpers — fallback to _preflight.py's own dir works")


def test_check_helpers_fallback_missing_module() -> None:
    """check_helpers with unset CLAUDE_PLUGIN_ROOT reports missing module correctly."""
    with patch.dict(os.environ, {}, clear=False):
        # Make sure CLAUDE_PLUGIN_ROOT is not set
        if "CLAUDE_PLUGIN_ROOT" in os.environ:
            del os.environ["CLAUDE_PLUGIN_ROOT"]

        stderr_capture = io.StringIO()
        with patch("sys.stderr", stderr_capture):
            rc = _preflight.check_helpers(["_nonexistent_helper"])

        assert rc != 0, f"Expected non-zero, got {rc}"
        stderr_output = stderr_capture.getvalue()
        assert "_nonexistent_helper" in stderr_output, (
            f"Expected '_nonexistent_helper' in error message, got: {stderr_output!r}"
        )
        # Verify ASCII-only
        stderr_output.encode("ascii")

    print("PASS check_helpers — fallback reports missing module correctly")
