"""Unit tests for plugins/mill/scripts/_paths.py sanitize_filename_component.

Covers:
  - sanitize_filename_component: replaces all Windows-reserved characters
"""
from __future__ import annotations

import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS_DIR = HUB / "plugins" / "mill" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import _paths  # noqa: E402


def test_sanitize_colon() -> None:
    """sanitize_filename_component replaces colon with hyphen."""
    result = _paths.sanitize_filename_component("test:name")
    assert result == "test-name", f"Expected 'test-name', got {result!r}"
    print("PASS sanitize_filename_component -- replaces colon")


def test_sanitize_backslash() -> None:
    """sanitize_filename_component replaces backslash with hyphen."""
    result = _paths.sanitize_filename_component("test\\name")
    assert result == "test-name", f"Expected 'test-name', got {result!r}"
    print("PASS sanitize_filename_component -- replaces backslash")


def test_sanitize_forward_slash() -> None:
    """sanitize_filename_component replaces forward slash with hyphen."""
    result = _paths.sanitize_filename_component("test/name")
    assert result == "test-name", f"Expected 'test-name', got {result!r}"
    print("PASS sanitize_filename_component -- replaces forward slash")


def test_sanitize_asterisk() -> None:
    """sanitize_filename_component replaces asterisk with hyphen."""
    result = _paths.sanitize_filename_component("test*name")
    assert result == "test-name", f"Expected 'test-name', got {result!r}"
    print("PASS sanitize_filename_component -- replaces asterisk")


def test_sanitize_question_mark() -> None:
    """sanitize_filename_component replaces question mark with hyphen."""
    result = _paths.sanitize_filename_component("test?name")
    assert result == "test-name", f"Expected 'test-name', got {result!r}"
    print("PASS sanitize_filename_component -- replaces question mark")


def test_sanitize_double_quote() -> None:
    """sanitize_filename_component replaces double quote with hyphen."""
    result = _paths.sanitize_filename_component('test"name')
    assert result == "test-name", f"Expected 'test-name', got {result!r}"
    print("PASS sanitize_filename_component -- replaces double quote")


def test_sanitize_less_than() -> None:
    """sanitize_filename_component replaces less-than with hyphen."""
    result = _paths.sanitize_filename_component("test<name")
    assert result == "test-name", f"Expected 'test-name', got {result!r}"
    print("PASS sanitize_filename_component -- replaces less-than")


def test_sanitize_greater_than() -> None:
    """sanitize_filename_component replaces greater-than with hyphen."""
    result = _paths.sanitize_filename_component("test>name")
    assert result == "test-name", f"Expected 'test-name', got {result!r}"
    print("PASS sanitize_filename_component -- replaces greater-than")


def test_sanitize_pipe() -> None:
    """sanitize_filename_component replaces pipe with hyphen."""
    result = _paths.sanitize_filename_component("test|name")
    assert result == "test-name", f"Expected 'test-name', got {result!r}"
    print("PASS sanitize_filename_component -- replaces pipe")


def test_sanitize_clean_name_passthrough() -> None:
    """sanitize_filename_component leaves clean names unchanged."""
    clean_name = "Core fix emit_prepare"
    result = _paths.sanitize_filename_component(clean_name)
    assert result == clean_name, f"Expected {clean_name!r}, got {result!r}"
    print("PASS sanitize_filename_component -- clean name passes through")


def test_sanitize_multi_unsafe_name() -> None:
    """sanitize_filename_component handles multi-unsafe names correctly."""
    name = "internal/lock: do x"
    result = _paths.sanitize_filename_component(name)
    # Should contain no reserved characters
    reserved_chars = r':\\/*?"<>|'
    for char in reserved_chars:
        assert char not in result, f"Result {result!r} contains reserved character {char!r}"
    print("PASS sanitize_filename_component -- multi-unsafe name")


def main() -> int:
    tests = [
        test_sanitize_colon,
        test_sanitize_backslash,
        test_sanitize_forward_slash,
        test_sanitize_asterisk,
        test_sanitize_question_mark,
        test_sanitize_double_quote,
        test_sanitize_less_than,
        test_sanitize_greater_than,
        test_sanitize_pipe,
        test_sanitize_clean_name_passthrough,
        test_sanitize_multi_unsafe_name,
    ]
    failures: list[str] = []
    for fn in tests:
        try:
            fn()
        except AssertionError as exc:
            print(f"FAIL [{fn.__name__}]: {exc}", file=sys.stderr)
            failures.append(fn.__name__)
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR [{fn.__name__}]: {exc}", file=sys.stderr)
            failures.append(fn.__name__)
    if failures:
        print(f"\n{len(failures)} test(s) failed: {failures}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
