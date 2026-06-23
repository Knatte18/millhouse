"""Unit tests for plugins/mill/scripts/_cleanliness.py."""
from __future__ import annotations

import io
import subprocess
import sys
import tempfile
import unittest.mock
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _cleanliness import (  # noqa: E402
    capture_snapshot,
    clean_ephemeral_scope_violations,
    compute_new_dirt,
    compute_scope_violations,
    compute_terminal_dirt,
    revert_out_of_scope_drift,
    _filter_to_task_scope,
    _parent_diff_names,
)


def main() -> int:
    failures: list[str] = []

    # 1. compute_new_dirt: empty pre + empty post -> []
    try:
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "snapshot.txt"
            snapshot_path.write_text("", encoding="utf-8")
            with unittest.mock.patch("_cleanliness._pygit2_util.status_porcelain", return_value=[]):
                result = compute_new_dirt(Path(tmp), snapshot_path)
            assert result == [], f"expected [], got {result!r}"
        print("PASS: empty pre + empty post -> []")
    except AssertionError as exc:
        failures.append(f"FAIL: empty pre + empty post: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: empty pre + empty post ({type(exc).__name__}): {exc}")

    # 2. compute_new_dirt: empty pre + dirty post -> all post lines sorted
    try:
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "snapshot.txt"
            snapshot_path.write_text("", encoding="utf-8")
            with unittest.mock.patch(
                "_cleanliness._pygit2_util.status_porcelain", return_value=[" M a.txt", " M b.txt"]
            ):
                result = compute_new_dirt(Path(tmp), snapshot_path)
            assert result == [" M a.txt", " M b.txt"], (
                f"expected sorted list, got {result!r}"
            )
        print("PASS: empty pre + dirty post -> all post lines sorted")
    except AssertionError as exc:
        failures.append(f"FAIL: empty pre + dirty post: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: empty pre + dirty post ({type(exc).__name__}): {exc}")

    # 3. compute_new_dirt: dirty pre + identical post -> [] (the original repro)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "snapshot.txt"
            snapshot_path.write_text(" M file.txt\n", encoding="utf-8")
            with unittest.mock.patch(
                "_cleanliness._pygit2_util.status_porcelain", return_value=[" M file.txt"]
            ):
                result = compute_new_dirt(Path(tmp), snapshot_path)
            assert result == [], f"expected [], got {result!r}"
        print("PASS: dirty pre + identical post -> [] (original repro)")
    except AssertionError as exc:
        failures.append(f"FAIL: dirty pre + identical post: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: dirty pre + identical post ({type(exc).__name__}): {exc}")

    # 4. compute_new_dirt: dirty pre + post is a strict superset -> only extra lines flagged
    try:
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "snapshot.txt"
            snapshot_path.write_text(" M a.txt\n", encoding="utf-8")
            with unittest.mock.patch(
                "_cleanliness._pygit2_util.status_porcelain", return_value=[" M a.txt", " M b.txt"]
            ):
                result = compute_new_dirt(Path(tmp), snapshot_path)
            assert result == [" M b.txt"], f"expected [' M b.txt'], got {result!r}"
        print("PASS: dirty pre + post is a strict superset -> only extra lines flagged")
    except AssertionError as exc:
        failures.append(f"FAIL: dirty pre + post superset: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: dirty pre + post superset ({type(exc).__name__}): {exc}")

    # 5. compute_new_dirt: dirty pre + post is a strict subset -> []
    try:
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "snapshot.txt"
            snapshot_path.write_text(" M a.txt\n M b.txt\n", encoding="utf-8")
            with unittest.mock.patch(
                "_cleanliness._pygit2_util.status_porcelain", return_value=[" M a.txt"]
            ):
                result = compute_new_dirt(Path(tmp), snapshot_path)
            assert result == [], f"expected [], got {result!r}"
        print("PASS: dirty pre + post is a strict subset -> []")
    except AssertionError as exc:
        failures.append(f"FAIL: dirty pre + post subset: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: dirty pre + post subset ({type(exc).__name__}): {exc}")

    # 6. compute_new_dirt: status-code change M -> MM flagged
    try:
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "snapshot.txt"
            snapshot_path.write_text(" M file.txt\n", encoding="utf-8")
            with unittest.mock.patch(
                "_cleanliness._pygit2_util.status_porcelain", return_value=["MM file.txt"]
            ):
                result = compute_new_dirt(Path(tmp), snapshot_path)
            assert result == ["MM file.txt"], f"expected ['MM file.txt'], got {result!r}"
        print("PASS: status-code change M -> MM flagged")
    except AssertionError as exc:
        failures.append(f"FAIL: status-code change: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: status-code change ({type(exc).__name__}): {exc}")

    # 7. compute_new_dirt: missing snapshot file -> returns post lines + [cleanliness] warning
    try:
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "missing.txt"
            with unittest.mock.patch(
                "_cleanliness._pygit2_util.status_porcelain", return_value=[" M a.txt"]
            ):
                with unittest.mock.patch("sys.stderr", new=io.StringIO()) as fake_err:
                    result = compute_new_dirt(Path(tmp), snapshot_path)
            assert result == [" M a.txt"], f"expected [' M a.txt'], got {result!r}"
            assert "[cleanliness]" in fake_err.getvalue(), (
                f"'[cleanliness]' not in stderr: {fake_err.getvalue()!r}"
            )
        print("PASS: missing snapshot file -> returns post lines + [cleanliness] warning to stderr")
    except AssertionError as exc:
        failures.append(f"FAIL: missing snapshot file: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: missing snapshot file ({type(exc).__name__}): {exc}")

    # 8. compute_new_dirt: CRLF in snapshot, LF in subprocess stdout -> no false-positive
    try:
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "snapshot.txt"
            snapshot_path.write_bytes(b" M file.txt\r\n")
            with unittest.mock.patch(
                "_cleanliness._pygit2_util.status_porcelain", return_value=[" M file.txt"]
            ):
                result = compute_new_dirt(Path(tmp), snapshot_path)
            assert result == [], f"expected [], got {result!r}"
        print("PASS: CRLF in snapshot, LF in subprocess stdout -> no false-positive new dirt")
    except AssertionError as exc:
        failures.append(f"FAIL: CRLF/LF normalization: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: CRLF/LF normalization ({type(exc).__name__}): {exc}")

    # 9. capture_snapshot: writes the exact git status --porcelain --untracked-files=no stdout
    try:
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "_mill" / ".cleanliness-snapshot-foo.txt"
            with unittest.mock.patch("_cleanliness._pygit2_util.status_porcelain", return_value=[" M file.txt"]):
                capture_snapshot(Path(tmp), snapshot_path)
            assert snapshot_path.exists(), "snapshot file not created"
            content = snapshot_path.read_text(encoding="utf-8")
            assert content == " M file.txt\n", f"content wrong: {content!r}"
        print("PASS: capture_snapshot writes exact git status stdout")
    except AssertionError as exc:
        failures.append(f"FAIL: capture_snapshot: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: capture_snapshot ({type(exc).__name__}): {exc}")

    # CV-1. compute_scope_violations: clean worktree returns []
    try:
        with tempfile.TemporaryDirectory() as tmp:
            with unittest.mock.patch("_cleanliness._pygit2_util.status_porcelain", return_value=[]):
                result = compute_scope_violations(Path(tmp))
            assert result == [], f"expected [], got {result!r}"
        print("PASS: compute_scope_violations: clean worktree -> []")
    except AssertionError as exc:
        failures.append(f"FAIL: compute_scope_violations clean: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: compute_scope_violations clean ({type(exc).__name__}): {exc}")

    # CV-2. compute_scope_violations: untracked file at root returned
    try:
        with tempfile.TemporaryDirectory() as tmp:
            with unittest.mock.patch("_cleanliness._pygit2_util.status_porcelain", return_value=["?? plugins/mill/scripts/foo.py"]):
                result = compute_scope_violations(Path(tmp))
            assert result == ["plugins/mill/scripts/foo.py"], f"expected ['plugins/mill/scripts/foo.py'], got {result!r}"
        print("PASS: compute_scope_violations: untracked at root -> path returned")
    except AssertionError as exc:
        failures.append(f"FAIL: compute_scope_violations untracked root: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: compute_scope_violations untracked root ({type(exc).__name__}): {exc}")

    # CV-3. compute_scope_violations: untracked file under _mill/ filtered out
    try:
        with tempfile.TemporaryDirectory() as tmp:
            with unittest.mock.patch("_cleanliness._pygit2_util.status_porcelain", return_value=["?? _mill/some-scratch.txt"]):
                result = compute_scope_violations(Path(tmp))
            assert result == [], f"expected [], got {result!r}"
        print("PASS: compute_scope_violations: untracked under _mill/ -> filtered")
    except AssertionError as exc:
        failures.append(f"FAIL: compute_scope_violations _mill filter: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: compute_scope_violations _mill filter ({type(exc).__name__}): {exc}")

    # CV-4. compute_scope_violations: untracked file in subdirectory outside _mill/ returned
    try:
        with tempfile.TemporaryDirectory() as tmp:
            with unittest.mock.patch("_cleanliness._pygit2_util.status_porcelain", return_value=["?? plugins/mill/scripts/new_file.py"]):
                result = compute_scope_violations(Path(tmp))
            assert result == ["plugins/mill/scripts/new_file.py"], f"expected ['plugins/mill/scripts/new_file.py'], got {result!r}"
        print("PASS: compute_scope_violations: untracked in subdir -> path returned")
    except AssertionError as exc:
        failures.append(f"FAIL: compute_scope_violations untracked subdir: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: compute_scope_violations untracked subdir ({type(exc).__name__}): {exc}")

    # CV-5. compute_scope_violations: junctions (.wiki, .portals, .active, .others) filtered
    try:
        with tempfile.TemporaryDirectory() as tmp:
            with unittest.mock.patch(
                "_cleanliness._pygit2_util.status_porcelain",
                return_value=["?? .wiki", "?? .portals", "?? .active", "?? .others", "?? bad_file.py"]
            ):
                result = compute_scope_violations(Path(tmp))
            assert result == ["bad_file.py"], f"expected ['bad_file.py'], got {result!r}"
        print("PASS: compute_scope_violations: junctions filtered, genuine file returned")
    except AssertionError as exc:
        failures.append(f"FAIL: compute_scope_violations junction filter: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: compute_scope_violations junction filter ({type(exc).__name__}): {exc}")

    # CV-6. compute_scope_violations: files under junction dirs filtered
    try:
        with tempfile.TemporaryDirectory() as tmp:
            with unittest.mock.patch(
                "_cleanliness._pygit2_util.status_porcelain",
                return_value=["?? .wiki/foo", "?? .portals/bar", "?? plugins/foo.py"]
            ):
                result = compute_scope_violations(Path(tmp))
            assert result == ["plugins/foo.py"], f"expected ['plugins/foo.py'], got {result!r}"
        print("PASS: compute_scope_violations: files under junctions filtered")
    except AssertionError as exc:
        failures.append(f"FAIL: compute_scope_violations files under junctions: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: compute_scope_violations files under junctions ({type(exc).__name__}): {exc}")

    # TD-1. _filter_to_task_scope: in-scope file under task_dir is included
    try:
        porcelain = [" M _mill/status.md", " M other_file.txt"]
        task_dir = Path("_mill")
        owned_paths = set()
        result = _filter_to_task_scope(porcelain, task_dir, owned_paths)
        assert result == [" M _mill/status.md"], f"expected [' M _mill/status.md'], got {result!r}"
        print("PASS: _filter_to_task_scope: file under task_dir included")
    except AssertionError as exc:
        failures.append(f"FAIL: _filter_to_task_scope under task_dir: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: _filter_to_task_scope under task_dir ({type(exc).__name__}): {exc}")

    # TD-2. _filter_to_task_scope: in-scope file in owned_paths is included
    try:
        porcelain = [" M src/main.py", " M other.py"]
        task_dir = Path("_mill")
        owned_paths = {"src/main.py"}
        result = _filter_to_task_scope(porcelain, task_dir, owned_paths)
        assert result == [" M src/main.py"], f"expected [' M src/main.py'], got {result!r}"
        print("PASS: _filter_to_task_scope: file in owned_paths included")
    except AssertionError as exc:
        failures.append(f"FAIL: _filter_to_task_scope owned_paths: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: _filter_to_task_scope owned_paths ({type(exc).__name__}): {exc}")

    # TD-3. _filter_to_task_scope: out-of-scope file excluded
    try:
        porcelain = [" M _mill/status.md", " M plugins/foo.py"]
        task_dir = Path("_mill")
        owned_paths = set()
        result = _filter_to_task_scope(porcelain, task_dir, owned_paths)
        assert result == [" M _mill/status.md"], f"expected [' M _mill/status.md'], got {result!r}"
        print("PASS: _filter_to_task_scope: out-of-scope file excluded")
    except AssertionError as exc:
        failures.append(f"FAIL: _filter_to_task_scope out-of-scope: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: _filter_to_task_scope out-of-scope ({type(exc).__name__}): {exc}")

    # TD-4. _filter_to_task_scope: empty porcelain returns empty
    try:
        porcelain = []
        task_dir = Path("_mill")
        owned_paths = {"some/file.py"}
        result = _filter_to_task_scope(porcelain, task_dir, owned_paths)
        assert result == [], f"expected [], got {result!r}"
        print("PASS: _filter_to_task_scope: empty porcelain -> []")
    except AssertionError as exc:
        failures.append(f"FAIL: _filter_to_task_scope empty: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: _filter_to_task_scope empty ({type(exc).__name__}): {exc}")

    # CTD-1. compute_terminal_dirt: clean worktree returns []
    try:
        with tempfile.TemporaryDirectory() as tmp:
            with unittest.mock.patch("_cleanliness._pygit2_util.status_porcelain", return_value=[]):
                with unittest.mock.patch("_cleanliness._parent_diff_names", return_value=[]):
                    result = compute_terminal_dirt(Path(tmp), Path("_mill"), "main")
            assert result == [], f"expected [], got {result!r}"
        print("PASS: compute_terminal_dirt: clean worktree -> []")
    except AssertionError as exc:
        failures.append(f"FAIL: compute_terminal_dirt clean: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: compute_terminal_dirt clean ({type(exc).__name__}): {exc}")

    # CTD-2. compute_terminal_dirt: in-scope dirt (file under task_dir) is returned
    try:
        with tempfile.TemporaryDirectory() as tmp:
            with unittest.mock.patch(
                "_cleanliness._pygit2_util.status_porcelain",
                return_value=[" M _mill/status.md", " M other.txt"]
            ):
                with unittest.mock.patch("_cleanliness._parent_diff_names", return_value=[]):
                    result = compute_terminal_dirt(Path(tmp), Path("_mill"), "main")
            assert result == [" M _mill/status.md"], f"expected [' M _mill/status.md'], got {result!r}"
        print("PASS: compute_terminal_dirt: in-scope file under task_dir returned")
    except AssertionError as exc:
        failures.append(f"FAIL: compute_terminal_dirt in-scope under task_dir: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: compute_terminal_dirt in-scope under task_dir ({type(exc).__name__}): {exc}")

    # CTD-3. compute_terminal_dirt: in-scope dirt (file in parent-diff set) is returned
    try:
        with tempfile.TemporaryDirectory() as tmp:
            with unittest.mock.patch(
                "_cleanliness._pygit2_util.status_porcelain",
                return_value=[" M src/main.py", " M other.txt"]
            ):
                with unittest.mock.patch("_cleanliness._parent_diff_names", return_value=["src/main.py"]):
                    result = compute_terminal_dirt(Path(tmp), Path("_mill"), "main")
            assert result == [" M src/main.py"], f"expected [' M src/main.py'], got {result!r}"
        print("PASS: compute_terminal_dirt: in-scope file in parent-diff set returned")
    except AssertionError as exc:
        failures.append(f"FAIL: compute_terminal_dirt in-scope parent-diff: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: compute_terminal_dirt in-scope parent-diff ({type(exc).__name__}): {exc}")

    # CTD-4. compute_terminal_dirt: out-of-scope dirt (another task's _mill/) is ignored
    try:
        with tempfile.TemporaryDirectory() as tmp:
            with unittest.mock.patch(
                "_cleanliness._pygit2_util.status_porcelain",
                return_value=[" M _mill/status.md", " M other_task/_mill/status.md"]
            ):
                with unittest.mock.patch("_cleanliness._parent_diff_names", return_value=[]):
                    result = compute_terminal_dirt(Path(tmp), Path("_mill"), "main")
            assert result == [" M _mill/status.md"], f"expected [' M _mill/status.md'], got {result!r}"
        print("PASS: compute_terminal_dirt: out-of-scope another task's _mill/ ignored")
    except AssertionError as exc:
        failures.append(f"FAIL: compute_terminal_dirt out-of-scope: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: compute_terminal_dirt out-of-scope ({type(exc).__name__}): {exc}")

    # CTD-5. compute_terminal_dirt: absolute task_dir is relativized and still matches
    try:
        with tempfile.TemporaryDirectory() as tmp:
            worktree = Path(tmp)
            # Simulate mill-go's task_dir = status_path.parent (absolute)
            abs_task_dir = worktree / "_mill"
            with unittest.mock.patch(
                "_cleanliness._pygit2_util.status_porcelain",
                return_value=[" M _mill/status.md", " M other.txt"]
            ):
                with unittest.mock.patch("_cleanliness._parent_diff_names", return_value=[]):
                    result = compute_terminal_dirt(worktree, abs_task_dir, "main")
            assert result == [" M _mill/status.md"], (
                f"expected [' M _mill/status.md'] with absolute task_dir, got {result!r}"
            )
        print("PASS: compute_terminal_dirt: absolute task_dir relativized correctly")
    except AssertionError as exc:
        failures.append(f"FAIL: compute_terminal_dirt absolute task_dir: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: compute_terminal_dirt absolute task_dir ({type(exc).__name__}): {exc}")

    # PDN-1. _parent_diff_names: non-zero git exit emits stderr warning and returns []
    try:
        with tempfile.TemporaryDirectory() as tmp:
            with unittest.mock.patch(
                "_cleanliness._subprocess_util.run",
                return_value=unittest.mock.Mock(returncode=128, stdout="", stderr="fatal: bad revision"),
            ):
                with unittest.mock.patch("sys.stderr", new=io.StringIO()) as fake_err:
                    result = _parent_diff_names(Path(tmp), "nonexistent-branch")
            assert result == [], f"expected [], got {result!r}"
            assert "[cleanliness]" in fake_err.getvalue(), (
                f"'[cleanliness]' not in stderr: {fake_err.getvalue()!r}"
            )
        print("PASS: _parent_diff_names: non-zero exit -> [] + stderr warning")
    except AssertionError as exc:
        failures.append(f"FAIL: _parent_diff_names non-zero exit: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: _parent_diff_names non-zero exit ({type(exc).__name__}): {exc}")

    # ROOD-1. revert_out_of_scope_drift: out-of-scope tracked modification only -> reverted, remaining empty
    try:
        with tempfile.TemporaryDirectory() as tmp:
            with unittest.mock.patch(
                "_cleanliness._pygit2_util.status_porcelain",
                return_value=[" M out_of_scope.txt"]
            ):
                with unittest.mock.patch("_cleanliness._parent_diff_names", return_value=[]):
                    with unittest.mock.patch("_cleanliness._subprocess_util.run") as mock_run:
                        mock_run.return_value = unittest.mock.Mock(returncode=0)
                        reverted, remaining = revert_out_of_scope_drift(Path(tmp), Path("_mill"), "main")
            assert reverted == ["out_of_scope.txt"], f"expected ['out_of_scope.txt'], got {reverted!r}"
            assert remaining == [], f"expected [], got {remaining!r}"
            # Verify git checkout was called
            assert mock_run.call_count == 1, f"expected 1 call to run, got {mock_run.call_count}"
            call_args = mock_run.call_args[0][0]
            assert call_args[0:3] == ["git", "checkout", "HEAD"], f"unexpected git call: {call_args}"
        print("PASS: revert_out_of_scope_drift: out-of-scope modification reverted, remaining empty")
    except AssertionError as exc:
        failures.append(f"FAIL: revert_out_of_scope_drift out-of-scope only: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: revert_out_of_scope_drift out-of-scope only ({type(exc).__name__}): {exc}")

    # ROOD-2. revert_out_of_scope_drift: mixed in-scope + out-of-scope -> out-of-scope reverted, in-scope returned
    try:
        with tempfile.TemporaryDirectory() as tmp:
            with unittest.mock.patch(
                "_cleanliness._pygit2_util.status_porcelain",
                return_value=[" M _mill/status.md", " M out_of_scope.txt"]
            ):
                with unittest.mock.patch("_cleanliness._parent_diff_names", return_value=[]):
                    with unittest.mock.patch("_cleanliness._subprocess_util.run") as mock_run:
                        mock_run.return_value = unittest.mock.Mock(returncode=0)
                        reverted, remaining = revert_out_of_scope_drift(Path(tmp), Path("_mill"), "main")
            assert reverted == ["out_of_scope.txt"], f"expected ['out_of_scope.txt'], got {reverted!r}"
            assert remaining == [" M _mill/status.md"], f"expected [' M _mill/status.md'], got {remaining!r}"
        print("PASS: revert_out_of_scope_drift: mixed in-scope + out-of-scope -> out-of-scope reverted")
    except AssertionError as exc:
        failures.append(f"FAIL: revert_out_of_scope_drift mixed: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: revert_out_of_scope_drift mixed ({type(exc).__name__}): {exc}")

    # ROOD-3. revert_out_of_scope_drift: deleted-in-index out-of-scope file NOT reverted (not a modified status code)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            with unittest.mock.patch(
                "_cleanliness._pygit2_util.status_porcelain",
                return_value=[" D out_of_scope.txt"]
            ):
                with unittest.mock.patch("_cleanliness._parent_diff_names", return_value=[]):
                    with unittest.mock.patch("_cleanliness._subprocess_util.run") as mock_run:
                        reverted, remaining = revert_out_of_scope_drift(Path(tmp), Path("_mill"), "main")
            assert reverted == [], f"expected [], got {reverted!r}"
            assert remaining == [], f"expected [], got {remaining!r}"
            # Verify git checkout was NOT called (file is deleted in index, not modified)
            assert mock_run.call_count == 0, f"expected 0 calls to run, got {mock_run.call_count}"
        print("PASS: revert_out_of_scope_drift: deleted-in-index file NOT reverted and NOT returned")
    except AssertionError as exc:
        failures.append(f"FAIL: revert_out_of_scope_drift untracked: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: revert_out_of_scope_drift untracked ({type(exc).__name__}): {exc}")

    # ROOD-4. revert_out_of_scope_drift: file in parent-diff owned set but outside task_dir is in-scope
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # Create a git repo with parent branch as base
            subprocess.run(
                ["git", "init", "-b", "parent", str(tmp_path)],
                check=True,
                capture_output=True,
            )
            # Configure git user
            subprocess.run(
                ["git", "-C", str(tmp_path), "config", "user.email", "test@test.com"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(tmp_path), "config", "user.name", "Test User"],
                check=True,
                capture_output=True,
            )
            # Create initial commit on parent branch
            (tmp_path / "src").mkdir(parents=True, exist_ok=True)
            (tmp_path / "src" / "main.py").write_text("def hello(): pass", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(tmp_path), "add", "src/main.py"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(tmp_path), "commit", "-m", "initial"],
                check=True,
                capture_output=True,
            )
            # Create task branch from parent
            subprocess.run(
                ["git", "-C", str(tmp_path), "checkout", "-b", "task"],
                check=True,
                capture_output=True,
            )
            # Modify src/main.py on task branch (this creates a parent-diff)
            (tmp_path / "src" / "main.py").write_text("def hello(): return 1", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(tmp_path), "add", "src/main.py"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(tmp_path), "commit", "-m", "modify src/main.py on task"],
                check=True,
                capture_output=True,
            )
            # Modify src/main.py again in working tree (simulating formatter drift)
            (tmp_path / "src" / "main.py").write_text("def hello(): return 2", encoding="utf-8")
            # Create _mill directory (task_dir)
            (tmp_path / "_mill").mkdir(parents=True, exist_ok=True)
            (tmp_path / "_mill" / "status.md").write_text("# Status", encoding="utf-8")
            # Now test revert_out_of_scope_drift
            reverted, remaining = revert_out_of_scope_drift(tmp_path, Path("_mill"), "parent")
            # src/main.py is in the parent-diff owned set, so it should NOT be reverted
            assert reverted == [], f"expected [], got {reverted!r}"
            # It should be in remaining since it is in-scope (part of owned set)
            assert len(remaining) == 1, f"expected 1 remaining line, got {len(remaining)}"
            assert "src/main.py" in remaining[0], f"expected 'src/main.py' in remaining, got {remaining!r}"
        print("PASS: revert_out_of_scope_drift: owned-set file treated as in-scope")
    except AssertionError as exc:
        failures.append(f"FAIL: revert_out_of_scope_drift owned-set: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: revert_out_of_scope_drift owned-set ({type(exc).__name__}): {exc}")

    # CESV-1. clean_ephemeral_scope_violations: allowlisted coverage.out is removed and reported
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # Create a git repo
            subprocess.run(
                ["git", "init", str(tmp_path)],
                check=True,
                capture_output=True,
            )
            # Create coverage.out as untracked (simulate a -cover run)
            coverage_file = tmp_path / "coverage.out"
            coverage_file.write_text("mode: set", encoding="utf-8")
            # Mock compute_scope_violations to return the coverage file
            with unittest.mock.patch(
                "_cleanliness.compute_scope_violations",
                return_value=["coverage.out"]
            ):
                removed, blocking = clean_ephemeral_scope_violations(tmp_path)
            # coverage.out should be removed and reported
            assert removed == ["coverage.out"], f"expected ['coverage.out'] in removed, got {removed!r}"
            assert blocking == [], f"expected [] in blocking, got {blocking!r}"
            # File should be deleted from disk
            assert not coverage_file.exists(), "coverage.out should have been deleted"
        print("PASS: clean_ephemeral_scope_violations: coverage.out allowlisted and removed")
    except AssertionError as exc:
        failures.append(f"FAIL: clean_ephemeral_scope_violations coverage.out: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: clean_ephemeral_scope_violations coverage.out ({type(exc).__name__}): {exc}")

    # CESV-2. clean_ephemeral_scope_violations: allowlisted .test.exe suffix is removed and reported
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            subprocess.run(
                ["git", "init", str(tmp_path)],
                check=True,
                capture_output=True,
            )
            # Create foo.test.exe as untracked
            test_file = tmp_path / "foo.test.exe"
            test_file.write_text("", encoding="utf-8")
            with unittest.mock.patch(
                "_cleanliness.compute_scope_violations",
                return_value=["foo.test.exe"]
            ):
                removed, blocking = clean_ephemeral_scope_violations(tmp_path)
            assert removed == ["foo.test.exe"], f"expected ['foo.test.exe'] in removed, got {removed!r}"
            assert blocking == [], f"expected [] in blocking, got {blocking!r}"
            assert not test_file.exists(), "foo.test.exe should have been deleted"
        print("PASS: clean_ephemeral_scope_violations: .test.exe suffix allowlisted and removed")
    except AssertionError as exc:
        failures.append(f"FAIL: clean_ephemeral_scope_violations .test.exe: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: clean_ephemeral_scope_violations .test.exe ({type(exc).__name__}): {exc}")

    # CESV-3. clean_ephemeral_scope_violations: non-allowlisted file is NOT removed and reported as blocking
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            subprocess.run(
                ["git", "init", str(tmp_path)],
                check=True,
                capture_output=True,
            )
            # Create notes.txt as untracked (non-allowlisted)
            notes_file = tmp_path / "notes.txt"
            notes_file.write_text("some notes", encoding="utf-8")
            with unittest.mock.patch(
                "_cleanliness.compute_scope_violations",
                return_value=["notes.txt"]
            ):
                removed, blocking = clean_ephemeral_scope_violations(tmp_path)
            assert removed == [], f"expected [] in removed, got {removed!r}"
            assert blocking == ["notes.txt"], f"expected ['notes.txt'] in blocking, got {blocking!r}"
            # File should NOT be deleted from disk
            assert notes_file.exists(), "notes.txt should NOT have been deleted"
        print("PASS: clean_ephemeral_scope_violations: non-allowlisted file NOT removed, reported as blocking")
    except AssertionError as exc:
        failures.append(f"FAIL: clean_ephemeral_scope_violations non-allowlisted: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: clean_ephemeral_scope_violations non-allowlisted ({type(exc).__name__}): {exc}")

    # CESV-4. clean_ephemeral_scope_violations: in-scope _mill/ files are neither removed nor reported
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            subprocess.run(
                ["git", "init", str(tmp_path)],
                check=True,
                capture_output=True,
            )
            # Create a file under _mill/ (in-scope, filtered by compute_scope_violations)
            (tmp_path / "_mill").mkdir(parents=True, exist_ok=True)
            mill_file = tmp_path / "_mill" / "scratch.txt"
            mill_file.write_text("", encoding="utf-8")
            with unittest.mock.patch(
                "_cleanliness.compute_scope_violations",
                return_value=[]  # _mill/ files already filtered by compute_scope_violations
            ):
                removed, blocking = clean_ephemeral_scope_violations(tmp_path)
            assert removed == [], f"expected [] in removed, got {removed!r}"
            assert blocking == [], f"expected [] in blocking, got {blocking!r}"
        print("PASS: clean_ephemeral_scope_violations: in-scope _mill/ files neither removed nor reported")
    except AssertionError as exc:
        failures.append(f"FAIL: clean_ephemeral_scope_violations in-scope: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: clean_ephemeral_scope_violations in-scope ({type(exc).__name__}): {exc}")

    # CESV-5. clean_ephemeral_scope_violations: already-gone allowlisted file is still reported as removed
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            subprocess.run(
                ["git", "init", str(tmp_path)],
                check=True,
                capture_output=True,
            )
            # Don't actually create the file, just mock compute_scope_violations
            with unittest.mock.patch(
                "_cleanliness.compute_scope_violations",
                return_value=["coverage.out"]  # File doesn't exist on disk
            ):
                removed, blocking = clean_ephemeral_scope_violations(tmp_path)
            # Should still be reported as removed (swallow FileNotFoundError)
            assert removed == ["coverage.out"], f"expected ['coverage.out'] in removed, got {removed!r}"
            assert blocking == [], f"expected [] in blocking, got {blocking!r}"
        print("PASS: clean_ephemeral_scope_violations: already-gone file swallowed and reported as removed")
    except AssertionError as exc:
        failures.append(f"FAIL: clean_ephemeral_scope_violations already-gone: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: clean_ephemeral_scope_violations already-gone ({type(exc).__name__}): {exc}")

    if failures:
        for msg in failures:
            print(msg, file=sys.stderr)
        return 1

    print("All _cleanliness unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
