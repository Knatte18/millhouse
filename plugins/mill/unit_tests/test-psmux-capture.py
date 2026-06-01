"""Unit tests for plugins/mill/scripts/_psmux_capture.py.

Pure-function tests on the output parser extract_response(). Each test
uses an inline multi-line string snapshot and asserts the extracted
response or exception.
"""
from __future__ import annotations

import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _psmux_capture as _psmux_capture_mod  # noqa: E402


def main() -> int:
    errors = 0

    # Test 1: Basic response
    try:
        snapshot = r"""  ❯
● First line
Second line
  ❯ """
        result = _psmux_capture_mod.extract_response(snapshot)
        expected = "First line\nSecond line"
        if result == expected:
            print("[OK] Test 1: Basic response")
        else:
            print(f"[FAIL] Test 1: expected {expected!r}, got {result!r}")
            errors += 1
    except Exception as e:
        print(f"[FAIL] Test 1: raised {e!r}")
        errors += 1

    # Test 2: Multi-line response (10 lines total)
    try:
        snapshot = r"""  ❯
● Start line
Line 2
Line 3
Line 4
Line 5
Line 6
Line 7
Line 8
Line 9
Line 10
  ❯ """
        result = _psmux_capture_mod.extract_response(snapshot)
        # Should contain all 10 lines, with bullet prefix stripped from first
        expected_lines = ["Start line"] + [f"Line {i}" for i in range(2, 11)]
        expected = "\n".join(expected_lines)
        if result == expected:
            print("[OK] Test 2: Multi-line response")
        else:
            print(f"[FAIL] Test 2: expected {expected!r}, got {result!r}")
            errors += 1
    except Exception as e:
        print(f"[FAIL] Test 2: raised {e!r}")
        errors += 1

    # Test 3: Bullet-prefix strip
    try:
        snapshot = r"""  ❯
● extra space
  ❯ """
        result = _psmux_capture_mod.extract_response(snapshot)
        expected = "extra space"
        if result == expected:
            print("[OK] Test 3: Bullet-prefix strip")
        else:
            print(f"[FAIL] Test 3: expected {expected!r}, got {result!r}")
            errors += 1
    except Exception as e:
        print(f"[FAIL] Test 3: raised {e!r}")
        errors += 1

    # Test 4: Session history (multiple prior blocks, only current response returned)
    try:
        snapshot = r"""  ❯
● Prior1
prior1 continuation
  ❯
● Prior2
prior2 continuation
  ❯
● Current response
  ❯ """
        result = _psmux_capture_mod.extract_response(snapshot)
        expected = "Current response"
        if result == expected:
            print("[OK] Test 4: Session history")
        else:
            print(f"[FAIL] Test 4: expected {expected!r}, got {result!r}")
            errors += 1
    except Exception as e:
        print(f"[FAIL] Test 4: raised {e!r}")
        errors += 1

    # Test 5: No bullet prefix
    try:
        snapshot = r"""  ❯
Response text
  ❯ """
        result = _psmux_capture_mod.extract_response(snapshot)
        print(f"[FAIL] Test 5: expected MarkerNotFoundError, got {result!r}")
        errors += 1
    except _psmux_capture_mod.MarkerNotFoundError:
        print("[OK] Test 5: No bullet prefix raises MarkerNotFoundError")
    except Exception as e:
        print(f"[FAIL] Test 5: raised {type(e).__name__}, expected MarkerNotFoundError")
        errors += 1

    # Test 6: No idle char
    try:
        snapshot = r"""● Response text"""
        result = _psmux_capture_mod.extract_response(snapshot)
        print(f"[FAIL] Test 6: expected MarkerNotFoundError, got {result!r}")
        errors += 1
    except _psmux_capture_mod.MarkerNotFoundError:
        print("[OK] Test 6: No idle char raises MarkerNotFoundError")
    except Exception as e:
        print(f"[FAIL] Test 6: raised {type(e).__name__}, expected MarkerNotFoundError")
        errors += 1

    # Test 7: Whitespace variants
    try:
        snapshot = r"""  ❯ done
  ● First line
Second line
  ❯ """
        result = _psmux_capture_mod.extract_response(snapshot)
        expected = "First line\nSecond line"
        if result == expected:
            print("[OK] Test 7: Whitespace variants")
        else:
            print(f"[FAIL] Test 7: expected {expected!r}, got {result!r}")
            errors += 1
    except Exception as e:
        print(f"[FAIL] Test 7: raised {e!r}")
        errors += 1

    # Test 8: Completion marker stripped
    try:
        snapshot = r"""  ❯
● PONG

✻ Cogitated for 5s

────────────
❯
────────────
? for shortcuts"""
        result = _psmux_capture_mod.extract_response(snapshot)
        expected = "PONG"
        if result == expected:
            print("[OK] Test 8: Completion marker stripped")
        else:
            print(f"[FAIL] Test 8: expected {expected!r}, got {result!r}")
            errors += 1
    except Exception as e:
        print(f"[FAIL] Test 8: raised {e!r}")
        errors += 1

    # Test 9: Auto-suggest not included
    try:
        snapshot = r"""  ❯
● Hello world

✻ Cooked for 2s

────────────
❯ show an example
────────────
? for shortcuts"""
        result = _psmux_capture_mod.extract_response(snapshot)
        expected = "Hello world"
        if result == expected:
            print("[OK] Test 9: Auto-suggest not included")
        else:
            print(f"[FAIL] Test 9: expected {expected!r}, got {result!r}")
            errors += 1
    except Exception as e:
        print(f"[FAIL] Test 9: raised {e!r}")
        errors += 1

    # Test 10: Multi-line response stripped cleanly
    try:
        snapshot = r"""  ❯
● Line one
Line two

✻ Brewed for 3s

────────────
❯
────────────"""
        result = _psmux_capture_mod.extract_response(snapshot)
        expected = "Line one\nLine two"
        if result.strip() == expected.strip():
            print("[OK] Test 10: Multi-line response stripped cleanly")
        else:
            print(f"[FAIL] Test 10: expected {expected!r}, got {result!r}")
            errors += 1
    except Exception as e:
        print(f"[FAIL] Test 10: raised {e!r}")
        errors += 1

    # Test 11: U+FFFD (replacement char) after bullet
    try:
        snapshot = "  ❯\n●�First line\n  ❯ "
        result = _psmux_capture_mod.extract_response(snapshot)
        expected = "First line"
        if result == expected:
            print("[OK] Test 11: U+FFFD after bullet (replacement char)")
        else:
            print(f"[FAIL] Test 11: expected {expected!r}, got {result!r}")
            errors += 1
    except Exception as e:
        print(f"[FAIL] Test 11: raised {e!r}")
        errors += 1

    # Test 12: U+00A0 (non-breaking space) after bullet
    try:
        snapshot = "  ❯\n● First line\n  ❯ "
        result = _psmux_capture_mod.extract_response(snapshot)
        expected = "First line"
        if result == expected:
            print("[OK] Test 12: U+00A0 after bullet (NBSP)")
        else:
            print(f"[FAIL] Test 12: expected {expected!r}, got {result!r}")
            errors += 1
    except Exception as e:
        print(f"[FAIL] Test 12: raised {e!r}")
        errors += 1

    # Test 13: ASCII space after bullet (regression guard)
    try:
        snapshot = "  ❯\n● First line\n  ❯ "
        result = _psmux_capture_mod.extract_response(snapshot)
        expected = "First line"
        if result == expected:
            print("[OK] Test 13: ASCII space after bullet (regression guard)")
        else:
            print(f"[FAIL] Test 13: expected {expected!r}, got {result!r}")
            errors += 1
    except Exception as e:
        print(f"[FAIL] Test 13: raised {e!r}")
        errors += 1

    return errors


if __name__ == "__main__":
    sys.exit(main())
