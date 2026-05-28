"""
Gate: no direct shutil.rmtree / os.removedirs / rmdir /s callsites in plugins/mill/
outside the explicit whitelist.

Rationale: direct recursive-deletion calls that bypass _safe_rmtree risk following NTFS
directory junctions into shared state (wiki, portals, hub root) -- the wiki-wipe incident
described in GitHub issue #100. Every callsite must go through _safe_rmtree.safe_rmtree,
which strips junctions first. Files that legitimately reference the banned patterns (the
helper itself, its test, docstrings explaining why the helper exists) are listed in
ALLOWED_FILES and skipped.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
MILL_DIR = REPO_ROOT / "plugins" / "mill"

BANNED_PATTERNS: dict[str, str] = {
    "shutil.rmtree": r"shutil\.rmtree",
    "os.removedirs": r"os\.removedirs",
    "rmdir /s": r"rmdir\s+/s",
}

ALLOWED_FILES: set[str] = {
    "plugins/mill/scripts/_junction.py",
    "plugins/mill/scripts/_safe_rmtree.py",
    "plugins/mill/unit_tests/test-no-direct-rmtree.py",
    "plugins/mill/unit_tests/test-safe-rmtree.py",
    "plugins/mill/unit_tests/test-worktree.py",
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


def _repo_relative_posix(p: Path) -> str:
    return p.relative_to(REPO_ROOT).as_posix()


def main() -> int:
    compiled = {name: re.compile(pat) for name, pat in BANNED_PATTERNS.items()}

    findings: list[tuple[str, str, int, str]] = []

    for file in _iter_python_files(MILL_DIR):
        rel = _repo_relative_posix(file)
        if rel in ALLOWED_FILES:
            continue
        text = file.read_text(encoding="utf-8")
        lines = text.split("\n")
        for lineno, line_text in enumerate(lines, start=1):
            for pat_name, rx in compiled.items():
                if rx.search(line_text):
                    findings.append((rel, pat_name, lineno, line_text))

    missing_whitelist: list[str] = []
    for entry in ALLOWED_FILES:
        if not (REPO_ROOT / entry).exists():
            missing_whitelist.append(entry)

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


if __name__ == "__main__":
    sys.exit(main())
