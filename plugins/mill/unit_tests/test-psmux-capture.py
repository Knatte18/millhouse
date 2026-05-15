"""Unit tests for plugins/mill/scripts/_psmux_capture.py.

Pure-function tests on the output parser extract_response(). Each test
loads a static fixture from fixtures/psmux-capture/ and asserts the
extracted response or exception.
"""
from __future__ import annotations

import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _psmux_capture as _psmux_capture_mod  # noqa: E402


def main() -> int:
    errors = 0
    fixture_base = Path(__file__).resolve().parent / "fixtures" / "psmux-capture"

    # Test 1: clean.txt
    try:
        capture_text = (fixture_base / "clean.txt").read_text()
        result = _psmux_capture_mod.extract_response(
            capture_text, "MILL_BEGIN_AAA", "MILL_END_BBB"
        )
        if result == "PONG":
            print("[OK] clean.txt: extracted single line")
        else:
            print(f"[FAIL] clean.txt: expected 'PONG', got {result!r}")
            errors += 1
    except Exception as e:
        print(f"[FAIL] clean.txt: raised {e!r}")
        errors += 1

    # Test 2: multiline.txt
    try:
        capture_text = (fixture_base / "multiline.txt").read_text()
        result = _psmux_capture_mod.extract_response(
            capture_text, "MILL_BEGIN_AAA", "MILL_END_BBB"
        )
        expected = (
            "Thread code shimmers,\n"
            "PowerShellthreadsweaveasone\n"
            "Into data streams."
        )
        if result == expected:
            print("[OK] multiline.txt: extracted three response lines")
        else:
            print(f"[FAIL] multiline.txt: expected {expected!r}, got {result!r}")
            errors += 1
    except Exception as e:
        print(f"[FAIL] multiline.txt: raised {e!r}")
        errors += 1

    # Test 3: with-status.txt
    try:
        capture_text = (fixture_base / "with-status.txt").read_text()
        result = _psmux_capture_mod.extract_response(
            capture_text, "MILL_BEGIN_AAA", "MILL_END_BBB"
        )
        expected = "First response line\nSecond response line"
        if result == expected:
            print("[OK] with-status.txt: excluded status line after marker")
        else:
            print(f"[FAIL] with-status.txt: expected {expected!r}, got {result!r}")
            errors += 1
    except Exception as e:
        print(f"[FAIL] with-status.txt: raised {e!r}")
        errors += 1

    # Test 4: with-scrollback.txt
    try:
        capture_text = (fixture_base / "with-scrollback.txt").read_text()
        result = _psmux_capture_mod.extract_response(
            capture_text, "MILL_BEGIN_AAA", "MILL_END_BBB"
        )
        expected = "\n".join(f"LINE_{i}" for i in range(1, 81))
        if result == expected:
            print("[OK] with-scrollback.txt: extracted 80 lines without truncation")
        else:
            print(f"[FAIL] with-scrollback.txt: length mismatch")
            errors += 1
    except Exception as e:
        print(f"[FAIL] with-scrollback.txt: raised {e!r}")
        errors += 1

    # Test 5: whitespace-compressed.txt
    try:
        capture_text = (fixture_base / "whitespace-compressed.txt").read_text()
        result = _psmux_capture_mod.extract_response(
            capture_text, "MILL_BEGIN_AAA", "MILL_END_BBB"
        )
        expected = "ResponsewithoutspaceBetweenWords"
        if result == expected:
            print("[OK] whitespace-compressed.txt: preserved missing space")
        else:
            print(f"[FAIL] whitespace-compressed.txt: expected {expected!r}, got {result!r}")
            errors += 1
    except Exception as e:
        print(f"[FAIL] whitespace-compressed.txt: raised {e!r}")
        errors += 1

    # Test 6: quoted-marker-text.txt
    try:
        capture_text = (fixture_base / "quoted-marker-text.txt").read_text()
        result = _psmux_capture_mod.extract_response(
            capture_text, "MILL_BEGIN_AAA", "MILL_END_BBB"
        )
        expected = (
            "This response mentions `MILL_BEGIN_AAA` inside backticks.\n"
            "It also has `MILL_END_BBB` quoted here.\n"
            "But these are not on their own lines."
        )
        if result == expected:
            print("[OK] quoted-marker-text.txt: ignored mid-line marker mentions")
        else:
            print(f"[FAIL] quoted-marker-text.txt: expected {expected!r}, got {result!r}")
            errors += 1
    except Exception as e:
        print(f"[FAIL] quoted-marker-text.txt: raised {e!r}")
        errors += 1

    # Test 7: no-end-marker.txt
    try:
        capture_text = (fixture_base / "no-end-marker.txt").read_text()
        result = _psmux_capture_mod.extract_response(
            capture_text, "MILL_BEGIN_AAA", "MILL_END_BBB"
        )
        print(f"[FAIL] no-end-marker.txt: expected MarkerNotFoundError, got {result!r}")
        errors += 1
    except _psmux_capture_mod.MarkerNotFoundError:
        print("[OK] no-end-marker.txt: raised MarkerNotFoundError")
    except Exception as e:
        print(f"[FAIL] no-end-marker.txt: raised {type(e).__name__}, expected MarkerNotFoundError")
        errors += 1

    # Test 8: markers-reversed.txt
    try:
        capture_text = (fixture_base / "markers-reversed.txt").read_text()
        result = _psmux_capture_mod.extract_response(
            capture_text, "MILL_BEGIN_AAA", "MILL_END_BBB"
        )
        print(f"[FAIL] markers-reversed.txt: expected MarkerNotFoundError, got {result!r}")
        errors += 1
    except _psmux_capture_mod.MarkerNotFoundError:
        print("[OK] markers-reversed.txt: raised MarkerNotFoundError")
    except Exception as e:
        print(f"[FAIL] markers-reversed.txt: raised {type(e).__name__}, expected MarkerNotFoundError")
        errors += 1

    # Test 9: polling-not-ready.txt
    try:
        capture_text = (fixture_base / "polling-not-ready.txt").read_text()
        result = _psmux_capture_mod.extract_response(
            capture_text, "MILL_BEGIN_AAA", "MILL_END_BBB"
        )
        print(f"[FAIL] polling-not-ready.txt: expected MarkerNotFoundError, got {result!r}")
        errors += 1
    except _psmux_capture_mod.MarkerNotFoundError:
        print("[OK] polling-not-ready.txt: raised MarkerNotFoundError")
    except Exception as e:
        print(f"[FAIL] polling-not-ready.txt: raised {type(e).__name__}, expected MarkerNotFoundError")
        errors += 1

    return errors


if __name__ == "__main__":
    sys.exit(main())
