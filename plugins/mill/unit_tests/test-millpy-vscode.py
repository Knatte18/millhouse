"""Unit tests for plugins/mill/scripts/millpy-vscode.py."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

# Load millpy-vscode.py via importlib (hyphenated name).
_SCRIPT = HUB / "plugins" / "mill" / "scripts" / "millpy-vscode.py"
_spec = importlib.util.spec_from_file_location("mill_vscode", _SCRIPT)
mill_vscode = importlib.util.module_from_spec(_spec)
sys.modules["mill_vscode"] = mill_vscode
_spec.loader.exec_module(mill_vscode)

import _active  # noqa: E402


def _make_git_repo(tmp: Path) -> Path:
    """Initialise a minimal git repo under ``tmp`` and return its path."""
    subprocess.run(
        ["git", "init", str(tmp)], check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp), "commit", "--allow-empty", "-m", "init"],
        check=True, capture_output=True,
    )
    return tmp


def _write_active_marker(worktree_path: Path, slug: str, title: str) -> None:
    """Write a valid active.slug.md under ``<worktree_path>/.millhouse/``."""
    mill_dir = worktree_path / ".millhouse"
    _active.write(
        mill_dir,
        slug=slug,
        task_title=title,
        branch=slug,
        spawned_at="2026-04-26T00:00:00Z",
    )


def main() -> int:
    errors = 0

    # ------------------------------------------------------------------
    # Test: two worktrees, user picks first -> subprocess called with
    # first worktree's path as sole positional arg.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _make_git_repo(root)

        worktrees_dir = root / "worktrees"
        wt1 = worktrees_dir / "task-alpha"
        wt2 = worktrees_dir / "task-beta"
        wt1.mkdir(parents=True)
        wt2.mkdir(parents=True)
        _write_active_marker(wt1, "task-alpha", "Alpha Task")
        _write_active_marker(wt2, "task-beta", "Beta Task")

        subprocess_calls: list[dict] = []

        def mock_subprocess_run(argv, **kwargs):
            subprocess_calls.append({"argv": argv})

        with (
            patch("mill_vscode.resolve_git_root", return_value=root),
            patch("mill_vscode.resolve_wiki_path", return_value=root / "wiki"),
            patch("mill_vscode.resolve_worktrees_dir", return_value=worktrees_dir),
            patch("mill_vscode.subprocess.run", side_effect=mock_subprocess_run),
            patch("mill_vscode.input", return_value="1", create=True),
        ):
            rc = mill_vscode.main([])

        if rc != 0:
            print(f"FAIL: two-worktree pick returned {rc}, expected 0", file=sys.stderr)
            errors += 1
        elif not subprocess_calls:
            print("FAIL: subprocess.run not called", file=sys.stderr)
            errors += 1
        else:
            argv = subprocess_calls[0]["argv"]
            # The last positional arg to code must be the worktree path.
            if str(wt1) not in argv:
                print(
                    f"FAIL: expected {wt1} in code argv, got {argv}",
                    file=sys.stderr,
                )
                errors += 1
            else:
                print("PASS: two worktrees -- user picks 1 -> code invoked with first worktree path")

    # ------------------------------------------------------------------
    # Test: --slug selects without prompting.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _make_git_repo(root)

        worktrees_dir = root / "worktrees"
        wt1 = worktrees_dir / "task-alpha"
        wt2 = worktrees_dir / "task-beta"
        wt1.mkdir(parents=True)
        wt2.mkdir(parents=True)
        _write_active_marker(wt1, "task-alpha", "Alpha Task")
        _write_active_marker(wt2, "task-beta", "Beta Task")

        subprocess_calls = []
        input_calls: list = []

        with (
            patch("mill_vscode.resolve_git_root", return_value=root),
            patch("mill_vscode.resolve_wiki_path", return_value=root / "wiki"),
            patch("mill_vscode.resolve_worktrees_dir", return_value=worktrees_dir),
            patch("mill_vscode.subprocess.run", side_effect=lambda a, **kw: subprocess_calls.append(a)),
            patch("mill_vscode.input", side_effect=lambda *a: input_calls.append(a) or "1", create=True),
        ):
            rc = mill_vscode.main(["--slug", "task-beta"])

        if rc != 0:
            print(f"FAIL: --slug path returned {rc}, expected 0", file=sys.stderr)
            errors += 1
        elif input_calls:
            print("FAIL: input() was called despite --slug", file=sys.stderr)
            errors += 1
        elif not subprocess_calls or str(wt2) not in subprocess_calls[0]:
            print(
                f"FAIL: expected {wt2} in code argv, got {subprocess_calls}",
                file=sys.stderr,
            )
            errors += 1
        else:
            print("PASS: --slug skips picker and opens correct worktree")

    # ------------------------------------------------------------------
    # Test: --list prints worktrees, does not launch VS Code.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _make_git_repo(root)

        worktrees_dir = root / "worktrees"
        wt1 = worktrees_dir / "task-alpha"
        wt1.mkdir(parents=True)
        _write_active_marker(wt1, "task-alpha", "Alpha Task")

        subprocess_calls = []
        with (
            patch("mill_vscode.resolve_git_root", return_value=root),
            patch("mill_vscode.resolve_wiki_path", return_value=root / "wiki"),
            patch("mill_vscode.resolve_worktrees_dir", return_value=worktrees_dir),
            patch("mill_vscode.subprocess.run", side_effect=lambda a, **kw: subprocess_calls.append(a)),
        ):
            rc = mill_vscode.main(["--list"])

        if rc != 0:
            print(f"FAIL: --list returned {rc}, expected 0", file=sys.stderr)
            errors += 1
        elif subprocess_calls:
            print("FAIL: subprocess.run called during --list", file=sys.stderr)
            errors += 1
        else:
            print("PASS: --list prints candidates without launching VS Code")

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All mill-vscode unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
