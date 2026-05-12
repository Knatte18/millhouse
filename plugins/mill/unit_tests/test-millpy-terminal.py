"""Unit tests for plugins/mill/scripts/millpy-terminal.py.

All discover_active_worktrees calls are mocked with return_value which accepts
the new (worktrees_dir, home_tasks, branch_prefix) signature unchanged.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, call, patch

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

# Load millpy-terminal.py via importlib (hyphenated name).
_SCRIPT = HUB / "plugins" / "mill" / "scripts" / "millpy-terminal.py"
_spec = importlib.util.spec_from_file_location("mill_terminal", _SCRIPT)
mill_terminal = importlib.util.module_from_spec(_spec)
sys.modules["mill_terminal"] = mill_terminal
_spec.loader.exec_module(mill_terminal)

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


def main() -> int:
    errors = 0

    # ------------------------------------------------------------------
    # Test: two worktrees present, user picks first -> subprocess called
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

        subprocess_calls: list = []

        def mock_subprocess_run(argv, *, cwd=None, **kwargs):
            subprocess_calls.append({"argv": argv, "cwd": cwd})

        with (
            patch("mill_terminal.resolve_git_root", return_value=root),
            patch("mill_terminal.resolve_wiki_path", return_value=root / "wiki"),
            patch("mill_terminal.resolve_worktrees_dir", return_value=worktrees_dir),
            patch("mill_terminal._spawn_core.discover_active_worktrees",
                  return_value=[(wt1, "task-alpha", "Alpha Task"), (wt2, "task-beta", "Beta Task")]),
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
    # Test: single worktree -> auto-selected, subprocess called without prompt.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _make_git_repo(root)

        worktrees_dir = root / "worktrees"
        wt1 = worktrees_dir / "solo-task"
        wt1.mkdir(parents=True)

        subprocess_calls = []
        input_calls: list = []

        def mock_input(prompt=""):
            input_calls.append(prompt)
            return "1"

        with (
            patch("mill_terminal.resolve_git_root", return_value=root),
            patch("mill_terminal.resolve_wiki_path", return_value=root / "wiki"),
            patch("mill_terminal.resolve_worktrees_dir", return_value=worktrees_dir),
            patch("mill_terminal._spawn_core.discover_active_worktrees",
                  return_value=[(wt1, "solo-task", "Solo Task")]),
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
    # Test: no active worktrees, spawn returns 0, backlog empty -> exit 0.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _make_git_repo(root)
        empty_dir = root / "worktrees"
        empty_dir.mkdir()

        spawn_callable = MagicMock(return_value=0)
        subprocess_calls = []
        with (
            patch("mill_terminal.resolve_git_root", return_value=root),
            patch("mill_terminal.resolve_wiki_path", return_value=root / "wiki"),
            patch("mill_terminal.resolve_worktrees_dir", return_value=empty_dir),
            patch("mill_terminal._spawn_core.discover_active_worktrees", return_value=[]),
            patch("mill_terminal._load_spawn_main", return_value=spawn_callable),
            patch("mill_terminal.subprocess.run", side_effect=lambda *a, **kw: subprocess_calls.append(kw)),
        ):
            rc = mill_terminal.main([])

        if rc != 0:
            print(f"FAIL: empty backlog -> expected exit 0, got {rc}", file=sys.stderr)
            errors += 1
        elif subprocess_calls:
            print("FAIL: subprocess.run called despite empty backlog", file=sys.stderr)
            errors += 1
        else:
            print("PASS: spawn empty backlog -> exit 0, no claude")

    # ------------------------------------------------------------------
    # Test: hub_relative_path set in per-worktree config -> subprocess
    # launched with <worktree>/src/csharp/X as cwd.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _make_git_repo(root)

        worktrees_dir = root / "worktrees"
        wt1 = worktrees_dir / "task-alpha"
        wt1.mkdir(parents=True)

        # Stub at worktree root pointing at sub-path.
        stub_dir = wt1 / ".millhouse"
        stub_dir.mkdir(exist_ok=True)
        (stub_dir / "config.local.yaml").write_text(
            "hub_relative_path: src/csharp/X\n", encoding="utf-8"
        )

        subprocess_calls: list = []
        wiki_path = root / "wiki"
        wiki_path.mkdir()

        with (
            patch("mill_terminal.resolve_git_root", return_value=root),
            patch("mill_terminal.resolve_wiki_path", return_value=wiki_path),
            patch("mill_terminal.resolve_worktrees_dir", return_value=worktrees_dir),
            patch("mill_terminal._spawn_core.discover_active_worktrees",
                  return_value=[(wt1, "task-alpha", "Alpha Task")]),
            patch("mill_terminal.subprocess.run", side_effect=lambda *a, **kw: subprocess_calls.append(kw.get("cwd"))),
        ):
            rc = mill_terminal.main([])

        expected_cwd = wt1 / "src" / "csharp" / "X"
        if rc != 0:
            print(f"FAIL: hub_relative_path test returned {rc}", file=sys.stderr)
            errors += 1
        elif not subprocess_calls or subprocess_calls[0] != expected_cwd:
            print(
                f"FAIL: expected cwd={expected_cwd}, got {subprocess_calls}",
                file=sys.stderr,
            )
            errors += 1
        else:
            print("PASS: hub_relative_path (sub-dir) -> subprocess launched in sub-dir")

    # ------------------------------------------------------------------
    # Test: hub_relative_path = "." -> subprocess launched at worktree root.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _make_git_repo(root)

        worktrees_dir = root / "worktrees"
        wt1 = worktrees_dir / "task-dot"
        wt1.mkdir(parents=True)

        mill_dir = wt1 / ".millhouse"
        mill_dir.mkdir(exist_ok=True)
        (mill_dir / "config.local.yaml").write_text(
            "hub_relative_path: .\n", encoding="utf-8"
        )

        subprocess_calls = []
        wiki_path = root / "wiki"
        wiki_path.mkdir()

        with (
            patch("mill_terminal.resolve_git_root", return_value=root),
            patch("mill_terminal.resolve_wiki_path", return_value=wiki_path),
            patch("mill_terminal.resolve_worktrees_dir", return_value=worktrees_dir),
            patch("mill_terminal._spawn_core.discover_active_worktrees",
                  return_value=[(wt1, "task-dot", "Dot Task")]),
            patch("mill_terminal.subprocess.run", side_effect=lambda *a, **kw: subprocess_calls.append(kw.get("cwd"))),
        ):
            rc = mill_terminal.main([])

        if rc != 0:
            print(f"FAIL: hub_relative_path=. test returned {rc}", file=sys.stderr)
            errors += 1
        elif not subprocess_calls or subprocess_calls[0] != wt1:
            print(
                f"FAIL: expected cwd={wt1}, got {subprocess_calls}",
                file=sys.stderr,
            )
            errors += 1
        else:
            print("PASS: hub_relative_path=. -> subprocess launched at worktree root")

    # ------------------------------------------------------------------
    # Regression: hub config has hub_relative_path: "hub-sub", selected
    # worktree's config has hub_relative_path: "wt-sub" -> wt-sub wins.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _make_git_repo(root)

        worktrees_dir = root / "worktrees"
        wt1 = worktrees_dir / "task-reg"
        wt1.mkdir(parents=True)

        # Hub config (at git_root)
        hub_mill_dir = root / ".millhouse"
        hub_mill_dir.mkdir(exist_ok=True)
        (hub_mill_dir / "config.local.yaml").write_text(
            "hub_relative_path: hub-sub\n", encoding="utf-8"
        )

        # Per-worktree config (at selected_path)
        wt_mill_dir = wt1 / ".millhouse"
        wt_mill_dir.mkdir(exist_ok=True)
        (wt_mill_dir / "config.local.yaml").write_text(
            "hub_relative_path: wt-sub\n", encoding="utf-8"
        )

        subprocess_calls = []
        wiki_path = root / "wiki"
        wiki_path.mkdir()

        with (
            patch("mill_terminal.resolve_git_root", return_value=root),
            patch("mill_terminal.resolve_wiki_path", return_value=wiki_path),
            patch("mill_terminal.resolve_worktrees_dir", return_value=worktrees_dir),
            patch("mill_terminal._spawn_core.discover_active_worktrees",
                  return_value=[(wt1, "task-reg", "Regression Task")]),
            patch("mill_terminal.subprocess.run", side_effect=lambda *a, **kw: subprocess_calls.append(kw.get("cwd"))),
        ):
            rc = mill_terminal.main([])

        expected_cwd = wt1 / "wt-sub"
        if rc != 0:
            print(f"FAIL: hub_relative_path regression test returned {rc}", file=sys.stderr)
            errors += 1
        elif not subprocess_calls or subprocess_calls[0] != expected_cwd:
            print(
                f"FAIL: expected cwd={expected_cwd} (wt-sub wins), got {subprocess_calls}",
                file=sys.stderr,
            )
            errors += 1
        else:
            print("PASS: per-worktree hub_relative_path wins over hub config value")

    # ------------------------------------------------------------------
    # Test: no active worktrees -> spawn called, new worktree, claude launched.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _make_git_repo(root)

        worktrees_dir = root / "worktrees"
        wt_new = worktrees_dir / "task-new"
        wt_new.mkdir(parents=True)

        spawn_callable = MagicMock(return_value=0)
        subprocess_calls: list = []

        with (
            patch("mill_terminal.resolve_git_root", return_value=root),
            patch("mill_terminal.resolve_wiki_path", return_value=root / "wiki"),
            patch("mill_terminal.resolve_worktrees_dir", return_value=worktrees_dir),
            patch(
                "mill_terminal._spawn_core.discover_active_worktrees",
                side_effect=[[], [(wt_new, "task-new", "New Task")]],
            ),
            patch("mill_terminal._load_spawn_main", return_value=spawn_callable),
            patch(
                "mill_terminal.subprocess.run",
                side_effect=lambda *a, **kw: subprocess_calls.append(kw),
            ),
        ):
            rc = mill_terminal.main([])

        if not spawn_callable.called:
            print("FAIL: spawn callable not called", file=sys.stderr)
            errors += 1
        elif spawn_callable.call_args_list[0] != call([]):
            print(
                f"FAIL: spawn callable called with wrong args: {spawn_callable.call_args_list}",
                file=sys.stderr,
            )
            errors += 1
        elif not subprocess_calls:
            print("FAIL: subprocess.run not called after spawn", file=sys.stderr)
            errors += 1
        elif subprocess_calls[0].get("cwd") != wt_new:
            print(
                f"FAIL: expected cwd={wt_new}, got {subprocess_calls}",
                file=sys.stderr,
            )
            errors += 1
        else:
            print("PASS: no active worktrees -> spawn called, claude launched in new worktree")

    # ------------------------------------------------------------------
    # Test: no active worktrees, spawn returns non-zero -> exit 1, no claude.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _make_git_repo(root)

        worktrees_dir = root / "worktrees"
        worktrees_dir.mkdir()

        spawn_callable = MagicMock(return_value=1)
        subprocess_calls = []

        with (
            patch("mill_terminal.resolve_git_root", return_value=root),
            patch("mill_terminal.resolve_wiki_path", return_value=root / "wiki"),
            patch("mill_terminal.resolve_worktrees_dir", return_value=worktrees_dir),
            patch("mill_terminal._spawn_core.discover_active_worktrees", return_value=[]),
            patch("mill_terminal._load_spawn_main", return_value=spawn_callable),
            patch(
                "mill_terminal.subprocess.run",
                side_effect=lambda *a, **kw: subprocess_calls.append(kw),
            ),
        ):
            rc = mill_terminal.main([])

        if rc != 1:
            print(f"FAIL: spawn non-zero rc -> expected exit 1, got {rc}", file=sys.stderr)
            errors += 1
        elif subprocess_calls:
            print("FAIL: subprocess.run called despite spawn failure", file=sys.stderr)
            errors += 1
        else:
            print("PASS: spawn non-zero rc -> exit 1, no claude")

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All mill-terminal unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
