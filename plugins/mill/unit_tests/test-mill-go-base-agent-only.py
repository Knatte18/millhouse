"""Regression guard for mill-go-base's agent-only dispatch surface.

Batch: regression-guard

Written first, deliberately red, against the post-strip end state that later
batches in this task produce: the subprocess/psmux dispatch branches removed
from mill-go-base/SKILL.md (banned literals), and the three cold-path
sections extracted into their own companion files (resume.md,
holistic-review.md, handoff.md), each referenced from SKILL.md by a
repo-relative path and a mandatory `Read` directive at its reference site.
This test fails until batch 4 completes, per the batch's own `verify: null`
Batch-local decision.
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


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _check_no_dead_dispatch_literals() -> list[str]:
    """
    Neither SKILL.md nor any companion file may contain a banned literal.

    A missing companion file is itself a failure here, reported as such
    rather than silently skipped -- this check does not depend on
    `_check_companion_files_exist` having run first.
    """
    failures: list[str] = []

    paths = [BASE_DIR / "SKILL.md"] + [BASE_DIR / name for name in COMPANIONS]
    for path in paths:
        if not path.exists():
            failures.append(f"FAIL: {path}: file does not exist, cannot check for banned literals")
            continue
        text = _read(path)
        for literal in BANNED_LITERALS:
            if literal in text:
                failures.append(f"FAIL: {path}: contains banned literal '{literal}'")

    return failures


def _check_companion_files_exist() -> list[str]:
    """Each of the three companion files must exist under mill-go-base/."""
    failures: list[str] = []

    for name in COMPANIONS:
        path = BASE_DIR / name
        if not path.exists():
            failures.append(f"FAIL: {path}: companion file does not exist")

    return failures


def _check_companions_referenced_by_repo_relative_path() -> list[str]:
    """SKILL.md must reference each companion file by its repo-relative path."""
    failures: list[str] = []
    path = BASE_DIR / "SKILL.md"
    text = _read(path)

    for name in COMPANIONS:
        expected = f"plugins/mill/skills/mill-go-base/{name}"
        if expected not in text:
            failures.append(f"FAIL: {path}: missing repo-relative reference '{expected}'")

    return failures


def _check_mandatory_read_directive_at_each_reference_site() -> list[str]:
    """
    Each companion reference site in SKILL.md must carry a mandatory-read directive.

    Asserts only on the `` Read `plugins/mill/skills/mill-go-base/<name>` ``
    shape, case-insensitively -- not on any surrounding prose, adjectives, or
    sentence ordering, so the wording at the three sites can be revised
    without breaking this guard.
    """
    failures: list[str] = []
    path = BASE_DIR / "SKILL.md"
    text = _read(path)

    for name in COMPANIONS:
        escaped_name = re.escape(name)
        pattern = re.compile(
            r"Read\s+`plugins/mill/skills/mill-go-base/" + escaped_name + r"`",
            re.IGNORECASE,
        )
        if not pattern.search(text):
            failures.append(
                f"FAIL: {path}: no mandatory-read directive found for companion '{name}' "
                f"(expected pattern: Read `plugins/mill/skills/mill-go-base/{name}`)"
            )

    return failures


def main() -> int:
    """Run all four agent-only dispatch checks and print a PASS/FAIL summary line."""
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
        print(f"FAIL: {len(all_failures)} agent-only dispatch check(s) failed", file=sys.stderr)
        return 1

    print("PASS: mill-go-base agent-only dispatch guard holds")
    return 0


if __name__ == "__main__":
    sys.exit(main())
