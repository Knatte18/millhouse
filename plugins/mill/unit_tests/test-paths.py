"""Unit tests for plugins/mill/scripts/_paths.py.

# resolve_git_root is exercised end-to-end by test-spawn.py and test-merge.py.
"""
from __future__ import annotations

import contextlib
import io
import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS_DIR = HUB / "plugins" / "mill" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from unittest.mock import patch  # noqa: E402
import subprocess  # noqa: E402

import _marker  # noqa: E402
import _paths  # noqa: E402
import _sibling  # noqa: E402

_UNIT_TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_UNIT_TESTS))


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


def _make_active_marker(worktree_dir: Path, *, branch: str) -> None:
    """Create a real git repo checked out on branch (replaces old marker-write helper)."""
    import _test_helpers  # noqa: E402
    repo = _test_helpers.init_minimal_git_repo(worktree_dir, branch="main")
    _test_helpers.checkout_new_branch(repo, branch)


def _write_stub(mill_dir, hub_relative_path):
    mill_dir.mkdir(parents=True, exist_ok=True)
    (mill_dir / "config.local.yaml").write_text(
        f"hub_relative_path: {hub_relative_path}\n", encoding="utf-8"
    )


def test_resolve_task_path() -> None:
    # Case 1: _mill/discussion.md exists -> returns _mill/ path, no [compat] in stderr
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "_mill").mkdir()
        (root / "_mill" / "discussion.md").write_text("", encoding="utf-8")
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            got = _paths.resolve_task_path(root, "_mill/discussion.md")
        assert got == root / "_mill" / "discussion.md", f"case 1: got {got}"
        assert "[compat]" not in buf.getvalue(), "case 1: unexpected [compat] in stderr"
    print("PASS resolve_task_path case 1: _mill/ target exists -> _mill/ path, no stderr")

    # Case 2: _mill/ absent, task/ present -> falls back, [compat] in stderr
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "task").mkdir()
        (root / "task" / "discussion.md").write_text("", encoding="utf-8")
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            got = _paths.resolve_task_path(root, "_mill/discussion.md")
        assert got == root / "task" / "discussion.md", f"case 2: got {got}"
        assert "[compat]" in buf.getvalue(), "case 2: expected [compat] in stderr"
    print("PASS resolve_task_path case 2: _mill/ absent, task/ present -> task/ path, [compat] stderr")

    # Case 3: neither exists -> returns _mill/ path, no [compat] in stderr
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            got = _paths.resolve_task_path(root, "_mill/discussion.md")
        assert got == root / "_mill" / "discussion.md", f"case 3: got {got}"
        assert "[compat]" not in buf.getvalue(), "case 3: unexpected [compat] in stderr"
    print("PASS resolve_task_path case 3: neither exists -> _mill/ path, no stderr")

    # Case 4: _mill/plan/ directory exists -> returns _mill/plan/ path
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "_mill" / "plan").mkdir(parents=True)
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            got = _paths.resolve_task_path(root, "_mill/plan/")
        assert got == root / "_mill" / "plan", f"case 4: got {got}"
        assert "[compat]" not in buf.getvalue(), "case 4: unexpected [compat] in stderr"
    print("PASS resolve_task_path case 4: _mill/plan/ dir exists -> _mill/plan/ path")

    # Case 5: _mill/plan/ absent, task/plan/ present -> falls back, [compat] in stderr
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "task" / "plan").mkdir(parents=True)
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            got = _paths.resolve_task_path(root, "_mill/plan/")
        assert got == root / "task" / "plan", f"case 5: got {got}"
        assert "[compat]" in buf.getvalue(), "case 5: expected [compat] in stderr"
    print("PASS resolve_task_path case 5: _mill/plan/ absent, task/plan/ present -> task/plan/, [compat] stderr")

    # Case 6: cfg_relative_path without _mill/ -> direct return, no fallback attempted
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            got = _paths.resolve_task_path(root, "task/status.md")
        assert got == root / "task" / "status.md", f"case 6: got {got}"
        assert "[compat]" not in buf.getvalue(), "case 6: unexpected [compat] in stderr"
    print("PASS resolve_task_path case 6: no _mill/ in path -> direct return, no fallback")

    # Case 7: empty _mill/plan/ dir + task/plan/ present -> task/plan/, [compat] stderr
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "_mill" / "plan").mkdir(parents=True)
        (root / "task" / "plan").mkdir(parents=True)
        (root / "task" / "plan" / "01-batch.md").write_text("", encoding="utf-8")
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            got = _paths.resolve_task_path(root, "_mill/plan/")
        assert got == root / "task" / "plan", f"case 7: got {got}"
        assert "[compat]" in buf.getvalue(), "case 7: expected [compat] in stderr"
    print("PASS resolve_task_path case 7: empty _mill/plan/ dir + task/plan/ present -> task/plan/, [compat] stderr")


