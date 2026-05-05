"""Unit tests for plugins/mill/scripts/millpy-worktree.py."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

# Load millpy-worktree.py via importlib (hyphenated name).
_SCRIPT = HUB / "plugins" / "mill" / "scripts" / "millpy-worktree.py"
_spec = importlib.util.spec_from_file_location("mill_worktree", _SCRIPT)
mill_worktree = importlib.util.module_from_spec(_spec)
sys.modules["mill_worktree"] = mill_worktree
_spec.loader.exec_module(mill_worktree)

import _subprocess_util  # noqa: E402,F401


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

    # ------------------------------------------------------------------
    # Test: standard layout regression — hub state at worktree_path/.millhouse/
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _make_git_repo(root)
        (root / ".millhouse").mkdir()

        worktrees_dir = root / "worktrees"
        worktree_path = worktrees_dir / "feature-x"

        git_calls2: list[list[str]] = []

        def capture_run2(argv, **kwargs):
            git_calls2.append(list(argv))
            if "--verify" in argv:
                return MagicMock(returncode=1, stderr="", stdout="")
            if "branch" in argv:
                return MagicMock(returncode=0, stderr="", stdout="")
            if "worktree" in argv and "add" in argv:
                worktrees_dir.mkdir(parents=True, exist_ok=True)
                worktree_path.mkdir(exist_ok=True)
                return MagicMock(returncode=0, stderr="", stdout="")
            return MagicMock(returncode=0, stderr="", stdout="")

        copy_calls: list[dict] = []

        def capture_copy(src, dst, exclude):
            copy_calls.append({"src": src, "dst": dst})

        vscode_calls2: list[dict] = []

        def capture_vscode2(color_hex, target, *, window_title=None, **kw):
            vscode_calls2.append({"target": target})

        hub_path = root

        with (
            patch("mill_worktree.resolve_git_root", return_value=root),
            patch("mill_worktree.resolve_hub_path", return_value=hub_path),
            patch("mill_worktree.resolve_hub_relative_path",
                  side_effect=lambda wt, sub: wt if sub == "." else wt / sub),
            patch("mill_worktree.resolve_container_path", return_value=root.parent),
            patch("mill_worktree.resolve_main_worktree_root", return_value=root),
            patch("mill_worktree.resolve_worktrees_dir", return_value=worktrees_dir),
            patch("mill_worktree.resolve_wiki_path", side_effect=SystemExit("no wiki")),
            patch("mill_worktree._load_config", return_value={}),
            patch("_subprocess_util.run", side_effect=capture_run2),
            patch("mill_worktree._vscode.write_settings", side_effect=capture_vscode2),
            patch("mill_worktree._worktree.copy_millhouse", side_effect=capture_copy),
        ):
            rc = mill_worktree.main(["create", "--branch", "feature-x"])

        if rc != 0:
            print(f"FAIL: standard-layout create returned {rc}", file=sys.stderr)
            errors += 1
        elif not copy_calls:
            print("FAIL: standard-layout -- copy_millhouse not called", file=sys.stderr)
            errors += 1
        elif copy_calls[0]["src"] != hub_path / ".millhouse":
            print(
                f"FAIL: standard-layout -- copy src should be {hub_path / '.millhouse'!r}, "
                f"got {copy_calls[0]['src']!r}",
                file=sys.stderr,
            )
            errors += 1
        elif copy_calls[0]["dst"] != worktree_path / ".millhouse":
            print(
                f"FAIL: standard-layout -- copy dst should be {worktree_path / '.millhouse'!r}, "
                f"got {copy_calls[0]['dst']!r}",
                file=sys.stderr,
            )
            errors += 1
        elif not vscode_calls2 or vscode_calls2[0]["target"] != worktree_path / ".vscode" / "settings.json":
            print(
                f"FAIL: standard-layout -- vscode target wrong: {vscode_calls2}",
                file=sys.stderr,
            )
            errors += 1
        elif (worktree_path / ".millhouse" / "config.local.yaml").exists():
            # No bootstrap stub should be written for standard layout
            print(
                "FAIL: standard-layout -- unexpected bootstrap stub at worktree_path/.millhouse/config.local.yaml",
                file=sys.stderr,
            )
            errors += 1
        else:
            print("PASS: standard-layout -- hub state at worktree_path/.millhouse/")

    # ------------------------------------------------------------------
    # Test: subfolder-install — hub state at dest_hub, bootstrap stub written
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _make_git_repo(root)
        (root / ".millhouse").mkdir()

        hub_subpath = "src/Models"
        worktrees_dir = root / "worktrees"
        worktree_path = worktrees_dir / "feature-x"
        dest_hub = worktree_path / hub_subpath

        def capture_run3(argv, **kwargs):
            if "--verify" in argv:
                return MagicMock(returncode=1, stderr="", stdout="")
            if "branch" in argv:
                return MagicMock(returncode=0, stderr="", stdout="")
            if "worktree" in argv and "add" in argv:
                worktrees_dir.mkdir(parents=True, exist_ok=True)
                worktree_path.mkdir(exist_ok=True)
                return MagicMock(returncode=0, stderr="", stdout="")
            return MagicMock(returncode=0, stderr="", stdout="")

        copy_calls3: list[dict] = []

        def capture_copy3(src, dst, exclude):
            copy_calls3.append({"src": src, "dst": dst})

        vscode_calls3: list[dict] = []

        def capture_vscode3(color_hex, target, *, window_title=None, **kw):
            vscode_calls3.append({"target": target})

        fake_wiki = Path("/fake/wiki")
        with (
            patch("mill_worktree.resolve_git_root", return_value=root),
            patch("mill_worktree.resolve_hub_path", return_value=root),
            patch("mill_worktree.resolve_hub_relative_path",
                  side_effect=lambda wt, sub: wt if sub == "." else wt / sub),
            patch("mill_worktree.resolve_container_path", return_value=root.parent),
            patch("mill_worktree.resolve_main_worktree_root", return_value=root),
            patch("mill_worktree.resolve_worktrees_dir", return_value=worktrees_dir),
            patch("mill_worktree.resolve_wiki_path", return_value=fake_wiki),
            patch("mill_worktree._load_config", return_value={"hub_relative_path": hub_subpath}),
            patch("mill_worktree._wiki.read_junctions", return_value={}),
            patch("_subprocess_util.run", side_effect=capture_run3),
            patch("mill_worktree._vscode.write_settings", side_effect=capture_vscode3),
            patch("mill_worktree._worktree.copy_millhouse", side_effect=capture_copy3),
        ):
            rc = mill_worktree.main(["create", "--branch", "feature-x"])

        import yaml

        stub_path = worktree_path / ".millhouse" / "config.local.yaml"
        failed = False
        if rc != 0:
            print(f"FAIL: subfolder-install create returned {rc}", file=sys.stderr)
            failed = True
        elif not copy_calls3:
            print("FAIL: subfolder-install -- copy_millhouse not called", file=sys.stderr)
            failed = True
        elif copy_calls3[0]["dst"] != dest_hub / ".millhouse":
            print(
                f"FAIL: subfolder-install -- copy dst should be {dest_hub / '.millhouse'!r}, "
                f"got {copy_calls3[0]['dst']!r}",
                file=sys.stderr,
            )
            failed = True
        elif not vscode_calls3 or vscode_calls3[0]["target"] != dest_hub / ".vscode" / "settings.json":
            print(
                f"FAIL: subfolder-install -- vscode target wrong: {vscode_calls3}",
                file=sys.stderr,
            )
            failed = True
        elif not stub_path.exists():
            print(
                f"FAIL: subfolder-install -- bootstrap stub not found at {stub_path}",
                file=sys.stderr,
            )
            failed = True
        else:
            stub_cfg = yaml.safe_load(stub_path.read_text(encoding="utf-8")) or {}
            if stub_cfg != {"hub_relative_path": hub_subpath}:
                print(
                    f"FAIL: subfolder-install -- stub content wrong: {stub_cfg!r}",
                    file=sys.stderr,
                )
                failed = True

        if not failed:
            print("PASS: subfolder-install -- hub state at dest_hub, bootstrap stub written")
        else:
            errors += 1

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All mill-worktree unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
