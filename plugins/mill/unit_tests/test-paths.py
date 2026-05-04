"""Unit tests for plugins/mill/scripts/_paths.py.

# resolve_git_root is exercised end-to-end by test-spawn.py and test-merge.py.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS_DIR = HUB / "plugins" / "mill" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from unittest.mock import MagicMock, patch  # noqa: E402

import _active  # noqa: E402
import _paths  # noqa: E402
import _sibling  # noqa: E402


def _make_run_result(stdout: str = "", returncode: int = 0, stderr: str = "") -> MagicMock:
    result = MagicMock()
    result.stdout = stdout
    result.returncode = returncode
    result.stderr = stderr
    return result


def _write_config(repo_root: Path, yaml_text: str) -> None:
    (repo_root / ".millhouse").mkdir(parents=True, exist_ok=True)
    (repo_root / ".millhouse" / "config.local.yaml").write_text(yaml_text, encoding="utf-8")


def _container_form(tmp_path: Path) -> Path:
    """Create container-form main_root at tmp_path/wts/millhouse and return it."""
    wts_dir = tmp_path / "wts"
    wts_dir.mkdir(exist_ok=True)
    main_root = wts_dir / "millhouse"
    main_root.mkdir(exist_ok=True)
    return main_root


def main() -> int:
    try:
        assert _paths.resolve_path is _sibling.resolve_path, \
            "resolve_path must be re-exported identity from _sibling, not duplicated"
        print("PASS: _paths.resolve_path is _sibling.resolve_path (no duplication)")

        # resolve_hub_path

        got = _paths.resolve_hub_path()
        assert got == Path.cwd().resolve(), f"no-arg: got {got}"
        print("PASS: resolve_hub_path() with no argument returns Path.cwd().resolve()")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp).resolve()
            got = _paths.resolve_hub_path(tmp_path)
            assert got == tmp_path, f"explicit absolute: got {got}"
        print("PASS: resolve_hub_path(absolute_path) returns it resolved")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp).resolve()
            parent = tmp_path.parent
            rel = Path(tmp_path.name)
            got = _paths.resolve_hub_path(parent / rel)
            assert got == tmp_path, f"relative-like path: got {got}"
            assert got.is_absolute(), f"result must be absolute: got {got}"
        print("PASS: resolve_hub_path(relative-style path) returns an absolute path")

        # resolve_wiki_path — container-form default (main_root under wts/)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            main_root = _container_form(tmp_path)
            with patch("_paths.resolve_main_worktree_root", return_value=main_root):
                got = _paths.resolve_wiki_path(main_root)
            assert got == tmp_path / "wiki", f"container-form default: got {got}"
        print("PASS: resolve_wiki_path container-form default -> <container>/wiki")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            foo = tmp_path / "foo"
            foo.mkdir()
            with patch("_paths.resolve_main_worktree_root", return_value=foo):
                got = _paths.resolve_wiki_path(foo)
            assert got == tmp_path / "foo.wiki", f"prefix-form default: got {got}"
        print("PASS: resolve_wiki_path prefix-form default -> <parent>/<name>.wiki")

        # Old hub-form now falls through to prefix-form (intentional regression from Card 1)
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            hub = tmp_path / "hub"
            hub.mkdir()
            with patch("_paths.resolve_main_worktree_root", return_value=hub):
                got = _paths.resolve_wiki_path(hub)
            assert got == tmp_path / "hub.wiki", f"hub-form now prefix-form: got {got}"
        print("PASS: resolve_wiki_path old hub-form -> prefix-form hub.wiki (intentional regression)")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            main_root = _container_form(tmp_path)
            abs_override = tmp_path / "elsewhere" / "wiki"
            _write_config(main_root, f"paths:\n  wiki: {abs_override}\n")
            with patch("_paths.resolve_main_worktree_root", return_value=main_root):
                got = _paths.resolve_wiki_path(main_root)
            assert got == abs_override, f"absolute override: got {got}"
        print("PASS: resolve_wiki_path absolute paths.wiki override wins")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            main_root = _container_form(tmp_path).resolve()
            _write_config(main_root, "paths:\n  wiki: ../custom-wiki\n")
            with patch("_paths.resolve_main_worktree_root", return_value=main_root):
                got = _paths.resolve_wiki_path(main_root)
            assert got == (tmp_path / "wts" / "custom-wiki").resolve(), \
                f"relative override: got {got}"
        print("PASS: resolve_wiki_path relative paths.wiki override resolves against main root")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            main_root = _container_form(tmp_path)
            _write_config(main_root, "paths: {}\n")
            with patch("_paths.resolve_main_worktree_root", return_value=main_root):
                got = _paths.resolve_wiki_path(main_root)
            assert got == tmp_path / "wiki", f"empty paths block: got {got}"
        print("PASS: resolve_wiki_path with empty paths: block falls through to sibling default")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            main_root = _container_form(tmp_path)
            _write_config(main_root, "other_key: value\n")
            with patch("_paths.resolve_main_worktree_root", return_value=main_root):
                got = _paths.resolve_wiki_path(main_root)
            assert got == tmp_path / "wiki", f"no paths key: got {got}"
        print("PASS: resolve_wiki_path with no paths: key falls through to sibling default")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            main_root = _container_form(tmp_path)
            _write_config(main_root, "paths:\n  wiki: [this is not a string\n")
            with patch("_paths.resolve_main_worktree_root", return_value=main_root):
                try:
                    _paths.resolve_wiki_path(main_root)
                    raise AssertionError("malformed YAML should have raised")
                except Exception as exc:
                    import yaml
                    assert isinstance(exc, yaml.YAMLError), \
                        f"expected yaml.YAMLError, got {type(exc).__name__}: {exc}"
        print("PASS: resolve_wiki_path propagates yaml.YAMLError on malformed config")

        # resolve_wiki_path walk-up composition (child worktree scenarios)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            wts_dir = tmp_path / "wts"
            wts_dir.mkdir()
            main_root = wts_dir / "millhouse"
            main_root.mkdir()
            worktree = wts_dir / "feat"
            worktree.mkdir()
            with patch("_paths.resolve_main_worktree_root", return_value=main_root):
                got = _paths.resolve_wiki_path(worktree)
            assert got == tmp_path / "wiki", f"walk-up container-form: got {got}"
        print("PASS: resolve_wiki_path walk-up container-form (from child worktree) -> <container>/wiki")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            worktree = tmp_path / "foo.worktrees" / "feat"
            worktree.mkdir(parents=True)
            with patch("_paths.resolve_main_worktree_root", return_value=tmp_path / "foo"):
                got = _paths.resolve_wiki_path(worktree)
            assert got == tmp_path / "foo.wiki", f"walk-up prefix-form: got {got}"
        print("PASS: resolve_wiki_path walk-up prefix-form (from child worktree) -> <parent>/<name>.wiki")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            wts_dir = tmp_path / "wts"
            wts_dir.mkdir()
            main_root = wts_dir / "millhouse"
            main_root.mkdir()
            worktree = wts_dir / "feat"
            worktree.mkdir()
            _write_config(worktree, "paths:\n  wiki: ../custom-wiki\n")
            with patch("_paths.resolve_main_worktree_root", return_value=main_root):
                got = _paths.resolve_wiki_path(worktree)
            expected = (main_root / ".." / "custom-wiki").resolve()
            assert got == expected, f"walk-up override-anchors-on-main: got {got}"
        print("PASS: resolve_wiki_path walk-up: relative override resolves against main root, not child worktree")

        # resolve_worktrees_dir walk-up composition

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            wts_dir = tmp_path / "wts"
            wts_dir.mkdir()
            main_root = wts_dir / "millhouse"
            main_root.mkdir()
            worktree = wts_dir / "feat"
            worktree.mkdir()
            with patch("_paths.resolve_main_worktree_root", return_value=main_root):
                got = _paths.resolve_worktrees_dir({}, worktree)
            assert got == wts_dir, f"worktrees container-form fallback: got {got}"
        print("PASS: resolve_worktrees_dir container-form fallback -> wts/ (main_root.parent)")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            foo = tmp_path / "foo"
            foo.mkdir()
            # Prefix-form: fallback is main_root.parent (no automatic prefix-form sibling)
            with patch("_paths.resolve_main_worktree_root", return_value=foo):
                got = _paths.resolve_worktrees_dir({}, foo)
            # Prefix-form fallback is main_root.parent = tmp_path; prefix-form users must
            # configure spawn.worktrees_dir: for a sensible default.
            assert got == tmp_path, f"worktrees prefix-form fallback: got {got}"
        print("PASS: resolve_worktrees_dir prefix-form fallback -> main_root.parent (configure override for real use)")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            wts_dir = tmp_path / "wts"
            wts_dir.mkdir()
            main_root = wts_dir / "millhouse"
            main_root.mkdir()
            cfg = {"spawn": {"worktrees_dir": "<CONTAINER_PATH>/custom-worktrees"}}
            with patch("_paths.resolve_main_worktree_root", return_value=main_root):
                got = _paths.resolve_worktrees_dir(cfg, main_root)
            assert got == tmp_path / "custom-worktrees", f"worktrees template override: got {got}"
        print("PASS: resolve_worktrees_dir template override anchors on main root via CONTAINER_PATH")

        # resolve_main_worktree_root

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            main_root = _container_form(tmp_path).resolve()
            mock_result = _make_run_result(stdout=".git\n")
            with patch("_subprocess_util.run", return_value=mock_result):
                got = _paths.resolve_main_worktree_root(main_root)
            assert got == main_root, f"container-form: got {got}"
        print("PASS: resolve_main_worktree_root container-form (.git relative) -> git_root")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            wts_dir = tmp_path / "wts"
            wts_dir.mkdir()
            main_root = wts_dir / "millhouse"
            git_root = wts_dir / "feat"
            git_root.mkdir()
            mock_stdout = str(main_root / ".git") + "\n"
            mock_result = _make_run_result(stdout=mock_stdout)
            with patch("_subprocess_util.run", return_value=mock_result):
                got = _paths.resolve_main_worktree_root(git_root)
            assert got == main_root, f"worktree-form: got {got}"
        print("PASS: resolve_main_worktree_root worktree-form (absolute stdout) -> main hub")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            main_root = _container_form(tmp_path)
            mock_result = _make_run_result(returncode=1, stderr="not a git repository")
            with patch("_subprocess_util.run", return_value=mock_result):
                try:
                    _paths.resolve_main_worktree_root(main_root)
                    raise AssertionError("expected SystemExit, got none")
                except SystemExit as exc:
                    msg = str(exc)
                    assert str(main_root) in msg, f"error msg missing git_root: {msg!r}"
                    assert "not a git repository" in msg, f"error msg missing stderr: {msg!r}"
        print("PASS: resolve_main_worktree_root returncode=1 -> SystemExit with git_root and stderr")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            main_root = _container_form(tmp_path).resolve()
            for stdout_val in [".git\r\n", "  .git  \n"]:
                mock_result = _make_run_result(stdout=stdout_val)
                with patch("_subprocess_util.run", return_value=mock_result):
                    got = _paths.resolve_main_worktree_root(main_root)
                assert got == main_root, f"whitespace/CRLF tolerance: stdout={stdout_val!r} got {got}"
        print("PASS: resolve_main_worktree_root tolerates CRLF and surrounding whitespace")

        # resolve_short_name
        got = _paths.resolve_short_name({"repo": {"short_name": "MH"}}, "millhouse")
        assert got == "MH", f"configured short_name: got {got!r}"
        print("PASS: resolve_short_name configured value 'MH' returned as-is")

        got = _paths.resolve_short_name({"repo": {"short_name": ""}}, "millhouse")
        assert got == "MI", f"empty short_name fallback: got {got!r}"
        print("PASS: resolve_short_name empty string falls back to repo_name[:2].upper()")

        got = _paths.resolve_short_name({}, "millhouse")
        assert got == "MI", f"missing repo block fallback: got {got!r}"
        print("PASS: resolve_short_name missing repo: block falls back to repo_name[:2].upper()")

        got = _paths.resolve_short_name({"repo": {}}, "millhouse")
        assert got == "MI", f"missing short_name key fallback: got {got!r}"
        print("PASS: resolve_short_name missing short_name key falls back to repo_name[:2].upper()")

        got = _paths.resolve_short_name({}, "foobar")
        assert got == "FO", f"repo_name=foobar fallback: got {got!r}"
        print("PASS: resolve_short_name repo_name='foobar' -> 'FO'")

        got = _paths.resolve_short_name({}, "x")
        assert got == "X", f"repo_name=x fallback: got {got!r}"
        print("PASS: resolve_short_name repo_name='x' -> 'X'")

        # resolve_hub_relative_path

        root = Path("/some/worktree")
        got = _paths.resolve_hub_relative_path(root, ".")
        assert got == root, f"dot returns worktree_root unchanged: got {got}"
        print("PASS: resolve_hub_relative_path('.') returns worktree_root unchanged")

        got = _paths.resolve_hub_relative_path(root, "src/csharp/X")
        assert got == root / "src" / "csharp" / "X", f"nested subpath: got {got}"
        print("PASS: resolve_hub_relative_path nested subpath -> worktree_root / subpath")

        got = _paths.resolve_hub_relative_path(root, "sub")
        assert got == root / "sub", f"single subpath: got {got}"
        print("PASS: resolve_hub_relative_path single subpath -> worktree_root / subpath")

        got = _paths.resolve_hub_relative_path(root, "sub/")
        assert got == root / "sub", f"trailing slash normalised: got {got}"
        print("PASS: resolve_hub_relative_path trailing slash is normalised away")

        try:
            _paths.resolve_hub_relative_path(root, "/absolute/path")
            raise AssertionError("expected ValueError for absolute hub_subpath")
        except ValueError as exc:
            assert "/absolute/path" in str(exc), f"ValueError missing offending value: {exc}"
        print("PASS: resolve_hub_relative_path absolute hub_subpath raises ValueError naming the value")

        # resolve_active_worktree

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            wts_dir = tmp_path / "wts"
            wts_dir.mkdir()
            worktree = wts_dir / "my-task"
            worktree.mkdir()
            mill_dir = worktree / ".millhouse"
            _active.write(
                mill_dir,
                slug="my-task",
                task_title="Test task",
                branch="hanf/my-task",
                spawned_at="2026-01-01T00:00:00Z",
            )
            got = _paths.resolve_active_worktree(tmp_path, "my-task")
            assert got == worktree, f"happy path: got {got}"
        print("PASS: resolve_active_worktree happy path returns container_path/wts/slug")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "wts").mkdir()
            try:
                _paths.resolve_active_worktree(tmp_path, "missing-slug")
                raise AssertionError("expected ActiveWorktreeNotFound")
            except _paths.ActiveWorktreeNotFound:
                pass
        print("PASS: resolve_active_worktree raises ActiveWorktreeNotFound when directory absent")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            wts_dir = tmp_path / "wts"
            wts_dir.mkdir()
            worktree = wts_dir / "my-task"
            worktree.mkdir()
            mill_dir = worktree / ".millhouse"
            _active.write(
                mill_dir,
                slug="different-slug",
                task_title="Test task",
                branch="hanf/different-slug",
                spawned_at="2026-01-01T00:00:00Z",
            )
            try:
                _paths.resolve_active_worktree(tmp_path, "my-task")
                raise AssertionError("expected ActiveWorktreeSlugMismatch")
            except _paths.ActiveWorktreeSlugMismatch:
                pass
        print("PASS: resolve_active_worktree raises ActiveWorktreeSlugMismatch when marker slug differs")

        # resolve_container_path

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            wts_dir = tmp_path / "wts"
            wts_dir.mkdir()
            main_root = wts_dir / "millhouse"
            main_root.mkdir()
            with patch("_paths.resolve_main_worktree_root", return_value=main_root):
                got = _paths.resolve_container_path(main_root)
            assert got == tmp_path, f"container-form: got {got}"
        print("PASS: resolve_container_path container-form -> grandparent (container dir)")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            main_root = tmp_path / "foo"
            main_root.mkdir()
            with patch("_paths.resolve_main_worktree_root", return_value=main_root):
                got = _paths.resolve_container_path(main_root)
            assert got == tmp_path, f"prefix-form: got {got}"
        print("PASS: resolve_container_path prefix-form -> parent dir")

        print("All _paths unit tests passed.")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