def test_status_path() -> None:
    """Merged in from former test-paths-status.py."""
    cfg = {"paths": {"status_md": "_mill/status.md"}}

    # Case 1: file exists -> returns configured path, no [compat] in stderr
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "_mill").mkdir()
        (root / "_mill" / "status.md").write_text("", encoding="utf-8")
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            got = _paths.status_path(root, cfg)
        assert got == root / "_mill" / "status.md", f"case 1: got {got}"
        assert "[compat]" not in buf.getvalue(), "case 1: unexpected [compat] in stderr"
    print("PASS status_path case 1: _mill/status.md exists -> configured path, no stderr")

    # Case 2: _mill/status.md missing, task/status.md present -> compat fallback with [compat] in stderr
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "task").mkdir()
        (root / "task" / "status.md").write_text("", encoding="utf-8")
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            got = _paths.status_path(root, cfg)
        assert got == root / "task" / "status.md", f"case 2: got {got}"
        assert "[compat]" in buf.getvalue(), "case 2: expected [compat] in stderr"
    print("PASS status_path case 2: _mill/ absent, task/status.md present -> task/ path, [compat] stderr")

    # Case 3: neither file exists -> returns configured path, no [compat]
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            got = _paths.status_path(root, cfg)
        assert got == root / "_mill" / "status.md", f"case 3: got {got}"
        assert "[compat]" not in buf.getvalue(), "case 3: unexpected [compat] in stderr"
    print("PASS status_path case 3: neither file exists -> configured path, no stderr")

    # Case 4: cfg has no 'paths' key -> KeyError naming paths.status_md
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        try:
            _paths.status_path(root, {})
            raise AssertionError("case 4: expected KeyError, got none")
        except KeyError as exc:
            assert "paths.status_md" in str(exc), f"case 4: KeyError message missing 'paths.status_md': {exc}"
    print("PASS status_path case 4: cfg={} -> KeyError naming paths.status_md")

    # Case 5: cfg has 'paths' but no 'status_md' key -> KeyError naming paths.status_md
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        try:
            _paths.status_path(root, {"paths": {}})
            raise AssertionError("case 5: expected KeyError, got none")
        except KeyError as exc:
            assert "paths.status_md" in str(exc), f"case 5: KeyError message missing 'paths.status_md': {exc}"
    print("PASS status_path case 5: cfg={'paths': {}} -> KeyError naming paths.status_md")


