"""Unit tests for _setup.set_repo_short_name."""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _setup import set_repo_short_name  # noqa: E402
from _test_helpers import safe_temp_dir  # noqa: E402

TEMPLATE = HUB / "plugins" / "mill" / "templates" / "mill-config.yaml"


def _test_template_roundtrip(errors: list[int]) -> None:
    with safe_temp_dir() as tmp:
        path = tmp / "config.yaml"
        original = TEMPLATE.read_bytes().decode("utf-8")
        path.write_bytes(original.encode("utf-8"))
        assert set_repo_short_name(path, "MH") is True
        updated = path.read_bytes().decode("utf-8")
        old_lines, new_lines = original.splitlines(True), updated.splitlines(True)
        assert len(old_lines) == len(new_lines)
        changed = [(o, n) for o, n in zip(old_lines, new_lines) if o != n]
        assert changed == [(
            '  short_name: ""    # e.g. "MH" for millhouse\n',
            '  short_name: MH    # e.g. "MH" for millhouse\n',
        )], changed
        assert yaml.safe_load(updated)["repo"]["short_name"] == "MH"
        before = (path.read_bytes(), path.stat().st_mtime_ns)
        assert set_repo_short_name(path, "MH") is False
        assert (path.read_bytes(), path.stat().st_mtime_ns) == before
        assert set_repo_short_name(path, "LYX") is True
        assert yaml.safe_load(path.read_text(encoding="utf-8"))["repo"]["short_name"] == "LYX"
    print("PASS: template line replaced in place, idempotent, replaceable")


def _test_insertions(errors: list[int]) -> None:
    with safe_temp_dir() as tmp:
        path = tmp / "a.yaml"
        path.write_bytes(b"git:\n  base_branch: main\n")
        assert set_repo_short_name(path, "AB") is True
        assert path.read_bytes() == b"repo:\n  short_name: AB\ngit:\n  base_branch: main\n"

        path.write_bytes(b"repo:\n  other: 1\ngit: {}\n")
        assert set_repo_short_name(path, "AB") is True
        assert path.read_bytes() == b"repo:\n  short_name: AB\n  other: 1\ngit: {}\n"

        path.write_bytes(b"git: {}\r\nx: 1\r\n")
        assert set_repo_short_name(path, "AB") is True
        assert path.read_bytes() == b"repo:\r\n  short_name: AB\r\ngit: {}\r\nx: 1\r\n"

        path.write_bytes(b"repo:\r\n  other: 1\r\n")
        assert set_repo_short_name(path, "AB") is True
        assert path.read_bytes() == b"repo:\r\n  short_name: AB\r\n  other: 1\r\n"

        path.write_bytes(b"repo: {}\n")
        try:
            set_repo_short_name(path, "AB")
        except ValueError:
            assert path.read_bytes() == b"repo: {}\n"
        else:
            raise AssertionError("expected ValueError for flow-style repo")
    print("PASS: missing block/key inserted, CRLF preserved, flow style rejected")


def _test_invalid_values(errors: list[int]) -> None:
    with safe_temp_dir() as tmp:
        path = tmp / "a.yaml"
        content = b'repo:\n  short_name: ""\n'
        path.write_bytes(content)
        for bad in ("A", "ABCDE", "A:B", "a-b"):
            try:
                set_repo_short_name(path, bad)
            except ValueError:
                assert path.read_bytes() == content
                continue
            raise AssertionError(f"expected ValueError for {bad!r}")
    print("PASS: invalid values raise and leave the file untouched")


def main() -> int:
    errors = [0]
    for test in (_test_template_roundtrip, _test_insertions, _test_invalid_values):
        try:
            test(errors)
        except AssertionError as exc:
            errors[0] += 1
            print(f"FAIL: {test.__name__}: {exc}", file=sys.stderr)
    return 1 if errors[0] else 0


if __name__ == "__main__":
    sys.exit(main())
