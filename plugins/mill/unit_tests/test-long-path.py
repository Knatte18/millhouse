"""
Unit tests for _long_path.to_extended platform-gated prefixing behaviour.

Covers idempotency on an already-prefixed string, drive-absolute and UNC path prefixing on Windows,
and the POSIX/non-Windows no-op path (both under the real test-environment platform and under an
explicit non-``win32`` mock), for the shared long-path helper introduced for the Windows
verify-baseline teardown WinError 145 fix.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _long_path  # noqa: E402


def main() -> int:
    passed = 0
    failed = 0

    def ok(name: str) -> None:
        nonlocal passed
        passed += 1
        print(f"PASS: {name}")

    def fail(name: str, exc: Exception) -> None:
        nonlocal failed
        failed += 1
        print(f"FAIL: {name}: {exc}", file=sys.stderr)

    # --- already-prefixed idempotency case ---
    try:
        with patch("_long_path.sys.platform", "win32"):
            result = _long_path.to_extended(Path("\\\\?\\C:\\foo\\bar"))
        assert result == "\\\\?\\C:\\foo\\bar", f"unexpected result: {result!r}"
        ok("already-prefixed idempotency case")
    except Exception as exc:
        fail("already-prefixed idempotency case", exc)

    # --- drive-absolute path case ---
    try:
        with patch("_long_path.sys.platform", "win32"):
            result = _long_path.to_extended(Path("C:\\foo\\bar"))
        assert result == "\\\\?\\C:\\foo\\bar", f"unexpected result: {result!r}"
        ok("drive-absolute path case")
    except Exception as exc:
        fail("drive-absolute path case", exc)

    # --- UNC path case ---
    try:
        with patch("_long_path.sys.platform", "win32"):
            result = _long_path.to_extended(Path("\\\\server\\share\\x"))
        assert result == "\\\\?\\UNC\\server\\share\\x", f"unexpected result: {result!r}"
        ok("UNC path case")
    except Exception as exc:
        fail("UNC path case", exc)

    # --- POSIX no-op case ---
    try:
        path = Path("/some/posix/path")
        result = _long_path.to_extended(path)
        assert result == str(path), f"unexpected result: {result!r}"

        with patch("_long_path.sys.platform", "darwin"):
            result = _long_path.to_extended(path)
        assert result == str(path), f"unexpected result under darwin mock: {result!r}"
        ok("POSIX no-op case")
    except Exception as exc:
        fail("POSIX no-op case", exc)

    print("", file=sys.stderr)
    if failed:
        print(f"FAIL -- {failed} of {passed + failed}", file=sys.stderr)
        return 1
    print(f"PASS -- all {passed} tests", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
