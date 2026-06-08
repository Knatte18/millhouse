"""Unit tests for plugins/mill/scripts/_gitignore.py."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _gitignore import (  # noqa: E402
    END,
    GLOB_ENTRIES,
    START,
    render_block,
    upsert,
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_anchored_entries_not_exported() -> int:
    errors = 0
    try:
        from _gitignore import ANCHORED_ENTRIES  # noqa: F401
        print("FAIL: ANCHORED_ENTRIES import should have raised ImportError", file=sys.stderr)
        errors += 1
    except ImportError:
        print("PASS: ANCHORED_ENTRIES no longer exported")
    return errors


def test_upsert_first_call_returns_true() -> int:
    errors = 0
    with tempfile.TemporaryDirectory() as tmpdir:
        gi = Path(tmpdir) / ".gitignore"
        gi.write_text("", encoding="utf-8")
        changed = upsert(gi, GLOB_ENTRIES)
        if not changed:
            print("FAIL: upsert first call on empty .gitignore should return True", file=sys.stderr)
            errors += 1
        else:
            print("PASS: upsert first call returns True (wrote new block)")
    return errors


def test_upsert_idempotent() -> int:
    errors = 0
    with tempfile.TemporaryDirectory() as tmpdir:
        gi = Path(tmpdir) / ".gitignore"
        gi.write_text("", encoding="utf-8")
        upsert(gi, GLOB_ENTRIES)
        changed = upsert(gi, GLOB_ENTRIES)
        if changed:
            print("FAIL: upsert second call should return False (already up to date)", file=sys.stderr)
            errors += 1
        else:
            print("PASS: upsert second call returns False (idempotent)")
    return errors


def test_upsert_preserves_existing_content() -> int:
    errors = 0
    with tempfile.TemporaryDirectory() as tmpdir:
        gi = Path(tmpdir) / ".gitignore"
        gi.write_text("*.pyc\n__pycache__/\n", encoding="utf-8")
        upsert(gi, GLOB_ENTRIES)
        content = _read(gi)
        if "*.pyc" not in content:
            print("FAIL: upsert did not preserve existing content above the block", file=sys.stderr)
            errors += 1
        if START not in content:
            print("FAIL: upsert did not append block to non-empty .gitignore", file=sys.stderr)
            errors += 1
        if content.index("*.pyc") > content.index(START):
            print("FAIL: existing content should appear before the mill block", file=sys.stderr)
            errors += 1
        if errors == 0:
            print("PASS: upsert appends block below existing content, preserving existing lines")
    return errors


def test_upsert_corrupt_marker_raises() -> int:
    errors = 0
    with tempfile.TemporaryDirectory() as tmpdir:
        gi = Path(tmpdir) / ".gitignore"
        gi.write_text(f"{START}\n**/.millhouse/\n", encoding="utf-8")
        try:
            upsert(gi, GLOB_ENTRIES)
            print("FAIL: expected ValueError for corrupt marker (START without END)", file=sys.stderr)
            errors += 1
        except ValueError:
            print("PASS: upsert raises ValueError for corrupt marker (START without END)")
    return errors


def test_render_block_contains_glob_entries() -> int:
    errors = 0
    block = render_block(GLOB_ENTRIES)
    for entry in GLOB_ENTRIES:
        if entry not in block:
            print(f"FAIL: render_block output missing entry: {entry}", file=sys.stderr)
            errors += 1
        elif not (block.index(START) < block.index(entry) < block.index(END)):
            print(f"FAIL: '{entry}' not between START and END markers", file=sys.stderr)
            errors += 1
    for removed in ("**/wts/", "**/portals/", "**/plugins/*/uv.lock"):
        if removed in GLOB_ENTRIES:
            print(f"FAIL: '{removed}' should not be in GLOB_ENTRIES", file=sys.stderr)
            errors += 1
    if errors == 0:
        print("PASS: render_block includes all five GLOB_ENTRIES between START and END; removed entries absent")
    return errors


def test_glob_entries_contains_new_junction_names() -> int:
    errors = 0
    for expected in ("**/.portals/", "**/.wiki/", "**/.active/"):
        if expected not in GLOB_ENTRIES:
            print(f"FAIL: GLOB_ENTRIES missing '{expected}'", file=sys.stderr)
            errors += 1
    if errors == 0:
        print("PASS: GLOB_ENTRIES contains **/.portals/, **/.wiki/, **/.active/")
    return errors


def test_glob_entries_excludes_briefs() -> int:
    errors = 0
    for entry in GLOB_ENTRIES:
        if "_mill/briefs" in entry:
            print(f"FAIL: GLOB_ENTRIES contains _mill/briefs in entry '{entry}' — briefs must remain tracked", file=sys.stderr)
            errors += 1
    if errors == 0:
        print("PASS: GLOB_ENTRIES contains no _mill/briefs entry — briefs are tracked, not ignored")
    return errors


def main() -> int:
    tests = [
        test_anchored_entries_not_exported,
        test_upsert_first_call_returns_true,
        test_upsert_idempotent,
        test_upsert_preserves_existing_content,
        test_upsert_corrupt_marker_raises,
        test_render_block_contains_glob_entries,
        test_glob_entries_contains_new_junction_names,
        test_glob_entries_excludes_briefs,
    ]
    errors = 0
    for test in tests:
        errors += test()

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All _gitignore unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
