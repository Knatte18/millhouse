"""Unit tests for plugins/codeguide/scripts/resolve_scope.py."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "codeguide" / "scripts"))

from resolve_scope import enumerate_scope  # noqa: E402


def _make_repo(tmp: Path, *, with_origin: bool, default_branch: str = "main", set_remote_head: bool = True) -> None:
    subprocess.run(["git", "-C", str(tmp), "init", "-b", default_branch], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp), "config", "user.email", "test@test.com"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp), "config", "user.name", "Test"], check=True, capture_output=True)
    if with_origin:
        origin = tmp / "origin.git"
        subprocess.run(["git", "init", "--bare", str(origin)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(tmp), "remote", "add", "origin", str(origin)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(tmp), "fetch", "origin"], capture_output=True)
        if set_remote_head:
            subprocess.run(
                ["git", "-C", str(tmp), "symbolic-ref",
                 "refs/remotes/origin/HEAD",
                 f"refs/remotes/origin/{default_branch}"],
                check=True, capture_output=True,
            )


def _commit(tmp: Path, files: dict[str, str], msg: str) -> str:
    for name, content in files.items():
        p = tmp / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp), "add"] + list(files.keys()), check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp), "commit", "-m", msg], check=True, capture_output=True)
    result = subprocess.run(
        ["git", "-C", str(tmp), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    )
    return result.stdout.strip()


def main() -> int:
    try:
        # Scenario 1: no-arg on main, clean tree
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            _make_repo(tmp, with_origin=True)
            _commit(tmp, {"a.py": "x"}, "init")
            paths, summary = enumerate_scope([], cwd=tmp)
            assert paths == [], f"expected [], got {paths}"
            assert summary["parent"] is None, f"expected parent=None, got {summary['parent']}"
            assert summary["base_branch"] == "main", f"expected base_branch=main, got {summary['base_branch']}"
            print("PASS: no-arg on main clean tree -> empty scope, parent=None, base_branch=main")

        # Scenario 2: no-arg on main, dirty tree
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            _make_repo(tmp, with_origin=True)
            _commit(tmp, {"a.py": "x", "b.py": "y"}, "init")
            (tmp / "a.py").write_text("modified", encoding="utf-8")
            (tmp / "b.py").write_text("modified", encoding="utf-8")
            subprocess.run(["git", "-C", str(tmp), "add", "b.py"], check=True, capture_output=True)
            paths, summary = enumerate_scope([], cwd=tmp)
            path_names = {p.name for p in paths}
            assert "a.py" in path_names and "b.py" in path_names, f"expected a.py and b.py in {path_names}"
            assert summary["parent"] is None, f"expected parent=None, got {summary['parent']}"
            print("PASS: no-arg on main dirty tree -> unstaged+staged files, parent=None")

        # Scenario 3: no-arg on task branch, clean tree
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            _make_repo(tmp, with_origin=True)
            _commit(tmp, {"init.py": "x"}, "init on main")
            subprocess.run(["git", "-C", str(tmp), "checkout", "-b", "feature"], check=True, capture_output=True)
            _commit(tmp, {"a.py": "x"}, "commit A")
            _commit(tmp, {"b.py": "y"}, "commit B")
            paths, summary = enumerate_scope([], cwd=tmp)
            path_names = {p.name for p in paths}
            assert path_names == {"a.py", "b.py"}, f"expected {{a.py, b.py}}, got {path_names}"
            assert summary["parent"] == "main", f"expected parent=main, got {summary['parent']}"
            assert summary["included_committed"] == 2, f"expected included_committed=2, got {summary['included_committed']}"
            assert summary["included_diff"] == 0, f"expected included_diff=0, got {summary['included_diff']}"
            print("PASS: no-arg on task branch clean tree -> committed files, parent=main, included_committed=2")

        # Scenario 4: no-arg on task branch, dirty tree
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            _make_repo(tmp, with_origin=True)
            _commit(tmp, {"init.py": "x", "c.py": "c_orig"}, "init on main")
            subprocess.run(["git", "-C", str(tmp), "checkout", "-b", "feature"], check=True, capture_output=True)
            _commit(tmp, {"a.py": "x"}, "commit A")
            _commit(tmp, {"b.py": "y"}, "commit B")
            (tmp / "c.py").write_text("c_modified", encoding="utf-8")
            paths, summary = enumerate_scope([], cwd=tmp)
            path_names = {p.name for p in paths}
            assert "a.py" in path_names and "b.py" in path_names and "c.py" in path_names, \
                f"expected a.py, b.py, c.py in {path_names}"
            assert summary["included_diff"] >= 1, f"expected included_diff>=1, got {summary['included_diff']}"
            print("PASS: no-arg on task branch dirty tree -> committed + unstaged files deduped")

        # Scenario 5: no-arg, task branch, no origin/HEAD, has origin/main
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            _make_repo(tmp, with_origin=True, set_remote_head=False)
            _commit(tmp, {"init.py": "x"}, "init on main")
            subprocess.run(["git", "-C", str(tmp), "push", "origin", "main"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(tmp), "checkout", "-b", "feature"], check=True, capture_output=True)
            _commit(tmp, {"a.py": "x"}, "commit on feature")
            paths, summary = enumerate_scope([], cwd=tmp)
            assert summary["base_branch"] == "main", f"expected base_branch=main, got {summary['base_branch']}"
            print("PASS: no origin/HEAD falls through to origin/main probe -> base_branch=main")

        # Scenario 6: no-arg, task branch, no origin/HEAD, no origin/main, has origin/master
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            _make_repo(tmp, with_origin=True, default_branch="master", set_remote_head=False)
            _commit(tmp, {"init.py": "x"}, "init on master")
            subprocess.run(["git", "-C", str(tmp), "push", "origin", "master"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(tmp), "checkout", "-b", "feature"], check=True, capture_output=True)
            _commit(tmp, {"a.py": "x"}, "commit on feature")
            paths, summary = enumerate_scope([], cwd=tmp)
            assert summary["base_branch"] == "master", f"expected base_branch=master, got {summary['base_branch']}"
            print("PASS: no origin/HEAD, no origin/main -> falls through to origin/master -> base_branch=master")

        # Scenario 7: no-arg, task branch, no remote at all
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            _make_repo(tmp, with_origin=False)
            _commit(tmp, {"init.py": "x"}, "init on main")
            subprocess.run(["git", "-C", str(tmp), "checkout", "-b", "feature"], check=True, capture_output=True)
            _commit(tmp, {"a.py": "x"}, "commit on feature")
            paths, summary = enumerate_scope([], cwd=tmp)
            assert paths == [], f"expected [], got {paths}"
            assert summary["parent"] is None, f"expected parent=None, got {summary['parent']}"
            assert summary["base_branch"] is None, f"expected base_branch=None, got {summary['base_branch']}"
            print("PASS: no remote -> graceful degradation, empty scope, parent=None, base_branch=None")

        # Scenario 8: HEAD-rev arg HEAD~3
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            _make_repo(tmp, with_origin=False)
            _commit(tmp, {"base.py": "base"}, "base commit")
            _commit(tmp, {"b.py": "b"}, "commit 2")
            _commit(tmp, {"c.py": "c"}, "commit 3")
            _commit(tmp, {"d.py": "d"}, "commit 4")
            paths, summary = enumerate_scope(["HEAD~3"], cwd=tmp)
            path_names = {p.name for p in paths}
            assert path_names == {"b.py", "c.py", "d.py"}, f"expected {{b.py, c.py, d.py}}, got {path_names}"
            assert summary["mode"] == "head-rev", f"expected mode=head-rev, got {summary['mode']}"
            print("PASS: HEAD~3 arg returns files from last 3 commits")

        # Scenario 9: time arg 1h
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            _make_repo(tmp, with_origin=False)
            _commit(tmp, {"recent.py": "x"}, "recent commit")
            paths, summary = enumerate_scope(["1h"], cwd=tmp)
            path_names = {p.name for p in paths}
            assert "recent.py" in path_names, f"expected recent.py in {path_names}"
            assert summary["mode"] == "time", f"expected mode=time, got {summary['mode']}"
            print("PASS: time arg 1h includes just-made commit's files")

        # Scenario 10: explicit paths (valid and nonexistent)
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            _make_repo(tmp, with_origin=False)
            _commit(tmp, {"a.py": "x"}, "init")
            paths, summary = enumerate_scope(["a.py", "nonexistent.py"], cwd=tmp)
            path_names = {p.name for p in paths}
            assert "a.py" in path_names, f"expected a.py in {path_names}"
            assert "nonexistent.py" in path_names, f"expected nonexistent.py in {path_names}"
            assert summary["mode"] == "explicit", f"expected mode=explicit, got {summary['mode']}"
            nonexistent = [p for p in paths if p.name == "nonexistent.py"][0]
            assert not nonexistent.exists(), "nonexistent.py should not exist on disk"
            print("PASS: explicit paths returns absolute paths without existence check")

        # Scenario 11: files deleted in parent..HEAD still appear in scope
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            _make_repo(tmp, with_origin=True)
            _commit(tmp, {"init.py": "x", "a.py": "orig"}, "init on main")
            subprocess.run(["git", "-C", str(tmp), "checkout", "-b", "feature"], check=True, capture_output=True)
            _commit(tmp, {"b.py": "y"}, "commit B")
            subprocess.run(["git", "-C", str(tmp), "rm", "a.py"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(tmp), "commit", "-m", "delete a.py"], check=True, capture_output=True)
            paths, summary = enumerate_scope([], cwd=tmp)
            path_names = {p.name for p in paths}
            assert "a.py" in path_names, f"expected deleted a.py in {path_names}"
            a_paths = [p for p in paths if p.name == "a.py"]
            assert len(a_paths) == 1 and not a_paths[0].exists(), \
                "a.py should appear exactly once and not exist on disk"
            print("PASS: deleted files in parent..HEAD still appear in scope")

        # Scenario 12: branch == base where base is master
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            _make_repo(tmp, with_origin=True, default_branch="master")
            _commit(tmp, {"init.py": "x"}, "init on master")
            paths, summary = enumerate_scope([], cwd=tmp)
            assert paths == [], f"expected [], got {paths}"
            assert summary["base_branch"] == "master", f"expected base_branch=master, got {summary['base_branch']}"
            print("PASS: branch == base (master) on clean tree -> empty scope")

        # Scenario 13: file in both parent..HEAD and current diff appears once
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            _make_repo(tmp, with_origin=True)
            _commit(tmp, {"init.py": "x", "a.py": "orig", "b.py": "orig"}, "init on main")
            subprocess.run(["git", "-C", str(tmp), "checkout", "-b", "feature"], check=True, capture_output=True)
            _commit(tmp, {"a.py": "committed_mod", "b.py": "committed_mod"}, "commit A and B")
            (tmp / "a.py").write_text("unstaged_mod", encoding="utf-8")
            paths, summary = enumerate_scope([], cwd=tmp)
            path_names = {p.name for p in paths}
            assert "a.py" in path_names, f"expected a.py in {path_names}"
            a_count = sum(1 for p in paths if p.name == "a.py")
            assert a_count == 1, f"a.py should appear exactly once, got {a_count}"
            assert summary["included_committed"] >= 1, f"expected included_committed>=1, got {summary['included_committed']}"
            assert summary["included_diff"] >= 1, f"expected included_diff>=1, got {summary['included_diff']}"
            print("PASS: file in both committed range and diff appears only once in deduped output")

        print("All resolve_scope unit tests passed.")
        return 0

    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
