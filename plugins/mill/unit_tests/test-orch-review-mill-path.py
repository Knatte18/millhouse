"""Unit tests for the orch-review hand-off path regression lock.

orch-review writes the --orch hand-off file to _mill/orch-review.md
orch-wait reads the --orch hand-off file from _mill/orch-review.md
"""
from __future__ import annotations

import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SKILLS = HUB / "plugins" / "mill" / "skills"


def test_mill_path() -> list[str]:
    """
    Assert orch-review/SKILL.md and orch-wait/SKILL.md both reference the
    _mill/orch-review.md hand-off path and no longer reference the stale
    .scratch/orch-review.md path.

    Returns list of failure messages (empty list = all passed).
    """
    failures: list[str] = []
    paths = [
        SKILLS / "orch-review" / "SKILL.md",
        SKILLS / "orch-wait" / "SKILL.md",
    ]

    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as e:
            failures.append(f"FAIL: could not read {path}: {e}")
            continue

        if text.count("_mill/orch-review.md") < 1:
            failures.append(
                f"FAIL: {path}: expected '_mill/orch-review.md' to appear "
                f"at least once, found 0 occurrences"
            )

        stale_count = text.count(".scratch/orch-review.md")
        if stale_count != 0:
            failures.append(
                f"FAIL: {path}: found {stale_count} occurrence(s) of stale "
                f"'.scratch/orch-review.md', expected 0"
            )

    return failures


def main() -> int:
    """
    Run the hand-off path regression lock.

    Returns 0 on all passes, 1 on any failure.
    """
    try:
        print("--- orch-review _mill/ path regression lock ---")

        print("Testing orch-review/orch-wait _mill/orch-review.md path...")
        failures = test_mill_path()
        if failures:
            for msg in failures:
                print(msg, file=sys.stderr)
            print(
                f"FAIL: {len(failures)} path check(s) failed",
                file=sys.stderr,
            )
            return 1
        print(
            "PASS: orch-review/SKILL.md and orch-wait/SKILL.md reference "
            "_mill/orch-review.md with no stale .scratch/orch-review.md references"
        )

        print("All test-orch-review-mill-path checks passed.")
        return 0

    except Exception as e:
        print(f"FAIL: unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
