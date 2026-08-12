"""Regression guard for the agent-only mill-go-base skill.

Batch: regression-guard

Written first, deliberately red, against the post-strip end state that later
batches in this task produce: the `mill-go-base` skill and its three
companion files (`resume.md`, `holistic-review.md`, `handoff.md`) must exist,
must be free of the dead subprocess/psmux dispatch literals, and must
cross-reference each other by repo-relative path with a mandatory Read
directive at each reference site.

This test fails from the moment it is written until batch 4 completes -- see
`_mill/plan/01-regression-guard.md`'s `## Batch Tests` section for why that is
expected and deliberate.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SKILLS = HUB / "plugins" / "mill" / "skills"

BASE_DIR = SKILLS / "mill-go-base"
COMPANIONS = ("resume.md", "holistic-review.md", "handoff.md")
BANNED_LITERALS = ("psmux", "millpy-bg", "dispatch == subprocess")


def _check_no_dead_dispatch_literals() -> list[str]:
    """
    None of the dead subprocess/psmux dispatch literals may survive in `SKILL.md`
    or in any of the three companion files.

    A missing companion file is itself a failure here -- it is reported
    directly rather than silently skipped, so the check still fails loudly
    before the companion files exist.
    """
    failures: list[str] = []
    paths = [BASE_DIR / "SKILL.md"] + [BASE_DIR / name for name in COMPANIONS]

    for path in paths:
        if not path.exists():
            failures.append(f"FAIL: {path}: file does not exist")
            continue
        text = path.read_text(encoding="utf-8")
        for literal in BANNED_LITERALS:
            if literal in text:
                failures.append(f"FAIL: {path}: contains banned literal '{literal}'")

    return failures


def _check_companion_files_exist() -> list[str]:
    """Each of the three companion files must exist under `mill-go-base/`."""
    failures: list[str] = []
    for name in COMPANIONS:
        path = BASE_DIR / name
        if not path.exists():
            failures.append(f"FAIL: {path}: companion file does not exist")
    return failures


def _check_companions_referenced_by_repo_relative_path() -> list[str]:
    """`SKILL.md` must reference each companion file by its repo-relative path."""
    failures: list[str] = []
    skill_path = BASE_DIR / "SKILL.md"
    if not skill_path.exists():
        failures.append(f"FAIL: {skill_path}: file does not exist")
        return failures

    text = skill_path.read_text(encoding="utf-8")
    for name in COMPANIONS:
        reference = f"plugins/mill/skills/mill-go-base/{name}"
        if reference not in text:
            failures.append(f"FAIL: {skill_path}: missing repo-relative reference '{reference}'")

    return failures


def _check_mandatory_read_directive_at_each_reference_site() -> list[str]:
    """
    Each companion reference site in `SKILL.md` must carry a mandatory-read
    directive of the shape `` Read `plugins/mill/skills/mill-go-base/<name>` ``.

    Only the read-instruction shape is asserted on -- not any surrounding
    prose, adjectives, or sentence ordering -- so the wording at the three
    sites can be revised without breaking this guard.
    """
    failures: list[str] = []
    skill_path = BASE_DIR / "SKILL.md"
    if not skill_path.exists():
        failures.append(f"FAIL: {skill_path}: file does not exist")
        return failures

    text = skill_path.read_text(encoding="utf-8")
    for name in COMPANIONS:
        escaped_name = re.escape(name)
        pattern = re.compile(
            r"Read\s+`plugins/mill/skills/mill-go-base/" + escaped_name + r"`",
            re.IGNORECASE,
        )
        if not pattern.search(text):
            failures.append(
                f"FAIL: {skill_path}: missing mandatory Read directive for '{name}'"
            )

    return failures


def main() -> int:
    """Run all four agent-only regression-guard checks and print a PASS/FAIL summary line."""
    checks = (
        _check_no_dead_dispatch_literals,
        _check_companion_files_exist,
        _check_companions_referenced_by_repo_relative_path,
        _check_mandatory_read_directive_at_each_reference_site,
    )

    all_failures: list[str] = []
    for check in checks:
        all_failures.extend(check())

    if all_failures:
        for msg in all_failures:
            print(msg, file=sys.stderr)
        print(f"FAIL: {len(all_failures)} agent-only regression-guard check(s) failed", file=sys.stderr)
        return 1

    print("PASS: mill-go-base agent-only regression guard holds")
    return 0


if __name__ == "__main__":
    sys.exit(main())