def main() -> int:
    try:
        assert _paths.resolve_path is _sibling.resolve_path, \
            "resolve_path must be re-exported identity from _sibling, not duplicated"
        print("PASS: _paths.resolve_path is _sibling.resolve_path (no duplication)")

        # resolve_hub_path -- since the refactor, resolves via git common dir
        # rather than trusting cwd. Outside a git repo, falls back to the
        # provided/cwd path resolved (preserves the original behaviour for
        # pre-init callers like mill-setup).

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp).resolve()
            got = _paths.resolve_hub_path(tmp_path)
            assert got == tmp_path, f"non-git absolute: got {got}"
        print("PASS: resolve_hub_path(absolute_path) outside git -> falls back to path resolved")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp).resolve()
            parent = tmp_path.parent
            rel = Path(tmp_path.name)
            got = _paths.resolve_hub_path(parent / rel)
            assert got == tmp_path, f"relative-like path: got {got}"
            assert got.is_absolute(), f"result must be absolute: got {got}"
        print("PASS: resolve_hub_path(relative-style path) outside git -> falls back to absolute")

        # Inside a git repo: returns the main worktree root regardless of
        # whether cwd is the hub, a hub subdir, or a child worktree.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp).resolve()
            hub = tmp_path / "hub"
            hub.mkdir()
            import _test_helpers
            _test_helpers.init_minimal_git_repo(hub, branch="main")
            sub = hub / ".millhouse"
            sub.mkdir()
            assert _paths.resolve_hub_path(hub) == hub
            assert _paths.resolve_hub_path(sub) == hub, \
                f"hub subdir should resolve to hub, got {_paths.resolve_hub_path(sub)}"
        print("PASS: resolve_hub_path inside git resolves subdirs to hub")

        # M2+sub: hub is a subdir of the git root; .millhouse/ lives there, not at root.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp).resolve()
            git_root_dir = tmp_path / "repo"
            git_root_dir.mkdir()
            _test_helpers.init_minimal_git_repo(git_root_dir, branch="main")
            hub_dir = git_root_dir / "src" / "subproj"
            hub_dir.mkdir(parents=True)
            (hub_dir / ".millhouse").mkdir()
            (hub_dir / ".millhouse" / "config.local.yaml").write_text(
                "hub_relative_path: src/subproj\n", encoding="utf-8"
            )
            # cwd = hub itself
            got = _paths.resolve_hub_path(hub_dir)
            assert got == hub_dir, \
                f"M2+sub cwd=hub: expected {hub_dir}, got {got}"
            # cwd = nested inside hub
            nested = hub_dir / "some" / "nested"
            nested.mkdir(parents=True)
            got2 = _paths.resolve_hub_path(nested)
            assert got2 == hub_dir, \
                f"M2+sub cwd=hub/nested: expected {hub_dir}, got {got2}"
        print("PASS: resolve_hub_path M2+sub returns hub subdir when cwd is inside it")

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

        # resolve_wiki_path subfolder-install stub-aware tests

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            main_root = _container_form(tmp_path)
            # Stub points at sub/hub
            _write_config(main_root, "hub_relative_path: sub/hub\n")
            # Real config at sub/hub has paths.wiki override
            real_mill_dir = main_root / "sub" / "hub" / ".millhouse"
            real_mill_dir.mkdir(parents=True, exist_ok=True)
            override_wiki = tmp_path / "override" / "wiki"
            (real_mill_dir / "config.local.yaml").write_text(
                f"paths:\n  wiki: {override_wiki}\n", encoding="utf-8"
            )
            with patch("_paths.resolve_main_worktree_root", return_value=main_root):
                got = _paths.resolve_wiki_path(main_root)
            assert got == override_wiki, f"subfolder stub + real config: got {got}"
        print("PASS: resolve_wiki_path subfolder-install: paths.wiki read from real config at hub subpath")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            main_root = _container_form(tmp_path)
            # Stub points at sub/hub but no real config exists there
            _write_config(main_root, "hub_relative_path: sub/hub\n")
            with patch("_paths.resolve_main_worktree_root", return_value=main_root):
                got = _paths.resolve_wiki_path(main_root)
            assert got == tmp_path / "wiki", f"subfolder stub no real config: got {got}"
        print("PASS: resolve_wiki_path subfolder-install: no real config falls back to sibling default")

        # resolve_mill_config_path

        test_repo_root = Path("/some/repo")
        got = _paths.resolve_mill_config_path(test_repo_root)
        assert got == test_repo_root / "mill-config.yaml", f"got {got}"
        print("PASS: resolve_mill_config_path returns repo_root / 'mill-config.yaml'")

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

        # Container-form: call on a real git repo
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            main_root = _container_form(tmp_path).resolve()
            subprocess.run(["git", "init", "--quiet", str(main_root)], check=True)
            got = _paths.resolve_main_worktree_root(main_root)
            assert got == main_root, f"container-form: got {got}"
        print("PASS: resolve_main_worktree_root container-form (real repo) -> git_root")

        # Worktree-form: create a real linked worktree via subprocess
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            wts_dir = tmp_path / "wts"
            wts_dir.mkdir()
            main_root = wts_dir / "millhouse"
            main_root.mkdir()
            subprocess.run(["git", "init", "--quiet", str(main_root)], check=True)
            linked_worktree = wts_dir / "feat"
            subprocess.run(
                ["git", "-C", str(main_root), "worktree", "add", str(linked_worktree)],
                capture_output=True,
            )
            got = _paths.resolve_main_worktree_root(linked_worktree)
            assert got == main_root, f"worktree-form: got {got}"
        print("PASS: resolve_main_worktree_root worktree-form (real linked worktree) -> main hub")

        # Error test: pass non-repo directory
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            not_repo = tmp_path / "not-repo"
            not_repo.mkdir()
            try:
                _paths.resolve_main_worktree_root(not_repo)
                raise AssertionError("expected SystemExit, got none")
            except SystemExit as exc:
                msg = str(exc)
                assert str(not_repo) in msg, f"error msg missing git_root: {msg!r}"
                assert "git" in msg.lower(), f"error msg should mention git: {msg!r}"
        print("PASS: resolve_main_worktree_root non-repo directory -> SystemExit with git_root")

        # Idempotency: call twice on real repo, same result
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            main_root = _container_form(tmp_path).resolve()
            subprocess.run(["git", "init", "--quiet", str(main_root)], check=True)
            got1 = _paths.resolve_main_worktree_root(main_root)
            got2 = _paths.resolve_main_worktree_root(main_root)
            assert got1 == got2, f"idempotency: got {got1} then {got2}"
        print("PASS: resolve_main_worktree_root idempotency (call twice, same result)")

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
        # Worktree-mode tests: patch _marker.slug_from_branch to raise MarkerError
        # (the caller's git_root is not a task-branch repo in these tests).
        # In-place tests: patch slug_from_branch to return slug + mock worktrees_dir.

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            wts_dir = tmp_path / "wts"
            wts_dir.mkdir()
            worktree = wts_dir / "my-task"
            _make_active_marker(worktree, branch="hanf/my-task")
            with patch("_marker.slug_from_branch", side_effect=_marker.MarkerError("not task")):
                got = _paths.resolve_active_worktree(
                    tmp_path, "my-task",
                    cfg={"spawn": {"branch_prefix": "hanf/"}},
                    git_root=tmp_path / "other-git-root",
                )
            assert got == worktree, f"happy path: got {got}"
        print("PASS: resolve_active_worktree happy path returns container_path/wts/slug")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "wts").mkdir()
            with patch("_marker.slug_from_branch", side_effect=_marker.MarkerError("not task")):
                try:
                    _paths.resolve_active_worktree(
                        tmp_path, "missing-slug",
                        cfg={},
                        git_root=tmp_path / "other",
                    )
                    raise AssertionError("expected ActiveWorktreeNotFound")
                except _paths.ActiveWorktreeNotFound:
                    pass
        print("PASS: resolve_active_worktree raises ActiveWorktreeNotFound when directory absent")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            wts_dir = tmp_path / "wts"
            wts_dir.mkdir()
            worktree = wts_dir / "my-task"
            # worktree dir named my-task but checked out on different-slug branch
            _make_active_marker(worktree, branch="hanf/different-slug")
            with patch("_marker.slug_from_branch", side_effect=_marker.MarkerError("not task")):
                try:
                    _paths.resolve_active_worktree(
                        tmp_path, "my-task",
                        cfg={"spawn": {"branch_prefix": "hanf/"}},
                        git_root=tmp_path / "other",
                    )
                    raise AssertionError("expected ActiveWorktreeSlugMismatch")
                except _paths.ActiveWorktreeSlugMismatch:
                    pass
        print("PASS: resolve_active_worktree raises ActiveWorktreeSlugMismatch when branch slug differs")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            wts_dir = tmp_path / "wts"
            wts_dir.mkdir()
            worktree = wts_dir / "my-task"
            _make_active_marker(worktree, branch="hanf/my-task")
            with patch("_marker.slug_from_branch", side_effect=_marker.MarkerError("not task")):
                got = _paths.resolve_active_worktree(
                    tmp_path, "my-task",
                    cfg={"spawn": {"branch_prefix": "hanf/"}},
                    git_root=tmp_path / "other-git-root",
                )
            assert got == worktree, f"M1 new sig: got {got}"
        print("PASS: resolve_active_worktree M1 (new sig) — container-form returns checkout root")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            wts_dir = tmp_path / "wts"
            wts_dir.mkdir()
            worktree = wts_dir / "my-task"
            _make_active_marker(worktree, branch="hanf/my-task")
            with patch("_marker.slug_from_branch", side_effect=_marker.MarkerError("not task")):
                got = _paths.resolve_active_worktree(
                    tmp_path, "my-task",
                    cfg={"spawn": {"branch_prefix": "hanf/"}, "hub_relative_path": "src/Models"},
                    git_root=tmp_path / "other-git-root",
                )
            assert got == worktree, f"M1+sub: got {got}"
        print("PASS: resolve_active_worktree M1+sub — sub-dir hub cfg still returns worktree root")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            git_root = tmp_path / "hub"
            git_root.mkdir()
            with patch("_paths.resolve_wiki_path", return_value=tmp_path / "wiki"), \
                 patch("_marker.slug_from_branch", return_value="my-task"), \
                 patch("_inplace.resolve_worktrees_dir", return_value=tmp_path / "wts-none"):
                got = _paths.resolve_active_worktree(
                    tmp_path, "my-task",
                    cfg={"hub_relative_path": "."},
                    git_root=git_root,
                )
            assert got == git_root, f"M2: got {got}"
        print("PASS: resolve_active_worktree M2 — in-place returns git_root")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            git_root = tmp_path / "hub"
            git_root.mkdir()
            with patch("_paths.resolve_wiki_path", return_value=tmp_path / "wiki"), \
                 patch("_marker.slug_from_branch", return_value="my-task"), \
                 patch("_inplace.resolve_worktrees_dir", return_value=tmp_path / "wts-none"):
                got = _paths.resolve_active_worktree(
                    tmp_path, "my-task",
                    cfg={"hub_relative_path": "src/Models"},
                    git_root=git_root,
                )
            assert got == git_root, f"M2+sub: got {got}"
        print("PASS: resolve_active_worktree M2+sub — in-place + sub-dir hub returns git_root")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            wts_dir = tmp_path / "wts"
            wts_dir.mkdir()
            worktree = wts_dir / "my-task"
            _make_active_marker(worktree, branch="hanf/different")
            with patch("_marker.slug_from_branch", side_effect=_marker.MarkerError("not task")):
                try:
                    _paths.resolve_active_worktree(
                        tmp_path, "my-task",
                        cfg={"spawn": {"branch_prefix": "hanf/"}},
                        git_root=tmp_path / "other",
                    )
                    raise AssertionError("expected ActiveWorktreeSlugMismatch")
                except _paths.ActiveWorktreeSlugMismatch:
                    pass
        print("PASS: resolve_active_worktree — worktree-dir slug mismatch raises ActiveWorktreeSlugMismatch")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "wts").mkdir()
            with patch("_marker.slug_from_branch", side_effect=_marker.MarkerError("not task")):
                try:
                    _paths.resolve_active_worktree(
                        tmp_path, "no-such-slug",
                        cfg={},
                        git_root=tmp_path / "other",
                    )
                    raise AssertionError("expected ActiveWorktreeNotFound")
                except _paths.ActiveWorktreeNotFound:
                    pass
        print("PASS: resolve_active_worktree — nothing exists raises ActiveWorktreeNotFound")

        # resolve_active_hub

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            wts_dir = tmp_path / "wts"
            wts_dir.mkdir()
            worktree = wts_dir / "my-task"
            _make_active_marker(worktree, branch="hanf/my-task")
            _write_stub(worktree / ".millhouse", ".")
            with patch("_marker.slug_from_branch", side_effect=_marker.MarkerError("not task")):
                got = _paths.resolve_active_hub(
                    tmp_path, "my-task",
                    cfg={"spawn": {"branch_prefix": "hanf/"}},
                    git_root=tmp_path / "other",
                )
            assert got == worktree, f"M1: got {got}"
        print("PASS: resolve_active_hub M1 — hub_relative_path=. returns worktree root")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            wts_dir = tmp_path / "wts"
            wts_dir.mkdir()
            worktree = wts_dir / "my-task"
            _make_active_marker(worktree, branch="hanf/my-task")
            _write_stub(worktree / ".millhouse", "src/Models")
            # cfg and stub agree
            with patch("_marker.slug_from_branch", side_effect=_marker.MarkerError("not task")):
                got = _paths.resolve_active_hub(
                    tmp_path, "my-task",
                    cfg={"spawn": {"branch_prefix": "hanf/"}, "hub_relative_path": "src/Models"},
                    git_root=tmp_path / "other",
                )
            assert got == worktree / "src" / "Models", f"M1+sub cfg+stub: got {got}"
            # stub overrides cfg when cfg says "."
            with patch("_marker.slug_from_branch", side_effect=_marker.MarkerError("not task")):
                got = _paths.resolve_active_hub(
                    tmp_path, "my-task",
                    cfg={"spawn": {"branch_prefix": "hanf/"}, "hub_relative_path": "."},
                    git_root=tmp_path / "other",
                )
            assert got == worktree / "src" / "Models", f"M1+sub stub override: got {got}"
        print("PASS: resolve_active_hub M1+sub — stub overrides caller cfg; both sources agree")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            git_root = tmp_path / "hub"
            git_root.mkdir()
            with patch("_paths.resolve_wiki_path", return_value=tmp_path / "wiki"), \
                 patch("_marker.slug_from_branch", return_value="my-task"), \
                 patch("_inplace.resolve_worktrees_dir", return_value=tmp_path / "wts-none"):
                got = _paths.resolve_active_hub(
                    tmp_path, "my-task",
                    cfg={"hub_relative_path": "."},
                    git_root=git_root,
                )
            assert got == git_root, f"M2: got {got}"
        print("PASS: resolve_active_hub M2 — in-place + hub_rel=. returns git_root")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            git_root = tmp_path / "hub"
            git_root.mkdir()
            with patch("_paths.resolve_wiki_path", return_value=tmp_path / "wiki"), \
                 patch("_marker.slug_from_branch", return_value="my-task"), \
                 patch("_inplace.resolve_worktrees_dir", return_value=tmp_path / "wts-none"):
                got = _paths.resolve_active_hub(
                    tmp_path, "my-task",
                    cfg={"hub_relative_path": "src/Models"},
                    git_root=git_root,
                )
            assert got == git_root / "src" / "Models", f"M2+sub: got {got}"
        print("PASS: resolve_active_hub M2+sub — in-place + sub-dir hub, cfg is authoritative")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "wts").mkdir()
            try:
                _paths.resolve_active_hub(
                    tmp_path, "no-such-slug",
                    cfg={"hub_relative_path": "."},
                    git_root=tmp_path / "other",
                )
                raise AssertionError("expected ActiveWorktreeNotFound")
            except _paths.ActiveWorktreeNotFound:
                pass
        print("PASS: resolve_active_hub — propagates ActiveWorktreeNotFound")

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

        # resolve_git_root wiki-cwd guards

        # Case 1: name check fires when resolved root name == "wiki"
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            wiki_dir = tmp_path / "wiki"
            wiki_dir.mkdir()
            with patch("_pygit2_util.discover_workdir", return_value=wiki_dir):
                try:
                    _paths.resolve_git_root()
                    raise AssertionError("expected SystemExit from name check, got none")
                except SystemExit as exc:
                    msg = str(exc)
                    assert "cwd is inside wiki" in msg, f"missing 'cwd is inside wiki': {msg!r}"
        print("PASS: resolve_git_root raises SystemExit when discovered path name == 'wiki'")

        # Case 2: path-equality guard fires when cwd equals wiki path (non-wiki name)
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp).resolve()
            with patch("_pygit2_util.discover_workdir", return_value=tmp_path), \
                 patch("_paths.resolve_wiki_path", return_value=tmp_path):
                try:
                    _paths.resolve_git_root()
                    raise AssertionError("expected SystemExit via path-equality, got none")
                except SystemExit:
                    pass
        print("PASS: resolve_git_root raises SystemExit via path-equality when cwd equals resolved wiki path")

        # Case 3: falls through when neither name nor equality matches
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp).resolve()
            other_path = tmp_path.parent / ("other_" + tmp_path.name)
            with patch("_pygit2_util.discover_workdir", return_value=tmp_path), \
                 patch("_paths.resolve_wiki_path", return_value=other_path):
                got = _paths.resolve_git_root()
            assert got == tmp_path, f"expected {tmp_path}, got {got}"
        print("PASS: resolve_git_root falls through when neither name nor equality matches")

        # Case 4: name check fires before nested-halt from resolve_wiki_path can propagate
        with patch("_paths.resolve_wiki_path", side_effect=SystemExit("nested-halt")):
            # Non-wiki sub-case: (Exception, SystemExit) swallow absorbs the inner halt
            with patch("_pygit2_util.discover_workdir", return_value=Path("/tmp/not-wiki")):
                got = _paths.resolve_git_root()
            assert got == Path("/tmp/not-wiki"), f"non-wiki sub-case: got {got}"
            # Wiki sub-case: name check fires first, nested halt cannot propagate
            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                wiki_dir = tmp_path / "wiki"
                wiki_dir.mkdir()
                with patch("_pygit2_util.discover_workdir", return_value=wiki_dir):
                    try:
                        _paths.resolve_git_root()
                        raise AssertionError("expected SystemExit from name check, got none")
                    except SystemExit as exc:
                        msg = str(exc)
                        assert "cwd is inside wiki" in msg, f"wrong message: {msg!r}"
                        assert "nested-halt" not in msg, f"inner halt leaked: {msg!r}"
        print("PASS: resolve_git_root name-check fires before nested-halt from resolve_wiki_path can propagate")

        # resolve_wiki_path wiki-cwd guards

        # Case 5: raises SystemExit when git_toplevel.name == "wiki"
        test_wiki_path = Path("/tmp/anything/wiki")
        try:
            _paths.resolve_wiki_path(test_wiki_path)
            raise AssertionError("expected SystemExit, got none")
        except SystemExit as exc:
            msg = str(exc)
            assert "cwd is inside wiki" in msg, f"missing 'cwd is inside wiki': {msg!r}"
            assert str(test_wiki_path) in msg, f"missing path: {msg!r}"
        print("PASS: resolve_wiki_path raises SystemExit when git_toplevel.name == 'wiki'")

        # Case 6: falls through (no exception) when git_toplevel.name != "wiki"
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            main_root = _container_form(tmp_path)
            with patch("_paths.resolve_main_worktree_root", return_value=main_root):
                got = _paths.resolve_wiki_path(main_root)
            assert isinstance(got, Path), f"expected Path, got {type(got)}"
        print("PASS: resolve_wiki_path falls through (no exception) when git_toplevel.name != 'wiki'")

        test_resolve_task_path()
        test_status_path()

        # Test resolve_git_root with start argument
        # Test 1: resolve_git_root(start) on a real git repo
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            # Initialize a real git repo
            subprocess.run(["git", "init", "--quiet", str(tmpdir)], check=True)
            result = _paths.resolve_git_root(tmpdir)
            assert isinstance(result, Path), f"expected Path, got {type(result)}"
            assert result == tmpdir.resolve(), f"expected {tmpdir.resolve()}, got {result}"
        print("PASS: resolve_git_root(start) returns correct path for real git repo")

        # Test 2: resolve_git_root with no args calls discover_workdir with None
        with patch("_pygit2_util.discover_workdir") as mock_discover:
            mock_discover.return_value = Path("/some/path").resolve()
            with patch("_paths.resolve_wiki_path", return_value=Path("/wiki")):
                try:
                    _paths.resolve_git_root()
                except SystemExit:
                    pass  # We expect this might fail due to wiki check, that's ok
                # Check that discover_workdir was called with None (no explicit start path)
                assert mock_discover.called, "discover_workdir should have been called"
                call_args = mock_discover.call_args_list[0][0]
                assert len(call_args) == 1, f"expected one arg, got {len(call_args)}"
                assert call_args[0] is None, f"expected None, got {call_args[0]}"
        print("PASS: resolve_git_root() with no args calls discover_workdir(None)")

        print("All _paths unit tests passed.")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
