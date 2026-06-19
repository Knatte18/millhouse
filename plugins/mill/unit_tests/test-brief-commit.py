"""Unit tests for brief-commit content regression lock.

Batch: brief-commit-uniformity

Card 5: Regression-lock the brief-commit steps
  Lock _mill/briefs/ commit steps in orchestrator SKILLs:
  - mill-start: Handoff, discussion-gap-fix, and discussion-fix commits include _mill/briefs/
  - mill-merge-in: New step 5.5 commit stages and commits _mill/briefs/ files
"""
from __future__ import annotations

import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SKILLS = HUB / "plugins" / "mill" / "skills"


def test_mill_start_brief_commits() -> list[str]:
    """
    Assert mill-start/SKILL.md references _mill/briefs/ in commit steps.

    Primary form: assert the substrings related to commit messages contain
    _mill/briefs/ within a reasonable window. Fallback: count total occurrences
    to catch dropped sites.

    Returns list of failure messages (empty list = all passed).
    """
    failures: list[str] = []
    mill_start_path = SKILLS / "mill-start" / "SKILL.md"

    try:
        text = mill_start_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as e:
        failures.append(f"FAIL: could not read {mill_start_path}: {e}")
        return failures

    # Check for three commit message contexts
    # Primary checks: look for the commit message markers with _mill/briefs/ nearby
    checks = [
        ("mill-start: handoff", "Handoff commit must include _mill/briefs/"),
        ("mill-start: discussion-gap-fix", "discussion-gap-fix commit must include _mill/briefs/"),
        ("mill-start: discussion-fix", "discussion-fix commit must include _mill/briefs/"),
    ]

    for commit_msg, description in checks:
        # Find all occurrences of the commit message
        found = False
        window_size = 300  # characters before/after to search for _mill/briefs/

        idx = 0
        while idx >= 0:
            idx = text.find(commit_msg, idx)
            if idx < 0:
                break

            # Extract window around this occurrence
            start = max(0, idx - window_size)
            end = min(len(text), idx + len(commit_msg) + window_size)
            window = text[start:end]

            if "_mill/briefs/" in window:
                found = True
                break

            idx += 1

        if not found:
            failures.append(
                f"FAIL: mill-start/SKILL.md: {description} "
                f"(commit message '{commit_msg}' found but no _mill/briefs/ nearby)"
            )

    # Fallback check: total occurrence count must be >= 4
    # This tolerates wording drift while catching a dropped site:
    # 4b interactive, 4b --auto, step 5 gap-fix, Handoff guard, plus --auto halt guards
    briefs_count = text.count("_mill/briefs/")
    if briefs_count < 4:
        failures.append(
            f"FAIL: mill-start/SKILL.md: _mill/briefs/ occurs {briefs_count} times, "
            f"expected >= 4 (4b interactive, 4b auto, gap-fix, Handoff, auto halt guards)"
        )

    return failures


def test_mill_merge_in_brief_commits() -> list[str]:
    """
    Assert mill-merge-in/SKILL.md includes a git add _mill/briefs/ step.

    Checks for the presence of _mill/briefs/ in an add context.

    Returns list of failure messages (empty list = all passed).
    """
    failures: list[str] = []
    mill_merge_in_path = SKILLS / "mill-merge-in" / "SKILL.md"

    try:
        text = mill_merge_in_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as e:
        failures.append(f"FAIL: could not read {mill_merge_in_path}: {e}")
        return failures

    # Check for _mill/briefs/ in git add context
    # Look for "git" followed by "add" followed by "_mill/briefs/" within a reasonable distance
    if "git" not in text or "add" not in text or "_mill/briefs/" not in text:
        failures.append(
            f"FAIL: mill-merge-in/SKILL.md: missing expected git add _mill/briefs/ pattern"
        )
        return failures

    # More specific check: ensure they appear in the same command or nearby
    # Look for patterns like "git -C ... add _mill/briefs/" or similar
    if "add _mill/briefs/" not in text and "add _mill/briefs" not in text:
        failures.append(
            f"FAIL: mill-merge-in/SKILL.md: _mill/briefs/ is present but not in an add command context"
        )

    return failures


def main() -> int:
    """
    Run both test groups.

    Returns 0 on all passes, 1 on any failure.
    """
    try:
        print("--- Card 5: Brief-commit regression lock ---")

        print("Testing mill-start brief commits...")
        mill_start_failures = test_mill_start_brief_commits()
        if mill_start_failures:
            for msg in mill_start_failures:
                print(msg, file=sys.stderr)
            print(
                f"FAIL: {len(mill_start_failures)} mill-start brief-commit check(s) failed",
                file=sys.stderr,
            )
            return 1
        print("PASS: mill-start SKILL.md references _mill/briefs/ in all required commit steps")

        print("Testing mill-merge-in brief commits...")
        mill_merge_in_failures = test_mill_merge_in_brief_commits()
        if mill_merge_in_failures:
            for msg in mill_merge_in_failures:
                print(msg, file=sys.stderr)
            print(
                f"FAIL: {len(mill_merge_in_failures)} mill-merge-in brief-commit check(s) failed",
                file=sys.stderr,
            )
            return 1
        print("PASS: mill-merge-in SKILL.md contains git add _mill/briefs/ step")

        print("All test-brief-commit checks passed.")
        return 0

    except Exception as e:
        print(f"FAIL: unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
