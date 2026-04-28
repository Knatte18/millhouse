"""Unit tests for plugins/mill/scripts/mill-terminal.py."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, call, patch

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

# Load mill-terminal.py via importlib (hyphenated name).
_SCRIPT = HUB / "plugins" / "mill" / "scripts" / "mill-terminal.py"
_spec = importlib.util.spec_from_file_location("mill_terminal", _SCRIPT)
mill_terminal = importlib.util.module_from_spec(_spec)
sys.modules["mill_terminal"] = mill_terminal
_spec.loader.exec_module(mill_terminal)

import _active  # noqa: E402


def _make_git_repo(tmp: Path) -> Path:
    """Initialise a minimal bare-enough git repo and return its path."""
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
    # Test: two worktrees present, user picks first → subprocess called
    # with first worktree's path.
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

        subprocess_calls: list = []

        def mock_subprocess_run(argv, *, cwd=None, **kwargs):
            subprocess_calls.append({"argv": argv, "cwd": cwd})

        with (
            patch("mill_terminal.resolve_git_root", return_value=root),
            patch("mill_terminal.resolve_wiki_path", return_value=root / "wiki"),
            patch("mill_terminal.resolve_worktrees_dir", return_value=worktrees_dir),
            patch("mill_terminal.subprocess.run", side_effect=mock_subprocess_run),
            patch("mill_terminal.input", return_value="1", create=True),
        ):
            rc = mill_terminal.main([])

        if rc != 0:
            print(f"FAIL: two-worktree pick returned {rc}, expected 0", file=sys.stderr)
            errors += 1
        elif not subprocess_calls:
            print("FAIL: subprocess.run not called", file=sys.stderr)
            errors += 1
        else:
            called_cwd = subprocess_calls[0]["cwd"]
            if called_cwd != wt1:
                print(
                    f"FAIL: expected cwd={wt1}, got {called_cwd}",
                    file=sys.stderr,
                )
                errors += 1
            else:
                print("PASS: two worktrees -- user picks 1 -> subprocess called with first path")

    # ------------------------------------------------------------------
    # Test: single worktree → auto-selected, subprocess called without prompt.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _make_git_repo(root)

        worktrees_dir = root / "worktrees"
        wt1 = worktrees_dir / "solo-task"
        wt1.mkdir(parents=True)
        _write_active_marker(wt1, "solo-task", "Solo Task")

        subprocess_calls = []
        input_calls: list = []

        def mock_input(prompt=""):
            input_calls.append(prompt)
            return "1"

        with (
            patch("mill_terminal.resolve_git_root", return_value=root),
            patch("mill_terminal.resolve_wiki_path", return_value=root / "wiki"),
            patch("mill_terminal.resolve_worktrees_dir", return_value=worktrees_dir),
            patch("mill_terminal.subprocess.run", side_effect=lambda *a, **kw: subprocess_calls.append(kw.get("cwd"))),
            patch("mill_terminal.input", side_effect=mock_input, create=True),
        ):
            rc = mill_terminal.main([])

        if rc != 0:
            print(f"FAIL: single-worktree auto-select returned {rc}", file=sys.stderr)
            errors += 1
        elif input_calls:
            print("FAIL: input() was called for single worktree (should auto-select)", file=sys.stderr)
            errors += 1
        elif not subprocess_calls or subprocess_calls[0] != wt1:
            print(
                f"FAIL: expected subprocess cwd={wt1}, got {subprocess_calls}",
                file=sys.stderr,
            )
            errors += 1
        else:
            print("PASS: single worktree auto-selected, no prompt, subprocess called")

    # ------------------------------------------------------------------
    # Test: no active worktrees → exits 0, no subprocess call.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _make_git_repo(root)
        empty_dir = root / "worktrees"
        empty_dir.mkdir()

        subprocess_calls = []
        with (
            patch("mill_terminal.resolve_git_root", return_value=root),
            patch("mill_terminal.resolve_wiki_path", return_value=root / "wiki"),
            patch("mill_terminal.resolve_worktrees_dir", return_value=empty_dir),
            patch("mill_terminal.subprocess.run", side_effect=lambda *a, **kw: subprocess_calls.append(kw)),
        ):
            rc = mill_terminal.main([])

        if rc != 0:
            print(f"FAIL: no worktrees returned {rc}, expected 0", file=sys.stderr)
            errors += 1
        elif subprocess_calls:
            print("FAIL: subprocess.run called when no worktrees found", file=sys.stderr)
            errors += 1
        else:
            print("PASS: no active worktrees -> exits 0, no subprocess call")

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All mill-terminal unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
