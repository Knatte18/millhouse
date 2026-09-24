"""Unit tests for plugins/mill/scripts/_vscode_keybindings.py.

Every disk test uses a tempdir path; the real user keybindings.json is never touched.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _vscode_keybindings import (  # noqa: E402
    BLOCK_BEGIN,
    BLOCK_END,
    KeybindingsParseError,
    desired_bindings,
    keybindings_path,
    merge_bindings,
    strip_jsonc,
    write_bindings,
)

EXPECTED_LABELS = [
    "mill: start",
    "mill: start-auto",
    "mill: start-orch",
    "mill: plan",
    "mill: go",
    "mill: quick",
]

USER_ARRAY = (
    "// my bindings\n"
    "[\n"
    '  { "key": "ctrl+k", "command": "a.b" }, // keep me\n'
    "  /* block [ comment \" */\n"
    '  { "key": "ctrl+j", "command": "c.d" }\n'
    "]\n"
)


def _mill_keys(text: str) -> list[str]:
    """Return the keys of every entry, parsed from ``text``."""
    return [entry["key"] for entry in json.loads(strip_jsonc(text))]


def _test_desired_bindings() -> None:
    bindings = desired_bindings()
    assert [b["key"] for b in bindings] == [f"alt+shift+{n}" for n in range(1, 7)]
    assert [b["args"] for b in bindings] == EXPECTED_LABELS
    assert {b["command"] for b in bindings} == {"workbench.action.tasks.runTask"}


def _test_keybindings_path() -> None:
    home = Path("/home/tester")
    assert keybindings_path("linux", home=home) == home / ".config/Code/User/keybindings.json"
    assert keybindings_path("darwin", home=home) == (
        home / "Library/Application Support/Code/User/keybindings.json"
    )
    assert keybindings_path("win32", env={"APPDATA": "C:/Users/t/AppData/Roaming"}) == Path(
        "C:/Users/t/AppData/Roaming/Code/User/keybindings.json"
    )
    for bad_call in (lambda: keybindings_path("win32", env={}), lambda: keybindings_path("plan9")):
        try:
            bad_call()
        except ValueError:
            continue
        raise AssertionError("expected ValueError")


def _test_strip_jsonc() -> None:
    assert json.loads(strip_jsonc('[1, // c\n 2 /* x */]')) == [1, 2]
    assert json.loads(strip_jsonc('["a // not", "b /* not */"]')) == ["a // not", "b /* not */"]
    assert json.loads(strip_jsonc(r'["q\"//x", 1]')) == ['q"//x', 1]
    assert json.loads(strip_jsonc('[1, 2,]')) == [1, 2]
    assert json.loads(strip_jsonc('[{"a": 1,},\n]')) == [{"a": 1}]
    assert json.loads(strip_jsonc('[1 // ] " } \n, /* ", [ */ 2]')) == [1, 2]


def _test_merge_empty_text() -> None:
    merged, warnings = merge_bindings("  \n")
    assert warnings == []
    assert merged.startswith("[\n") and merged.endswith("]\n")
    assert merged.count(BLOCK_BEGIN) == 1 and merged.count(BLOCK_END) == 1
    assert _mill_keys(merged) == [f"alt+shift+{n}" for n in range(1, 7)]


def _test_merge_into_existing_array() -> None:
    merged, warnings = merge_bindings(USER_ARRAY)
    assert warnings == []
    assert merged.startswith(
        "// my bindings\n[\n"
        '  { "key": "ctrl+k", "command": "a.b" }, // keep me\n'
        "  /* block [ comment \" */\n"
        '  { "key": "ctrl+j", "command": "c.d" },\n'
    ), merged
    assert merged.endswith("  " + BLOCK_END + "\n]\n")
    assert _mill_keys(merged) == ["ctrl+k", "ctrl+j"] + [f"alt+shift+{n}" for n in range(1, 7)]


def _test_merge_trailing_comma_and_empty_array() -> None:
    merged, _ = merge_bindings('[\n  { "key": "ctrl+k", "command": "a" },\n]\n')
    assert merged.startswith('[\n  { "key": "ctrl+k", "command": "a" },\n  ' + BLOCK_BEGIN)
    assert ",," not in merged.replace(" ", "")
    assert len(_mill_keys(merged)) == 7
    merged, _ = merge_bindings("[]")
    assert merged.startswith("[\n  " + BLOCK_BEGIN) and merged.endswith("\n]")
    assert len(_mill_keys(merged)) == 6


def _test_merge_is_idempotent() -> None:
    first, _ = merge_bindings(USER_ARRAY)
    second, _ = merge_bindings(first)
    assert second == first


def _test_merge_replaces_block_in_place() -> None:
    first, _ = merge_bindings("[]")
    stale = first.replace("alt+shift+2", "alt+shift+9")
    with_user_entry = stale.replace(
        "\n]", ',\n  { "key": "ctrl+u", "command": "u.v" }\n]'
    )
    merged, warnings = merge_bindings(with_user_entry)
    assert warnings == []
    assert "alt+shift+9" not in merged
    assert merged.index(BLOCK_BEGIN) < merged.index("ctrl+u")
    keys = _mill_keys(merged)
    assert keys == [f"alt+shift+{n}" for n in range(1, 7)] + ["ctrl+u"]
    # The block is followed by a user entry, so its last binding needs a trailing comma.
    assert merged.split(BLOCK_END)[0].rstrip().rstrip("/").rstrip().endswith('"mill: quick"},')
    assert json.loads(strip_jsonc(merged))[5]["args"] == "mill: quick"


def _test_merge_conflicts() -> None:
    for variant in ("Alt+Shift+4", " alt + shift+4 ", "ALT+SHIFT+4"):
        text = f'[\n  {{ "key": "{variant}", "command": "user.cmd" }}\n]\n'
        merged, warnings = merge_bindings(text)
        assert warnings == [
            'alt+shift+4 is already bound to user.cmd; skipped mill binding "mill: plan"'
        ], warnings
        assert all(ord(char) < 128 for char in warnings[0])
        block_keys = [k for k in _mill_keys(merged) if k.startswith("alt+shift+") and k != variant]
        assert block_keys == [f"alt+shift+{n}" for n in (1, 2, 3, 5, 6)]


def _test_merge_all_conflicting_removes_block() -> None:
    first, _ = merge_bindings("[]")
    entries = ",\n".join(
        f'  {{ "key": "alt+shift+{n}", "command": "user.{n}" }}' for n in range(1, 7)
    )
    text = first.replace("\n]", ",\n" + entries + "\n]")
    merged, warnings = merge_bindings(text)
    assert len(warnings) == 6
    assert BLOCK_BEGIN not in merged and BLOCK_END not in merged
    assert len(_mill_keys(merged)) == 6


def _test_merge_parse_errors() -> None:
    for bad in ('{ "key": "a" }', "[ not json"):
        try:
            merge_bindings(bad)
        except KeybindingsParseError:
            continue
        raise AssertionError(f"expected KeybindingsParseError for {bad!r}")


def _test_marker_inside_string_ignored() -> None:
    text = '[\n  { "key": "ctrl+k", "command": "a.b", "when": "' + BLOCK_BEGIN + '" }\n]\n'
    merged, _warnings = merge_bindings(text)
    assert merged.count(BLOCK_BEGIN) == 2
    assert merged.startswith('[\n  { "key": "ctrl+k", "command": "a.b", "when": "')
    assert len(_mill_keys(merged)) == 7


def _test_write_bindings() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        user_dir = Path(tmpdir) / "User"
        user_dir.mkdir()
        target = user_dir / "keybindings.json"

        assert write_bindings(target) == ("created", [])
        assert len(_mill_keys(target.read_text(encoding="utf-8"))) == 6

        before_bytes = target.read_bytes()
        before_mtime = target.stat().st_mtime_ns
        assert write_bindings(target) == ("unchanged", [])
        assert target.read_bytes() == before_bytes
        assert target.stat().st_mtime_ns == before_mtime

        target.write_text(before_bytes.decode().replace("alt+shift+3", "alt+shift+8"), encoding="utf-8")
        assert write_bindings(target) == ("updated", [])
        assert target.read_bytes() == before_bytes

        garbage = b"[ definitely not json"
        target.write_bytes(garbage)
        status, warnings = write_bindings(target)
        assert status == "skipped" and len(warnings) == 1 and "all six" in warnings[0]
        assert target.read_bytes() == garbage

        missing = Path(tmpdir) / "nope" / "keybindings.json"
        status, warnings = write_bindings(missing)
        assert status == "skipped" and len(warnings) == 1
        assert not missing.parent.exists()


TESTS = [
    _test_desired_bindings,
    _test_keybindings_path,
    _test_strip_jsonc,
    _test_merge_empty_text,
    _test_merge_into_existing_array,
    _test_merge_trailing_comma_and_empty_array,
    _test_merge_is_idempotent,
    _test_merge_replaces_block_in_place,
    _test_merge_conflicts,
    _test_merge_all_conflicting_removes_block,
    _test_merge_parse_errors,
    _test_marker_inside_string_ignored,
    _test_write_bindings,
]


def main() -> int:
    failures = 0
    for test in TESTS:
        try:
            test()
        except AssertionError as error:
            failures += 1
            print(f"FAIL: {test.__name__}: {error}", file=sys.stderr)
        else:
            print(f"PASS: {test.__name__}")
    if failures:
        print(f"\n{failures} test(s) FAILED", file=sys.stderr)
        return 1
    print("All _vscode_keybindings unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
