"""Prevent cd .wiki / os.chdir(wiki) / cwd=wiki regressions (2026-05-11 incident).

Any match in scripts/ or skills/ across mill + codeguide is a regression.
See '## Wiki access' in CLAUDE.md for the invariant this test enforces.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent

_WALK_ROOTS = [
    HUB / "plugins" / "mill" / "scripts",
    HUB / "plugins" / "mill" / "skills",
    HUB / "plugins" / "codeguide" / "scripts",
    HUB / "plugins" / "codeguide" / "skills",
]

_ALLOWLIST = {
    "plugins/mill/skills/mill-start/SKILL.md",
    "plugins/mill/skills/mill-plan/SKILL.md",
    "plugins/mill/skills/mill-go/SKILL.md",
    "plugins/mill/skills/mill-merge/SKILL.md",
    "plugins/mill/skills/mill-wiki-push/SKILL.md",
    "plugins/mill/skills/mill-setup/SKILL.md",
    "plugins/mill/skills/mill-claim/SKILL.md",
    "plugins/mill/skills/mill-spawn/SKILL.md",
}

_PATTERNS = [
    ("cd-wiki-junction",   re.compile(r"cd \.wiki\b")),
    ("cd-wiki-token",      re.compile(r"cd <wiki[^>]*>")),
    ("os-chdir-wiki",      re.compile(r"os\.chdir\([^)]*wiki")),
    ("subprocess-cwd-wiki",re.compile(r"cwd=[^,)]*wiki")),
    ("cd-wiki-relative",   re.compile(r"cd \.\./[^\s]*wiki/")),
]

_SELF = Path(__file__).resolve()


def main() -> int:
    findings: list[tuple[str, int, str, str]] = []

    for root in _WALK_ROOTS:
        if not root.exists():
            continue
        for ext in ("*.py", "*.md", "*.sh"):
            for candidate in root.rglob(ext):
                if candidate.resolve() == _SELF:
                    continue
                try:
                    rel = candidate.resolve().relative_to(HUB).as_posix()
                except ValueError:
                    rel = candidate.as_posix()
                if rel in _ALLOWLIST:
                    continue
                text = candidate.read_text(encoding="utf-8", errors="replace")
                for lineno, line in enumerate(text.splitlines(), 1):
                    for name, pattern in _PATTERNS:
                        if pattern.search(line):
                            findings.append((rel, lineno, name, line.rstrip()))

    if not findings:
        print("PASS: no wiki-cwd anti-patterns in scripts/ or skills/ across mill + codeguide")
        return 0

    for rel_path, lineno, regex_name, line in findings:
        print(f"FAIL: {rel_path}:{lineno}: {regex_name}: {line}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
