"""Unit tests for plugins/mill/scripts/millpy-vscode.py."""
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
            patch("mill_vscode._vscode_processes.find_open_vscode_paths", return_value=set()),
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

        # Stub at worktree root pointing at sub-path; active marker lives
        # under the sub-path (mirrors the real hub-relative-path layout).
        mill_dir = wt1 / ".millhouse"
        mill_dir.mkdir(exist_ok=True)
        (mill_dir / "config.local.yaml").write_text(
            "hub_relative_path: src/csharp/X\n", encoding="utf-8"
        )
        _write_active_marker(wt1 / "src" / "csharp" / "X", "task-alpha", "Alpha Task")

        subprocess_calls: list[dict] = []
        wiki_path = root / "wiki"
        wiki_path.mkdir()

        with (
            patch("mill_vscode.resolve_git_root", return_value=root),
            patch("mill_vscode.resolve_wiki_path", return_value=wiki_path),
            patch("mill_vscode.resolve_worktrees_dir", return_value=worktrees_dir),
            patch("mill_vscode.subprocess.run", side_effect=lambda a, **kw: subprocess_calls.append({"argv": a})),
            patch("mill_vscode._vscode_processes.find_open_vscode_paths", return_value=set()),
            patch("mill_vscode.input", return_value="1", create=True),
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
        _write_active_marker(wt1, "task-dot", "Dot Task")

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
            patch("mill_vscode.subprocess.run", side_effect=lambda a, **kw: subprocess_calls.append({"argv": a})),
            patch("mill_vscode._vscode_processes.find_open_vscode_paths", return_value=set()),
            patch("mill_vscode.input", return_value="1", create=True),
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
        # Active marker lives under the sub-path per the stub.
        _write_active_marker(wt1 / "wt-sub", "task-reg", "Regression Task")

        subprocess_calls = []
        wiki_path = root / "wiki"
        wiki_path.mkdir()

        with (
            patch("mill_vscode.resolve_git_root", return_value=root),
            patch("mill_vscode.resolve_wiki_path", return_value=wiki_path),
            patch("mill_vscode.resolve_worktrees_dir", return_value=worktrees_dir),
            patch("mill_vscode.subprocess.run", side_effect=lambda a, **kw: subprocess_calls.append({"argv": a})),
            patch("mill_vscode._vscode_processes.find_open_vscode_paths", return_value=set()),
            patch("mill_vscode.input", return_value="1", create=True),
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

    # ------------------------------------------------------------------
    # Test: filter_excludes_open_worktree — alpha open → only beta shown,
    # input "1" selects beta.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _make_git_repo(root)

        worktrees_dir = root / "worktrees"
        wt_alpha = worktrees_dir / "task-alpha"
        wt_beta = worktrees_dir / "task-beta"
        wt_alpha.mkdir(parents=True)
        wt_beta.mkdir(parents=True)
        _write_active_marker(wt_alpha, "task-alpha", "Alpha")
        _write_active_marker(wt_beta, "task-beta", "Beta")

        subprocess_calls: list[dict] = []

        with (
            patch("mill_vscode.resolve_git_root", return_value=root),
            patch("mill_vscode.resolve_wiki_path", return_value=root / "wiki"),
            patch("mill_vscode.resolve_worktrees_dir", return_value=worktrees_dir),
            patch("mill_vscode.subprocess.run", side_effect=lambda a, **kw: subprocess_calls.append({"argv": a})),
            patch("mill_vscode._vscode_processes.find_open_vscode_paths", return_value={Path(str(wt_alpha))}),
            patch("mill_vscode.input", return_value="1", create=True),
        ):
            rc = mill_vscode.main([])

        if rc != 0:
            print(f"FAIL: filter_excludes_open_worktree returned {rc}", file=sys.stderr)
            errors += 1
        elif not subprocess_calls or str(wt_beta) not in subprocess_calls[0]["argv"]:
            print(
                f"FAIL: filter_excludes_open_worktree: expected {wt_beta} in code argv, got {subprocess_calls}",
                file=sys.stderr,
            )
            errors += 1
        else:
            print("PASS: filter_excludes_open_worktree — open worktree filtered, remaining selected")

    # ------------------------------------------------------------------
    # Test: filter_empties_list_calls_spawn_then_opens — one worktree open,
    # filter empties list, spawn called, new worktree opened.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _make_git_repo(root)

        worktrees_dir = root / "worktrees"
        wt_alpha = worktrees_dir / "task-alpha"
        wt_beta = worktrees_dir / "task-beta"
        wt_alpha.mkdir(parents=True)
        _write_active_marker(wt_alpha, "task-alpha", "Alpha")

        spawn_callable = MagicMock(return_value=0)
        subprocess_calls = []

        with (
            patch("mill_vscode.resolve_git_root", return_value=root),
            patch("mill_vscode.resolve_wiki_path", return_value=root / "wiki"),
            patch("mill_vscode.resolve_worktrees_dir", return_value=worktrees_dir),
            patch(
                "mill_vscode._spawn_core.discover_active_worktrees",
                side_effect=[
                    [(wt_alpha, "task-alpha", "Alpha")],
                    [(wt_alpha, "task-alpha", "Alpha"), (wt_beta, "task-beta", "Beta")],
                ],
            ),
            patch("mill_vscode._load_spawn_main", return_value=spawn_callable),
            patch("mill_vscode.subprocess.run", side_effect=lambda a, **kw: subprocess_calls.append({"argv": a})),
            patch("mill_vscode._vscode_processes.find_open_vscode_paths", return_value={Path(str(wt_alpha))}),
        ):
            rc = mill_vscode.main([])

        if not spawn_callable.called:
            print("FAIL: filter_empties_list_calls_spawn_then_opens: spawn not called", file=sys.stderr)
            errors += 1
        elif spawn_callable.call_args_list[0] != call([]):
            print(
                f"FAIL: filter_empties_list_calls_spawn_then_opens: spawn args wrong: {spawn_callable.call_args_list}",
                file=sys.stderr,
            )
            errors += 1
        elif not subprocess_calls or str(wt_beta) not in subprocess_calls[0]["argv"]:
            print(
                f"FAIL: filter_empties_list_calls_spawn_then_opens: expected {wt_beta} in argv, got {subprocess_calls}",
                file=sys.stderr,
            )
            errors += 1
        else:
            print("PASS: filter_empties_list_calls_spawn_then_opens — all filtered → spawn + open new")

    # ------------------------------------------------------------------
    # Test: q_quits_with_zero — q input exits 0, no VS Code launched.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _make_git_repo(root)

        worktrees_dir = root / "worktrees"
        wt_alpha = worktrees_dir / "task-alpha"
        wt_beta = worktrees_dir / "task-beta"
        wt_alpha.mkdir(parents=True)
        wt_beta.mkdir(parents=True)
        _write_active_marker(wt_alpha, "task-alpha", "Alpha")
        _write_active_marker(wt_beta, "task-beta", "Beta")

        subprocess_calls = []

        with (
            patch("mill_vscode.resolve_git_root", return_value=root),
            patch("mill_vscode.resolve_wiki_path", return_value=root / "wiki"),
            patch("mill_vscode.resolve_worktrees_dir", return_value=worktrees_dir),
            patch("mill_vscode.subprocess.run", side_effect=lambda a, **kw: subprocess_calls.append({"argv": a})),
            patch("mill_vscode._vscode_processes.find_open_vscode_paths", return_value=set()),
            patch("mill_vscode.input", return_value="q", create=True),
        ):
            rc = mill_vscode.main([])

        if rc != 0:
            print(f"FAIL: q_quits_with_zero returned {rc}, expected 0", file=sys.stderr)
            errors += 1
        elif subprocess_calls:
            print("FAIL: q_quits_with_zero: subprocess.run called despite q", file=sys.stderr)
            errors += 1
        else:
            print("PASS: q_quits_with_zero — q input → exit 0, no VS Code")

    # ------------------------------------------------------------------
    # Test: enter_spawns_and_opens — empty input triggers spawn, new
    # worktree (gamma) opened via pre/post diff.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _make_git_repo(root)

        worktrees_dir = root / "worktrees"
        wt_alpha = worktrees_dir / "task-alpha"
        wt_beta = worktrees_dir / "task-beta"
        wt_gamma = worktrees_dir / "task-gamma"
        wt_alpha.mkdir(parents=True)
        wt_beta.mkdir(parents=True)
        _write_active_marker(wt_alpha, "task-alpha", "Alpha")
        _write_active_marker(wt_beta, "task-beta", "Beta")

        spawn_callable = MagicMock(return_value=0)
        subprocess_calls = []

        with (
            patch("mill_vscode.resolve_git_root", return_value=root),
            patch("mill_vscode.resolve_wiki_path", return_value=root / "wiki"),
            patch("mill_vscode.resolve_worktrees_dir", return_value=worktrees_dir),
            patch(
                "mill_vscode._spawn_core.discover_active_worktrees",
                side_effect=[
                    [(wt_alpha, "task-alpha", "Alpha"), (wt_beta, "task-beta", "Beta")],
                    [(wt_alpha, "task-alpha", "Alpha"), (wt_beta, "task-beta", "Beta"), (wt_gamma, "task-gamma", "Gamma")],
                ],
            ),
            patch("mill_vscode._load_spawn_main", return_value=spawn_callable),
            patch("mill_vscode.subprocess.run", side_effect=lambda a, **kw: subprocess_calls.append({"argv": a})),
            patch("mill_vscode._vscode_processes.find_open_vscode_paths", return_value=set()),
            patch("mill_vscode.input", return_value="", create=True),
        ):
            rc = mill_vscode.main([])

        if not spawn_callable.called:
            print("FAIL: enter_spawns_and_opens: spawn not called", file=sys.stderr)
            errors += 1
        elif spawn_callable.call_args_list[0] != call([]):
            print(
                f"FAIL: enter_spawns_and_opens: spawn args wrong: {spawn_callable.call_args_list}",
                file=sys.stderr,
            )
            errors += 1
        elif not subprocess_calls or str(wt_gamma) not in subprocess_calls[0]["argv"]:
            print(
                f"FAIL: enter_spawns_and_opens: expected {wt_gamma} in argv, got {subprocess_calls}",
                file=sys.stderr,
            )
            errors += 1
        else:
            print("PASS: enter_spawns_and_opens — <Enter> → spawn + open new worktree (gamma)")

    # ------------------------------------------------------------------
    # Test: new_flag_skips_list_and_opens_new — --new flag bypasses filter
    # and prompt, spawns and opens new worktree.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _make_git_repo(root)

        worktrees_dir = root / "worktrees"
        wt_alpha = worktrees_dir / "task-alpha"
        wt_beta = worktrees_dir / "task-beta"
        wt_gamma = worktrees_dir / "task-gamma"
        wt_alpha.mkdir(parents=True)
        wt_beta.mkdir(parents=True)
        _write_active_marker(wt_alpha, "task-alpha", "Alpha")
        _write_active_marker(wt_beta, "task-beta", "Beta")

        spawn_callable = MagicMock(return_value=0)
        subprocess_calls = []
        find_open_mock = MagicMock()
        input_mock = MagicMock()

        with (
            patch("mill_vscode.resolve_git_root", return_value=root),
            patch("mill_vscode.resolve_wiki_path", return_value=root / "wiki"),
            patch("mill_vscode.resolve_worktrees_dir", return_value=worktrees_dir),
            patch(
                "mill_vscode._spawn_core.discover_active_worktrees",
                side_effect=[
                    [(wt_alpha, "task-alpha", "Alpha"), (wt_beta, "task-beta", "Beta")],
                    [(wt_alpha, "task-alpha", "Alpha"), (wt_beta, "task-beta", "Beta"), (wt_gamma, "task-gamma", "Gamma")],
                ],
            ),
            patch("mill_vscode._load_spawn_main", return_value=spawn_callable),
            patch("mill_vscode.subprocess.run", side_effect=lambda a, **kw: subprocess_calls.append({"argv": a})),
            patch("mill_vscode._vscode_processes.find_open_vscode_paths", find_open_mock),
            patch("mill_vscode.input", input_mock, create=True),
        ):
            rc = mill_vscode.main(["--new"])

        if find_open_mock.called:
            print("FAIL: new_flag_skips_list_and_opens_new: find_open_vscode_paths called", file=sys.stderr)
            errors += 1
        elif input_mock.called:
            print("FAIL: new_flag_skips_list_and_opens_new: input() called", file=sys.stderr)
            errors += 1
        elif not spawn_callable.called:
            print("FAIL: new_flag_skips_list_and_opens_new: spawn not called", file=sys.stderr)
            errors += 1
        elif not subprocess_calls or str(wt_gamma) not in subprocess_calls[0]["argv"]:
            print(
                f"FAIL: new_flag_skips_list_and_opens_new: expected {wt_gamma} in argv, got {subprocess_calls}",
                file=sys.stderr,
            )
            errors += 1
        else:
            print("PASS: new_flag_skips_list_and_opens_new — --new skips filter+prompt, opens new worktree")

    # ------------------------------------------------------------------
    # Test: spawn_returns_zero_no_new_entries — <Enter> at prompt, spawn
    # succeeds but post-diff finds no new worktree → exit 0, no VS Code.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _make_git_repo(root)

        worktrees_dir = root / "worktrees"
        wt_alpha = worktrees_dir / "task-alpha"
        wt_alpha.mkdir(parents=True)
        _write_active_marker(wt_alpha, "task-alpha", "Alpha")

        spawn_callable = MagicMock(return_value=0)
        subprocess_calls = []

        with (
            patch("mill_vscode.resolve_git_root", return_value=root),
            patch("mill_vscode.resolve_wiki_path", return_value=root / "wiki"),
            patch("mill_vscode.resolve_worktrees_dir", return_value=worktrees_dir),
            patch(
                "mill_vscode._spawn_core.discover_active_worktrees",
                side_effect=[
                    [(wt_alpha, "task-alpha", "Alpha")],
                    [(wt_alpha, "task-alpha", "Alpha")],
                ],
            ),
            patch("mill_vscode._load_spawn_main", return_value=spawn_callable),
            patch("mill_vscode.subprocess.run", side_effect=lambda a, **kw: subprocess_calls.append({"argv": a})),
            patch("mill_vscode._vscode_processes.find_open_vscode_paths", return_value=set()),
            patch("mill_vscode.input", return_value="", create=True),
        ):
            rc = mill_vscode.main([])

        if rc != 0:
            print(f"FAIL: spawn_returns_zero_no_new_entries returned {rc}, expected 0", file=sys.stderr)
            errors += 1
        elif subprocess_calls:
            print("FAIL: spawn_returns_zero_no_new_entries: subprocess.run called", file=sys.stderr)
            errors += 1
        else:
            print("PASS: spawn_returns_zero_no_new_entries — spawn ok but no new entry → exit 0, no VS Code")

    # ------------------------------------------------------------------
    # Test: spawn_returns_nonzero — <Enter> at prompt, spawn returns 1 →
    # exit 1, no VS Code.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _make_git_repo(root)

        worktrees_dir = root / "worktrees"
        wt_alpha = worktrees_dir / "task-alpha"
        wt_alpha.mkdir(parents=True)
        _write_active_marker(wt_alpha, "task-alpha", "Alpha")

        spawn_callable = MagicMock(return_value=1)
        subprocess_calls = []

        with (
            patch("mill_vscode.resolve_git_root", return_value=root),
            patch("mill_vscode.resolve_wiki_path", return_value=root / "wiki"),
            patch("mill_vscode.resolve_worktrees_dir", return_value=worktrees_dir),
            patch(
                "mill_vscode._spawn_core.discover_active_worktrees",
                return_value=[(wt_alpha, "task-alpha", "Alpha")],
            ),
            patch("mill_vscode._load_spawn_main", return_value=spawn_callable),
            patch("mill_vscode.subprocess.run", side_effect=lambda a, **kw: subprocess_calls.append({"argv": a})),
            patch("mill_vscode._vscode_processes.find_open_vscode_paths", return_value=set()),
            patch("mill_vscode.input", return_value="", create=True),
        ):
            rc = mill_vscode.main([])

        if rc != 1:
            print(f"FAIL: spawn_returns_nonzero returned {rc}, expected 1", file=sys.stderr)
            errors += 1
        elif subprocess_calls:
            print("FAIL: spawn_returns_nonzero: subprocess.run called despite spawn failure", file=sys.stderr)
            errors += 1
        else:
            print("PASS: spawn_returns_nonzero — spawn rc 1 → exit 1, no VS Code")

    # ------------------------------------------------------------------
    # Test: new_and_slug_mutex — --new and --slug together → SystemExit(2).
    # ------------------------------------------------------------------
    try:
        mill_vscode.main(["--new", "--slug", "x"])
        print("FAIL: new_and_slug_mutex: no SystemExit raised", file=sys.stderr)
        errors += 1
    except SystemExit as exc:
        if exc.code == 2:
            print("PASS: new_and_slug_mutex — --new + --slug → SystemExit(2)")
        else:
            print(f"FAIL: new_and_slug_mutex: expected exit 2, got {exc.code}", file=sys.stderr)
            errors += 1

    # ------------------------------------------------------------------
    # Test: probe_failure_falls_back — empty probe result means all
    # worktrees shown unfiltered; input "1" selects first (alpha).
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _make_git_repo(root)

        worktrees_dir = root / "worktrees"
        wt_alpha = worktrees_dir / "task-alpha"
        wt_beta = worktrees_dir / "task-beta"

        subprocess_calls = []

        with (
            patch("mill_vscode.resolve_git_root", return_value=root),
            patch("mill_vscode.resolve_wiki_path", return_value=root / "wiki"),
            patch("mill_vscode.resolve_worktrees_dir", return_value=worktrees_dir),
            patch(
                "mill_vscode._spawn_core.discover_active_worktrees",
                return_value=[(wt_alpha, "task-alpha", "Alpha"), (wt_beta, "task-beta", "Beta")],
            ),
            patch("mill_vscode.subprocess.run", side_effect=lambda a, **kw: subprocess_calls.append({"argv": a})),
            patch("mill_vscode._vscode_processes.find_open_vscode_paths", return_value=set()),
            patch("mill_vscode.input", return_value="1", create=True),
        ):
            rc = mill_vscode.main([])

        if rc != 0:
            print(f"FAIL: probe_failure_falls_back returned {rc}, expected 0", file=sys.stderr)
            errors += 1
        elif not subprocess_calls or str(wt_alpha) not in subprocess_calls[0]["argv"]:
            print(
                f"FAIL: probe_failure_falls_back: expected {wt_alpha} in code argv, got {subprocess_calls}",
                file=sys.stderr,
            )
            errors += 1
        else:
            print("PASS: probe_failure_falls_back — empty probe → all shown, user picks 1 (alpha)")

    # ------------------------------------------------------------------
    # Test: probe_returns_unrelated_paths — unrelated paths don't filter
    # anything; input "2" selects beta.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _make_git_repo(root)

        worktrees_dir = root / "worktrees"
        wt_alpha = worktrees_dir / "task-alpha"
        wt_beta = worktrees_dir / "task-beta"

        subprocess_calls = []

        with (
            patch("mill_vscode.resolve_git_root", return_value=root),
            patch("mill_vscode.resolve_wiki_path", return_value=root / "wiki"),
            patch("mill_vscode.resolve_worktrees_dir", return_value=worktrees_dir),
            patch(
                "mill_vscode._spawn_core.discover_active_worktrees",
                return_value=[(wt_alpha, "task-alpha", "Alpha"), (wt_beta, "task-beta", "Beta")],
            ),
            patch("mill_vscode.subprocess.run", side_effect=lambda a, **kw: subprocess_calls.append({"argv": a})),
            patch("mill_vscode._vscode_processes.find_open_vscode_paths", return_value={Path("/some/unrelated/path")}),
            patch("mill_vscode.input", return_value="2", create=True),
        ):
            rc = mill_vscode.main([])

        if rc != 0:
            print(f"FAIL: probe_returns_unrelated_paths returned {rc}, expected 0", file=sys.stderr)
            errors += 1
        elif not subprocess_calls or str(wt_beta) not in subprocess_calls[0]["argv"]:
            print(
                f"FAIL: probe_returns_unrelated_paths: expected {wt_beta} in code argv, got {subprocess_calls}",
                file=sys.stderr,
            )
            errors += 1
        else:
            print("PASS: probe_returns_unrelated_paths — unrelated probe paths → no filter, user picks 2 (beta)")

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All mill-vscode unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
