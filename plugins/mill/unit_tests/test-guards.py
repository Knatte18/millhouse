"""Source-tree guards: regressions against documented anti-patterns.

Four checks bundled into one test file so we pay Python startup + import
overhead once instead of four times. Each check scans `plugins/mill/` (and
`plugins/codeguide/` for the wiki-cwd check) for forbidden patterns and
returns FAIL with line numbers on hit.

Checks:
  - no_direct_rmtree   -- no `shutil.rmtree` / `os.removedirs` / `rmdir /s`
                          outside the explicit ALLOWED_FILES whitelist.
                          Direct recursive-deletion that bypasses _safe_rmtree
                          can follow NTFS junctions into wiki/portals state
                          (the 2026-03 wiki-wipe incident, GitHub #100).
  - no_unicode_arrow   -- no U+2192 `->` in any test-*.py. Windows cp1252
                          consoles crash on non-ASCII stdout; use `->` in ASCII.
  - no_wiki_cwd        -- no `cd .wiki`, `os.chdir(wiki)`, `cwd=wiki` in
                          scripts/ or skills/. Wiki access goes through
                          `_wiki` helpers, never via cwd change (2026-05-11
                          incident). See CLAUDE.md `## Wiki access`.
  - anti_weakening_guardrail -- assert the anti-weakening guardrail is present
                          in both implementer-brief.md and mill-implementer.md
                          (#492).

Each previously lived in its own test-no-*.py file. Consolidated 2026-05-28
to reduce suite startup overhead (#388).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Iterable

HUB = Path(__file__).resolve().parent.parent.parent.parent
MILL_DIR = HUB / "plugins" / "mill"


# --------------------------------------------------------------------------- #
# Check 1: no_direct_rmtree                                                   #
# --------------------------------------------------------------------------- #

_RMTREE_PATTERNS: dict[str, str] = {
    "shutil.rmtree": r"shutil\.rmtree",
    "os.removedirs": r"os\.removedirs",
    "rmdir /s": r"rmdir\s+/s",
}

_RMTREE_ALLOWED_FILES: set[str] = {
    "plugins/mill/scripts/_junction.py",
    "plugins/mill/scripts/_safe_rmtree.py",
    "plugins/mill/unit_tests/test-guards.py",
    "plugins/mill/unit_tests/test-safe-rmtree.py",
    "plugins/mill/unit_tests/test-worktree.py",
    "plugins/mill/unit_tests/test-wiki-daemon.py",
    "plugins/mill/unit_tests/test-wiki-store.py",
    "plugins/mill/unit_tests/test-wiki-sync.py",
    "plugins/mill/integration_tests/test-wiki-daemon-tinydb.py",
}


def _iter_python_files(root: Path) -> Iterable[Path]:
    """Yield every .py file under root, sorted, skipping hidden dirs and __pycache__."""
    for p in sorted(root.rglob("*.py")):
        if p.is_symlink():
            continue
        if any(part.startswith(".") or part == "__pycache__" for part in p.parts):
            continue
        yield p


def _check_no_direct_rmtree() -> int:
    """Return 0 on PASS, 1 on FAIL."""
    compiled = {name: re.compile(pat) for name, pat in _RMTREE_PATTERNS.items()}
    findings: list[tuple[str, str, int, str]] = []

    for file in _iter_python_files(MILL_DIR):
        rel = file.relative_to(HUB).as_posix()
        if rel in _RMTREE_ALLOWED_FILES:
            continue
        text = file.read_text(encoding="utf-8")
        for lineno, line_text in enumerate(text.split("\n"), start=1):
            for pat_name, rx in compiled.items():
                if rx.search(line_text):
                    findings.append((rel, pat_name, lineno, line_text))

    missing_whitelist = [e for e in _RMTREE_ALLOWED_FILES if not (HUB / e).exists()]
    if missing_whitelist:
        for m in missing_whitelist:
            print(f"FAIL: whitelist entry not found on disk: {m}")
        return 1

    if findings:
        for rel, pat_name, lineno, line_text in findings:
            print(f"FAIL: {rel}:{lineno}: {pat_name}: {line_text.strip()}")
        print(f"FAIL: {len(findings)} direct rmtree callsite(s) outside ALLOWED_FILES")
        return 1

    print("PASS: no direct rmtree callsites in plugins/mill/ outside ALLOWED_FILES")
    return 0


# --------------------------------------------------------------------------- #
# Check 2: no_unicode_arrow                                                   #
# --------------------------------------------------------------------------- #

def _check_no_unicode_arrow() -> int:
    """Return 0 on PASS, 1 on FAIL."""
    here = Path(__file__).resolve().parent
    self_name = Path(__file__).name
    hits: list[str] = []
    for path in sorted(here.glob("test-*.py")):
        if path.name == self_name:
            continue
        text = path.read_text(encoding="utf-8")
        if "→" in text:
            hits.append(path.name)
    if hits:
        for name in hits:
            print(f"FAIL: U+2192 arrow found in {name}", file=sys.stderr)
        return 1
    print("PASS: no U+2192 arrow in any test-*.py")
    return 0


# --------------------------------------------------------------------------- #
# Check 3: no_wiki_cwd                                                        #
# --------------------------------------------------------------------------- #

_WALK_ROOTS = [
    HUB / "plugins" / "mill" / "scripts",
    HUB / "plugins" / "mill" / "skills",
    HUB / "plugins" / "codeguide" / "scripts",
    HUB / "plugins" / "codeguide" / "skills",
]

_WIKI_CWD_ALLOWLIST = {
    "plugins/mill/skills/mill-start/SKILL.md",
    "plugins/mill/skills/mill-plan/SKILL.md",
    "plugins/mill/skills/mill-go/SKILL.md",
    "plugins/mill/skills/mill-merge/SKILL.md",
    "plugins/mill/skills/mill-wiki-push/SKILL.md",
    "plugins/mill/skills/mill-setup/SKILL.md",
    "plugins/mill/skills/mill-claim/SKILL.md",
    "plugins/mill/skills/mill-spawn/SKILL.md",
    "plugins/mill/skills/mill-finalize/SKILL.md",
}

_WIKI_CWD_PATTERNS = [
    ("cd-wiki-junction",    re.compile(r"cd \.wiki\b")),
    ("cd-wiki-token",       re.compile(r"cd <wiki[^>]*>")),
    ("os-chdir-wiki",       re.compile(r"os\.chdir\([^)]*wiki")),
    ("subprocess-cwd-wiki", re.compile(r"cwd=[^,)]*wiki")),
    ("cd-wiki-relative",    re.compile(r"cd \.\./[^\s]*wiki/")),
]


def _check_no_wiki_cwd() -> int:
    """Return 0 on PASS, 1 on FAIL."""
    self_path = Path(__file__).resolve()
    findings: list[tuple[str, int, str, str]] = []

    for root in _WALK_ROOTS:
        if not root.exists():
            continue
        for ext in ("*.py", "*.md", "*.sh"):
            for candidate in root.rglob(ext):
                if candidate.resolve() == self_path:
                    continue
                try:
                    rel = candidate.resolve().relative_to(HUB).as_posix()
                except ValueError:
                    rel = candidate.as_posix()
                if rel in _WIKI_CWD_ALLOWLIST:
                    continue
                text = candidate.read_text(encoding="utf-8", errors="replace")
                for lineno, line in enumerate(text.splitlines(), 1):
                    for name, pattern in _WIKI_CWD_PATTERNS:
                        if pattern.search(line):
                            findings.append((rel, lineno, name, line.rstrip()))

    if not findings:
        print("PASS: no wiki-cwd anti-patterns in scripts/ or skills/ across mill + codeguide")
        return 0

    for rel_path, lineno, regex_name, line in findings:
        print(f"FAIL: {rel_path}:{lineno}: {regex_name}: {line}")
    return 1


# --------------------------------------------------------------------------- #
# Check 4: anti_weakening_guardrail                                           #
# --------------------------------------------------------------------------- #

_ANTI_WEAKENING_MARKER = "Never weaken, relax, exclude, downgrade, or delete test assertions, conformance checks, or allowlist entries to make verify pass."

_GUARDRAIL_FILES = [
    "plugins/mill/templates/implementer-brief.md",
    "plugins/mill/agents/mill-implementer.md",
]


def _check_anti_weakening_guardrail() -> int:
    """
    Return 0 on PASS, 1 on FAIL.

    Assert that the anti-weakening guardrail marker sentence is present in both
    implementer-brief.md and mill-implementer.md (#492).
    """
    findings: list[str] = []

    for rel_path in _GUARDRAIL_FILES:
        file_path = HUB / rel_path
        if not file_path.exists():
            findings.append(f"FAIL: file not found: {rel_path}")
            continue
        text = file_path.read_text(encoding="utf-8")
        if _ANTI_WEAKENING_MARKER not in text:
            findings.append(f"FAIL: {rel_path}: anti-weakening guardrail marker not found")

    if findings:
        for msg in findings:
            print(msg)
        return 1

    print("PASS: anti-weakening guardrail present in both implementer-brief.md and mill-implementer.md")
    return 0


# --------------------------------------------------------------------------- #
# Entry                                                                       #
# --------------------------------------------------------------------------- #

def main() -> int:
    rc = 0
    rc |= _check_no_direct_rmtree()
    rc |= _check_no_unicode_arrow()
    rc |= _check_no_wiki_cwd()
    rc |= _check_anti_weakening_guardrail()
    return rc


if __name__ == "__main__":
    sys.exit(main())
