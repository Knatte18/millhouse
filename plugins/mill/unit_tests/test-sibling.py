"""Unit tests for plugins/mill/scripts/_sibling.py."""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS_DIR = HUB / "plugins" / "mill" / "scripts"
CODEGUIDE_SCRIPTS_DIR = HUB / "plugins" / "codeguide" / "scripts"
SIBLING_PY = SCRIPTS_DIR / "_sibling.py"
CODEGUIDE_SIBLING_PY = CODEGUIDE_SCRIPTS_DIR / "_sibling.py"
sys.path.insert(0, str(SCRIPTS_DIR))

from _sibling import resolve_path  # noqa: E402


def _check(role: str, repo_root: str, expected: str) -> None:
    got = resolve_path(role, Path(repo_root))
    assert got == Path(expected), f"resolve_path({role!r}, {repo_root!r}) -> {got}, expected {expected}"


def _strip_module_docstring(source: str) -> str:
    """Remove the module-level docstring from Python source text."""
    tree = ast.parse(source)
    if (
        tree.body
        and isinstance(tree.body[0], ast.Expr)
        and isinstance(tree.body[0].value, ast.Constant)
        and isinstance(tree.body[0].value.value, str)
    ):
        node = tree.body[0]
        lines = source.splitlines(keepends=True)
        return "".join(lines[: node.lineno - 1] + lines[node.end_lineno :])
    return source


def main() -> int:
    try:
        # Container-form: parent.name == "wts" -> siblings live next to wts/
        _check("wiki", "/c/Code/wts/millhouse", "/c/Code/wiki")
        _check("codeguide", "/c/Code/wts/millhouse", "/c/Code/codeguide")
        _check("wts", "/c/Code/wts/millhouse", "/c/Code/wts")
        print("PASS: container-form -> bare role next to wts/")

        _check("wiki", "/projects/wts/myrepo", "/projects/wiki")
        _check("codeguide", "/projects/wts/myrepo", "/projects/codeguide")
        print("PASS: container-form works for non-millhouse repo names")

        # Prefix-form: parent.name != "wts" -> <name>.<role>
        _check("worktrees", "/c/projects/foo", "/c/projects/foo.worktrees")
        _check("wiki", "/c/projects/foo", "/c/projects/foo.wiki")
        _check("codeguide", "/c/projects/foo", "/c/projects/foo.codeguide")
        print("PASS: prefix-form -> <name>.<role> next to repo")

        # Old hub-form no longer triggers special-case (intentional regression)
        _check("wiki", "/c/Code/millhouse/hub", "/c/Code/millhouse/hub.wiki")
        _check("worktrees", "/c/Code/millhouse/hub", "/c/Code/millhouse/hub.worktrees")
        _check("codeguide", "/c/Code/millhouse/hub", "/c/Code/millhouse/hub.codeguide")
        print("PASS: old hub-form no longer triggers special-case (intentional regression)")

        # Case sensitivity: parent directory must be exactly "wts"
        _check("worktrees", "/c/x/Wts/millhouse", "/c/x/Wts/millhouse.worktrees")
        _check("worktrees", "/c/x/WTS/millhouse", "/c/x/WTS/millhouse.worktrees")
        _check("worktrees", "/c/x/hub-v2", "/c/x/hub-v2.worktrees")
        _check("worktrees", "/c/x/my-hub", "/c/x/my-hub.worktrees")
        print("PASS: container-form match is case-sensitive and literal")

        # Trailing slash on repo_root does not break detection
        _check("codeguide", "/c/Code/wts/millhouse/", "/c/Code/codeguide")
        _check("codeguide", "/tmp/hub/", "/tmp/hub.codeguide")
        print("PASS: trailing slash on repo_root does not break detection")

        cli_cases = [
            ("wiki", "/c/Code/wts/millhouse", "/c/Code/wiki"),
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

        # Identical-twin invariant: both _sibling.py files are byte-equal outside their module docstrings
        mill_source = SIBLING_PY.read_text(encoding="utf-8")
        codeguide_source = CODEGUIDE_SIBLING_PY.read_text(encoding="utf-8")
        mill_stripped = _strip_module_docstring(mill_source)
        codeguide_stripped = _strip_module_docstring(codeguide_source)
        assert mill_stripped == codeguide_stripped, (
            "mill and codeguide _sibling.py differ outside their module docstrings.\n"
            "If you changed one, apply the same change to the other."
        )
        print("PASS: mill and codeguide _sibling.py are identical-twins (modulo module docstring)")

        print("All _sibling unit tests passed.")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
