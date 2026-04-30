"""Unit tests for plugins/mill/scripts/_gitignore.py."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _gitignore import (  # noqa: E402
    ANCHORED_ENTRIES,
    END,
    GLOB_ENTRIES,
    START,
    upsert_split,
)

def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    errors = 0

    # --- upsert_split: same path → single combined block ---
    with tempfile.TemporaryDirectory() as tmpdir:
        gi = Path(tmpdir) / ".gitignore"
        gi.write_text("", encoding="utf-8")
        repo_changed, hub_changed = upsert_split(gi, gi, GLOB_ENTRIES, ANCHORED_ENTRIES)
        content = _read(gi)
        if not repo_changed:
            print("FAIL: upsert_split same-path first run should return (True, False)", file=sys.stderr)
            errors += 1
        if hub_changed:
            print("FAIL: upsert_split same-path hub_changed should be False", file=sys.stderr)
            errors += 1
        for entry in GLOB_ENTRIES + ANCHORED_ENTRIES:
            if entry not in content:
                print(f"FAIL: upsert_split same-path missing entry: {entry}", file=sys.stderr)
                errors += 1
        if errors == 0:
            print("PASS: upsert_split same-path writes single combined block, returns (True, False)")

    # --- upsert_split: same path → idempotent re-run ---
    with tempfile.TemporaryDirectory() as tmpdir:
        gi = Path(tmpdir) / ".gitignore"
        gi.write_text("", encoding="utf-8")
        upsert_split(gi, gi, GLOB_ENTRIES, ANCHORED_ENTRIES)
        repo_changed, hub_changed = upsert_split(gi, gi, GLOB_ENTRIES, ANCHORED_ENTRIES)
        if repo_changed or hub_changed:
            print("FAIL: upsert_split same-path re-run should return (False, False)", file=sys.stderr)
            errors += 1
        else:
            print("PASS: upsert_split same-path re-run -> (False, False)")

    # --- upsert_split: different paths → two separate blocks ---
    with tempfile.TemporaryDirectory() as tmpdir:
        root_gi = Path(tmpdir) / ".gitignore"
        hub_dir = Path(tmpdir) / "src" / "hub"
        hub_dir.mkdir(parents=True)
        hub_gi = hub_dir / ".gitignore"
        root_gi.write_text("", encoding="utf-8")
        hub_gi.write_text("", encoding="utf-8")
        repo_changed, hub_changed = upsert_split(root_gi, hub_gi, GLOB_ENTRIES, ANCHORED_ENTRIES)
        root_content = _read(root_gi)
        hub_content = _read(hub_gi)
        if not repo_changed:
            print("FAIL: upsert_split diff-path repo_changed should be True", file=sys.stderr)
            errors += 1
        if not hub_changed:
            print("FAIL: upsert_split diff-path hub_changed should be True", file=sys.stderr)
            errors += 1
        # Root gets only glob entries
        for entry in GLOB_ENTRIES:
            if entry not in root_content:
                print(f"FAIL: root .gitignore missing glob entry: {entry}", file=sys.stderr)
                errors += 1
        for entry in ANCHORED_ENTRIES:
            if entry in root_content:
                print(f"FAIL: root .gitignore should not contain anchored entry: {entry}", file=sys.stderr)
                errors += 1
        # Hub gets only anchored entries
        for entry in ANCHORED_ENTRIES:
            if entry not in hub_content:
                print(f"FAIL: hub .gitignore missing anchored entry: {entry}", file=sys.stderr)
                errors += 1
        for entry in GLOB_ENTRIES:
            if entry in hub_content:
                print(f"FAIL: hub .gitignore should not contain glob entry: {entry}", file=sys.stderr)
                errors += 1
        if errors == 0:
            print("PASS: upsert_split diff-path writes glob-only to root and anchored-only to hub")

    # --- upsert_split: different paths → idempotent re-run on each path ---
    with tempfile.TemporaryDirectory() as tmpdir:
        root_gi = Path(tmpdir) / ".gitignore"
        hub_dir = Path(tmpdir) / "src" / "hub"
        hub_dir.mkdir(parents=True)
        hub_gi = hub_dir / ".gitignore"
        root_gi.write_text("", encoding="utf-8")
        hub_gi.write_text("", encoding="utf-8")
        upsert_split(root_gi, hub_gi, GLOB_ENTRIES, ANCHORED_ENTRIES)
        repo_changed, hub_changed = upsert_split(root_gi, hub_gi, GLOB_ENTRIES, ANCHORED_ENTRIES)
        if repo_changed or hub_changed:
            print("FAIL: upsert_split diff-path re-run should return (False, False)", file=sys.stderr)
            errors += 1
        else:
            print("PASS: upsert_split diff-path re-run -> (False, False)")

    # --- upsert_split: anchored entries get / prepended if missing ---
    with tempfile.TemporaryDirectory() as tmpdir:
        root_gi = Path(tmpdir) / ".gitignore"
        hub_dir = Path(tmpdir) / "hub"
        hub_dir.mkdir()
        hub_gi = hub_dir / ".gitignore"
        root_gi.write_text("", encoding="utf-8")
        hub_gi.write_text("", encoding="utf-8")
        upsert_split(root_gi, hub_gi, [], ["tasks.md", "/.others"])
        hub_content = _read(hub_gi)
        if "/tasks.md" not in hub_content:
            print("FAIL: bare anchored entry 'tasks.md' not normalised to '/tasks.md'", file=sys.stderr)
            errors += 1
        if "//tasks.md" in hub_content:
            print("FAIL: double-slash in hub .gitignore for bare entry", file=sys.stderr)
            errors += 1
        if "/.others" not in hub_content:
            print("FAIL: already-prefixed entry '/.others' missing from hub .gitignore", file=sys.stderr)
            errors += 1
        if "//.others" in hub_content:
            print("FAIL: double-slash introduced for already-prefixed '/.others'", file=sys.stderr)
            errors += 1
        if errors == 0:
            print("PASS: upsert_split anchored entries get / prepended; already-prefixed kept as-is")

    # --- upsert_split: corrupt-marker ValueError preserved ---
    with tempfile.TemporaryDirectory() as tmpdir:
        gi = Path(tmpdir) / ".gitignore"
        gi.write_text(f"{START}\n**/.millhouse/\n", encoding="utf-8")
        try:
            upsert_split(gi, gi, GLOB_ENTRIES, ANCHORED_ENTRIES)
            print("FAIL: expected ValueError for corrupt marker in upsert_split", file=sys.stderr)
            errors += 1
        except ValueError:
            print("PASS: upsert_split preserves corrupt-marker ValueError")

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All _gitignore unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
