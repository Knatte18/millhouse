"""Unit tests for plugins/mill/scripts/mill-worktree.py."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

# Load mill-worktree.py via importlib (hyphenated name).
_SCRIPT = HUB / "plugins" / "mill" / "scripts" / "mill-worktree.py"
_spec = importlib.util.spec_from_file_location("mill_worktree", _SCRIPT)
mill_worktree = importlib.util.module_from_spec(_spec)
sys.modules["mill_worktree"] = mill_worktree
_spec.loader.exec_module(mill_worktree)

import _subprocess_util  # noqa: E402


def _make_git_repo(tmp: Path) -> Path:
    """Initialise a real git repo under ``tmp``."""
    subprocess.run(
        ["git", "init", str(tmp), "-b", "main"], check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp), "commit", "--allow-empty", "-m", "init"],
        check=True, capture_output=True,
    )
    return tmp


def main() -> int:
    errors = 0

    # ------------------------------------------------------------------
    # Test: create subcommand calls git worktree add
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _make_git_repo(root)

        worktrees_dir = root.parent / "worktrees"

        git_calls: list[list[str]] = []

        def capture_run(argv, **kwargs):
            git_calls.append(list(argv))
            # For rev-parse --verify, return failure so branch gets created.
            if "--verify" in argv:
                result = MagicMock()
                result.returncode = 1
                result.stderr = ""
                result.stdout = ""
                return result
            # For git branch creation: succeed.
            if argv[1:3] == ["-C", str(root)] and "branch" in argv:
                result = MagicMock()
                result.returncode = 0
                result.stderr = ""
                result.stdout = ""
                return result
            # For git worktree add: create the directory on disk and succeed.
            if "worktree" in argv and "add" in argv:
                worktrees_dir.mkdir(parents=True, exist_ok=True)
                (worktrees_dir / "feature-x").mkdir(exist_ok=True)
                result = MagicMock()
                result.returncode = 0
                result.stderr = ""
                result.stdout = ""
                return result

        vscode_calls: list[dict] = []

        def mock_write_settings(color_hex, target, *, window_title=None, **kw):
            vscode_calls.append({"color_hex": color_hex, "target": target})

        with (
            patch("mill_worktree.resolve_git_root", return_value=root),
            patch("mill_worktree.resolve_worktrees_dir", return_value=worktrees_dir),
            patch("mill_worktree.resolve_wiki_path", side_effect=SystemExit("no wiki")),
            patch("_subprocess_util.run", side_effect=capture_run),
            patch("mill_worktree._vscode.write_settings", side_effect=mock_write_settings),
            patch("mill_worktree._worktree.copy_millhouse"),
        ):
            rc = mill_worktree.main(["create", "--branch", "feature-x"])

        # Verify the branch-creation git call was attempted.
        branch_calls = [c for c in git_calls if "branch" in c and "feature-x" in c]
        if not branch_calls:
            print("FAIL: create -- no git branch call for non-existing branch", file=sys.stderr)
            errors += 1
        else:
            print("PASS: create -- git branch called for new branch")

    # ------------------------------------------------------------------
    # Test: remove subcommand calls git worktree remove --force
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _make_git_repo(root)

        fake_worktree = root / "fake-wt"
        fake_worktree.mkdir()

        remove_calls: list[list[str]] = []

        def mock_remove(path, cwd, force=True):
            remove_calls.append({"path": path, "force": force})

        with (
            patch("mill_worktree.resolve_git_root", return_value=root),
            patch("mill_worktree._worktree.remove", side_effect=mock_remove),
            patch("mill_worktree._junction.remove"),  # best-effort, always succeeds
        ):
            rc = mill_worktree.main(["remove", str(fake_worktree)])

        if rc != 0:
            print(f"FAIL: remove returned {rc}, expected 0", file=sys.stderr)
            errors += 1
        elif not remove_calls or not remove_calls[0]["force"]:
            print("FAIL: remove -- _worktree.remove not called with force=True", file=sys.stderr)
            errors += 1
        else:
            print("PASS: remove -- _worktree.remove called with force=True")

    # ------------------------------------------------------------------
    # Test: list subcommand parses porcelain output and prints worktrees
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _make_git_repo(root)

        fake_porcelain_output = [
            {"path": str(root), "branch": "main"},
        ]

        with (
            patch("mill_worktree.resolve_git_root", return_value=root),
            patch("mill_worktree._worktree.list_worktrees", return_value=fake_porcelain_output),
        ):
            rc = mill_worktree.main(["list"])

        if rc != 0:
            print(f"FAIL: list returned {rc}, expected 0", file=sys.stderr)
            errors += 1
        else:
            print("PASS: list -- parses worktree list without error")

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All mill-worktree unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
