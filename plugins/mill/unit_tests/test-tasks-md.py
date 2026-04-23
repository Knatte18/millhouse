"""Unit tests for plugins/mill/scripts/_tasks_md.py."""
from __future__ import annotations

import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _tasks_md import claim, parse, set_phase  # noqa: E402


def main() -> int:
    try:
        sample = (
            "# Tasks\n\n"
            "<!-- comment -->\n\n"
            "## First task [task-one]\n\n"
            "Summary for task-one.\n\n"
            "## Second task [[task-two]](proposal-task-two)\n\n"
            "Summary for task-two (with proposal).\n\n"
            "## Third task [task-three] [s]\n\n"
            "Summary for task-three, already spawn-ready.\n"
        )
        parsed = parse(sample)
        assert len(parsed) == 3, f"Expected 3 tasks, got {len(parsed)}"
        assert parsed[0].slug == "task-one" and parsed[0].phase is None
        assert parsed[1].slug == "task-two" and parsed[1].has_proposal
        assert parsed[2].phase == "s"
        print("PASS: parse() returns 3 tasks with correct slugs/phases/proposals")

        claimed = claim(sample, "task-one")
        reparsed = parse(claimed)
        assert reparsed[0].phase == "active", f"Expected active, got {reparsed[0].phase!r}"
        print("PASS: claim() sets [active] on the target heading")

        cleared = set_phase(claimed, "task-one", None)
        assert parse(cleared)[0].phase is None
        print("PASS: set_phase(..., None) strips the marker")

        try:
            claim(sample, "does-not-exist")
        except ValueError as exc:
            print(f"PASS: claim() raises on unknown slug ({exc})")
        else:
            raise AssertionError("Expected ValueError for unknown slug")

        print("All _tasks_md unit tests passed.")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
