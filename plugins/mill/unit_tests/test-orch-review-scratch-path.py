"""Unit tests for the orch-review .scratch/ path migration regression lock.

Batch: review-hygiene-fixes

Card 3: Regression-lock the .scratch/ hand-off path
SKILLs: - orch-review: writes the --orch hand-off file to .scratch/orch-review.md
- orch-wait: reads the --orch hand-off file from .scratch/orch-review.md
"""
from __future__ import annotations

import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SKILLS = HUB / "plugins" / "mill" / "skills"


def test_scratch_path_migration() -> list[str]:
    """
    Assert orch-review/SKILL.md and orch-wait/SKILL.md both reference the
    .scratch/orch-review.md hand-off path and no longer reference the
    stale _mill/orch-review.md path.

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

        if text.count(".scratch/orch-review.md") < 1:
            failures.append(
                f"FAIL: {path}: expected '.scratch/orch-review.md' to appear "
                f"at least once, found 0 occurrences"
            )

        stale_count = text.count("_mill/orch-review.md")
        if stale_count != 0:
            failures.append(
                f"FAIL: {path}: found {stale_count} occurrence(s) of stale "
                f"'_mill/orch-review.md', expected 0"
            )

    return failures


def main() -> int:
    """
    Run the scratch-path migration regression lock.

    Returns 0 on all passes, 1 on any failure.
    """
    try:
        print("--- Card 3: orch-review .scratch/ path regression lock ---")

        print("Testing orch-review/orch-wait .scratch/orch-review.md path...")
        failures = test_scratch_path_migration()
        if failures:
            for msg in failures:
                print(msg, file=sys.stderr)
            print(
                f"FAIL: {len(failures)} scratch-path migration check(s) failed",
                file=sys.stderr,
            )
            return 1
        print(
            "PASS: orch-review/SKILL.md and orch-wait/SKILL.md reference "
            ".scratch/orch-review.md with no stale _mill/orch-review.md references"
        )

        print("All test-orch-review-scratch-path checks passed.")
        return 0

    except Exception as e:
        print(f"FAIL: unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
