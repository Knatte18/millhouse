"""Unit tests for plugins/mill/scripts/_sibling.py."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS_DIR = HUB / "plugins" / "mill" / "scripts"
SIBLING_PY = SCRIPTS_DIR / "_sibling.py"
sys.path.insert(0, str(SCRIPTS_DIR))

from _sibling import resolve_path  # noqa: E402


def _check(role: str, repo_root: str, expected: str) -> None:
    got = resolve_path(role, Path(repo_root))
    assert got == Path(expected), f"resolve_path({role!r}, {repo_root!r}) -> {got}, expected {expected}"


def main() -> int:
    try:
        _check("worktrees", "/c/Code/millhouse/hub", "/c/Code/millhouse/worktrees")
        _check("wiki", "/c/Code/millhouse/hub", "/c/Code/millhouse/wiki")
        _check("codeguide", "/c/Code/millhouse/hub", "/c/Code/millhouse/codeguide")
        print("PASS: hub-form -> bare role next to hub/")

        _check("worktrees", "/c/projects/foo", "/c/projects/foo.worktrees")
        _check("wiki", "/c/projects/foo", "/c/projects/foo.wiki")
        _check("codeguide", "/c/projects/foo", "/c/projects/foo.codeguide")
        print("PASS: prefix-form -> <name>.<role> next to repo")

        _check("worktrees", "/c/x/Hub", "/c/x/Hub.worktrees")
        _check("worktrees", "/c/x/HUB", "/c/x/HUB.worktrees")
        _check("worktrees", "/c/x/hub-v2", "/c/x/hub-v2.worktrees")
        _check("worktrees", "/c/x/my-hub", "/c/x/my-hub.worktrees")
        print("PASS: hub-form match is case-sensitive and literal")

        _check("codeguide", "/tmp/hub", "/tmp/codeguide")
        _check("codeguide", "/tmp/hub/", "/tmp/codeguide")
        print("PASS: trailing slash on repo_root does not break detection")

        cli_cases = [
            ("worktrees", "/c/Code/millhouse/hub", "/c/Code/millhouse/worktrees"),
            ("wiki", "/c/projects/foo", "/c/projects/foo.wiki"),
            ("codeguide", "/c/x/Hub", "/c/x/Hub.codeguide"),
        ]
        for role, repo_root, expected in cli_cases:
            result = subprocess.run(
                [sys.executable, str(SIBLING_PY), role, repo_root],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, f"CLI exit={result.returncode} stderr={result.stderr}"
            out = result.stdout.strip()
            assert Path(out) == Path(expected), f"CLI({role}, {repo_root}) -> {out!r}, expected {expected!r}"
        print("PASS: CLI entry point prints resolved path, exit 0")

        bad = subprocess.run(
            [sys.executable, str(SIBLING_PY), "only-one-arg"],
            capture_output=True,
            text=True,
        )
        assert bad.returncode == 2, f"expected exit 2 for bad args, got {bad.returncode}"
        assert "usage" in bad.stderr.lower()
        print("PASS: CLI exits 2 with usage message on bad args")

        print("All _sibling unit tests passed.")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
