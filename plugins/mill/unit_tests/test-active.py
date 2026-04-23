"""Unit tests for plugins/mill/scripts/_active.py."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _active import ActiveError, read_all, read_slug, write  # noqa: E402


def main() -> int:
    try:
        with tempfile.TemporaryDirectory() as tmp:
            mill = Path(tmp) / ".millhouse"
            write(
                mill,
                slug="demo-task",
                task_title="Demo task",
                branch="hanf/demo-task",
                spawned_at="2026-04-22T14:32:05Z",
            )
            assert read_slug(mill) == "demo-task"
            data = read_all(mill)
            assert data["task_title"] == "Demo task"
            assert data["branch"] == "hanf/demo-task"
            print("PASS: write -> read_all / read_slug roundtrip")

        # Missing file should raise.
        try:
            read_slug(Path(tempfile.gettempdir()) / "does-not-exist")
        except ActiveError:
            print("PASS: read_slug raises ActiveError when file missing")
        else:
            raise AssertionError("expected ActiveError")

        print("All _active unit tests passed.")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
