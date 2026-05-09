"""Unit tests for plugins/mill/scripts/millpy-vscode.py.

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

# Load millpy-vscode.py via importlib (hyphenated name).
_SCRIPT = HUB / "plugins" / "mill" / "scripts" / "millpy-vscode.py"
_spec = importlib.util.spec_from_file_location("mill_vscode", _SCRIPT)
mill_vscode = importlib.util.module_from_spec(_spec)
sys.modules["mill_vscode"] = mill_vscode
_spec.loader.exec_module(mill_vscode)

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

        subprocess_calls: list[dict] = []

        def mock_subprocess_run(argv, **kwargs):
            subprocess_calls.append({"argv": argv})

        with (
            patch("mill_vscode.resolve_git_root", return_value=root),
            patch("mill_vscode.resolve_wiki_path", return_value=root / "wiki"),
            patch("mill_vscode.resolve_worktrees_dir", return_value=worktrees_dir),
            patch("mill_vscode._spawn_core.discover_active_worktrees",
                  return_value=[(wt1, "task-alpha", "Alpha Task"), (wt2, "task-beta", "Beta Task")]),
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

        subprocess_calls = []
        input_calls: list = []

        with (
            patch("mill_vscode.resolve_git_root", return_value=root),
            patch("mill_vscode.resolve_wiki_path", return_value=root / "wiki"),
            patch("mill_vscode.resolve_worktrees_dir", return_value=worktrees_dir),
            patch("mill_vscode._spawn_core.discover_active_worktrees",
                  return_value=[(wt1, "task-alpha", "Alpha Task"), (wt2, "task-beta", "Beta Task")]),
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

        subprocess_calls = []
        with (
            patch("mill_vscode.resolve_git_root", return_value=root),
            patch("mill_vscode.resolve_wiki_path", return_value=root / "wiki"),
            patch("mill_vscode.resolve_worktrees_dir", return_value=worktrees_dir),
            patch("mill_vscode._spawn_core.discover_active_worktrees",
                  return_value=[(wt1, "task-alpha", "Alpha Task")]),
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

    # ------------------------------------------------------------------
    # Test: hub_relative_path set in per-worktree config → VS Code
    # launched with <worktree>/src/csharp/X as workspace folder.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _make_git_repo(root)

        worktrees_dir = root / "worktrees"
        wt1 = worktrees_dir / "task-alpha"
        wt1.mkdir(parents=True)

        # Stub at worktree root pointing at sub-path.
        mill_dir = wt1 / ".millhouse"
        mill_dir.mkdir(exist_ok=True)
        (mill_dir / "config.local.yaml").write_text(
            "hub_relative_path: src/csharp/X\n", encoding="utf-8"
        )

        subprocess_calls: list[dict] = []
        wiki_path = root / "wiki"
        wiki_path.mkdir()

        with (
            patch("mill_vscode.resolve_git_root", return_value=root),
            patch("mill_vscode.resolve_wiki_path", return_value=wiki_path),
            patch("mill_vscode.resolve_worktrees_dir", return_value=worktrees_dir),
            patch("mill_vscode._spawn_core.discover_active_worktrees",
                  return_value=[(wt1, "task-alpha", "Alpha Task")]),
            patch("mill_vscode.subprocess.run", side_effect=lambda a, **kw: subprocess_calls.append({"argv": a})),
        ):
            rc = mill_vscode.main([])

        expected_workspace = str(wt1 / "src" / "csharp" / "X")
        if rc != 0:
            print(f"FAIL: hub_relative_path test returned {rc}", file=sys.stderr)
            errors += 1
        elif not subprocess_calls or expected_workspace not in subprocess_calls[0]["argv"]:
            print(
                f"FAIL: expected {expected_workspace} in code argv, got {subprocess_calls}",
                file=sys.stderr,
            )
            errors += 1
        else:
            print("PASS: hub_relative_path (sub-dir) → VS Code launched in sub-dir")

    # ------------------------------------------------------------------
    # Test: hub_relative_path = "." → VS Code launched at worktree root.
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
            patch("mill_vscode.resolve_git_root", return_value=root),
            patch("mill_vscode.resolve_wiki_path", return_value=wiki_path),
            patch("mill_vscode.resolve_worktrees_dir", return_value=worktrees_dir),
            patch("mill_vscode._spawn_core.discover_active_worktrees",
                  return_value=[(wt1, "task-dot", "Dot Task")]),
            patch("mill_vscode.subprocess.run", side_effect=lambda a, **kw: subprocess_calls.append({"argv": a})),
        ):
            rc = mill_vscode.main([])

        if rc != 0:
            print(f"FAIL: hub_relative_path=. test returned {rc}", file=sys.stderr)
            errors += 1
        elif not subprocess_calls or str(wt1) not in subprocess_calls[0]["argv"]:
            print(
                f"FAIL: expected {wt1} in code argv, got {subprocess_calls}",
                file=sys.stderr,
            )
            errors += 1
        else:
            print("PASS: hub_relative_path=. → VS Code launched at worktree root")

    # ------------------------------------------------------------------
    # Regression: hub config has hub_relative_path: "hub-sub", selected
    # worktree's config has hub_relative_path: "wt-sub" → wt-sub wins.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _make_git_repo(root)

        worktrees_dir = root / "worktrees"
        wt1 = worktrees_dir / "task-reg"
        wt1.mkdir(parents=True)

        hub_mill_dir = root / ".millhouse"
        hub_mill_dir.mkdir(exist_ok=True)
        (hub_mill_dir / "config.local.yaml").write_text(
            "hub_relative_path: hub-sub\n", encoding="utf-8"
        )

        wt_mill_dir = wt1 / ".millhouse"
        wt_mill_dir.mkdir(exist_ok=True)
        (wt_mill_dir / "config.local.yaml").write_text(
            "hub_relative_path: wt-sub\n", encoding="utf-8"
        )

        subprocess_calls = []
        wiki_path = root / "wiki"
        wiki_path.mkdir()

        with (
            patch("mill_vscode.resolve_git_root", return_value=root),
            patch("mill_vscode.resolve_wiki_path", return_value=wiki_path),
            patch("mill_vscode.resolve_worktrees_dir", return_value=worktrees_dir),
            patch("mill_vscode._spawn_core.discover_active_worktrees",
                  return_value=[(wt1, "task-reg", "Regression Task")]),
            patch("mill_vscode.subprocess.run", side_effect=lambda a, **kw: subprocess_calls.append({"argv": a})),
        ):
            rc = mill_vscode.main([])

        expected_workspace = str(wt1 / "wt-sub")
        if rc != 0:
            print(f"FAIL: hub_relative_path regression test returned {rc}", file=sys.stderr)
            errors += 1
        elif not subprocess_calls or expected_workspace not in subprocess_calls[0]["argv"]:
            print(
                f"FAIL: expected {expected_workspace} (wt-sub wins), got {subprocess_calls}",
                file=sys.stderr,
            )
            errors += 1
        else:
            print("PASS: per-worktree hub_relative_path wins over hub config value")

    # ------------------------------------------------------------------
    # Test: no active worktrees, no flags → spawn called, new worktree opened.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _make_git_repo(root)

        worktrees_dir = root / "worktrees"
        wt_new = worktrees_dir / "task-new"
        wt_new.mkdir(parents=True)

        spawn_callable = MagicMock(return_value=0)
        subprocess_calls: list[dict] = []

        with (
            patch("mill_vscode.resolve_git_root", return_value=root),
            patch("mill_vscode.resolve_wiki_path", return_value=root / "wiki"),
            patch("mill_vscode.resolve_worktrees_dir", return_value=worktrees_dir),
            patch(
                "mill_vscode._spawn_core.discover_active_worktrees",
                side_effect=[[], [(wt_new, "task-new", "New Task")]],
            ),
            patch("mill_vscode._load_spawn_main", return_value=spawn_callable),
            patch(
                "mill_vscode.subprocess.run",
                side_effect=lambda a, **kw: subprocess_calls.append({"argv": a}),
            ),
        ):
            rc = mill_vscode.main([])

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
        elif str(wt_new) not in subprocess_calls[0]["argv"]:
            print(
                f"FAIL: expected {wt_new} in code argv, got {subprocess_calls}",
                file=sys.stderr,
            )
            errors += 1
        else:
            print("PASS: no active worktrees + no flags → spawn called, new worktree opened")

    # ------------------------------------------------------------------
    # Test: no active worktrees, spawn returns non-zero → exit 1, no VS Code.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _make_git_repo(root)

        worktrees_dir = root / "worktrees"
        worktrees_dir.mkdir()

        spawn_callable = MagicMock(return_value=1)
        subprocess_calls = []

        with (
            patch("mill_vscode.resolve_git_root", return_value=root),
            patch("mill_vscode.resolve_wiki_path", return_value=root / "wiki"),
            patch("mill_vscode.resolve_worktrees_dir", return_value=worktrees_dir),
            patch("mill_vscode._spawn_core.discover_active_worktrees", return_value=[]),
            patch("mill_vscode._load_spawn_main", return_value=spawn_callable),
            patch(
                "mill_vscode.subprocess.run",
                side_effect=lambda a, **kw: subprocess_calls.append(a),
            ),
        ):
            rc = mill_vscode.main([])

        if rc != 1:
            print(f"FAIL: spawn non-zero rc → expected exit 1, got {rc}", file=sys.stderr)
            errors += 1
        elif subprocess_calls:
            print("FAIL: subprocess.run called despite spawn failure", file=sys.stderr)
            errors += 1
        else:
            print("PASS: spawn non-zero rc → exit 1, no VS Code")

    # ------------------------------------------------------------------
    # Test: no active worktrees, spawn returns 0 but backlog empty → exit 0, no VS Code.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _make_git_repo(root)

        worktrees_dir = root / "worktrees"
        worktrees_dir.mkdir()

        spawn_callable = MagicMock(return_value=0)
        subprocess_calls = []

        with (
            patch("mill_vscode.resolve_git_root", return_value=root),
            patch("mill_vscode.resolve_wiki_path", return_value=root / "wiki"),
            patch("mill_vscode.resolve_worktrees_dir", return_value=worktrees_dir),
            patch("mill_vscode._spawn_core.discover_active_worktrees", return_value=[]),
            patch("mill_vscode._load_spawn_main", return_value=spawn_callable),
            patch(
                "mill_vscode.subprocess.run",
                side_effect=lambda a, **kw: subprocess_calls.append(a),
            ),
        ):
            rc = mill_vscode.main([])

        if rc != 0:
            print(f"FAIL: empty backlog → expected exit 0, got {rc}", file=sys.stderr)
            errors += 1
        elif subprocess_calls:
            print("FAIL: subprocess.run called despite empty backlog", file=sys.stderr)
            errors += 1
        else:
            print("PASS: spawn empty backlog → exit 0, no VS Code")

    # ------------------------------------------------------------------
    # Test: --list with no active worktrees → spawn NOT called, exit 0.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _make_git_repo(root)

        worktrees_dir = root / "worktrees"
        worktrees_dir.mkdir()

        load_spawn_mock = MagicMock()

        with (
            patch("mill_vscode.resolve_git_root", return_value=root),
            patch("mill_vscode.resolve_wiki_path", return_value=root / "wiki"),
            patch("mill_vscode.resolve_worktrees_dir", return_value=worktrees_dir),
            patch("mill_vscode._spawn_core.discover_active_worktrees", return_value=[]),
            patch("mill_vscode._load_spawn_main", load_spawn_mock),
        ):
            rc = mill_vscode.main(["--list"])

        if load_spawn_mock.called:
            print("FAIL: _load_spawn_main called despite --list flag", file=sys.stderr)
            errors += 1
        elif rc != 0:
            print(f"FAIL: --list empty → expected exit 0, got {rc}", file=sys.stderr)
            errors += 1
        else:
            print("PASS: --list with empty active list → spawn not called")

    # ------------------------------------------------------------------
    # Test: --slug with no active worktrees → spawn NOT called, exit 0.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _make_git_repo(root)

        worktrees_dir = root / "worktrees"
        worktrees_dir.mkdir()

        load_spawn_mock = MagicMock()

        with (
            patch("mill_vscode.resolve_git_root", return_value=root),
            patch("mill_vscode.resolve_wiki_path", return_value=root / "wiki"),
            patch("mill_vscode.resolve_worktrees_dir", return_value=worktrees_dir),
            patch("mill_vscode._spawn_core.discover_active_worktrees", return_value=[]),
            patch("mill_vscode._load_spawn_main", load_spawn_mock),
        ):
            rc = mill_vscode.main(["--slug", "nonexistent"])

        if load_spawn_mock.called:
            print("FAIL: _load_spawn_main called despite --slug flag", file=sys.stderr)
            errors += 1
        elif rc != 0:
            print(f"FAIL: --slug empty → expected exit 0, got {rc}", file=sys.stderr)
            errors += 1
        else:
            print("PASS: --slug with empty active list → spawn not called")

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All mill-vscode unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
