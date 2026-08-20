"""Unit tests for plugins/mill/scripts/_worktree.py."""
from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _safe_rmtree  # noqa: E402, F401
from _worktree import (  # noqa: E402
    WorktreeError,
    WorktreeLockedError,
    copy_millhouse,
    create,
    list_worktrees,
    move,
    remove,
    remove_safe,
    processes_holding_path,
    kill_stale_holders,
)


def _git_init(path: Path) -> None:
    """Initialise a real git repo with an empty initial commit."""
    subprocess.run(["git", "init", "-b", "main", str(path)], check=False, capture_output=True)
    # Fallback for Git < 2.28 which does not support -b
    subprocess.run(
        ["git", "-C", str(path), "symbolic-ref", "HEAD", "refs/heads/main"],
        check=False, capture_output=True,
    )
    subprocess.run(["git", "-C", str(path), "config", "user.email", "test@test.com"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Test"], check=True, capture_output=True)
    (path / ".keep").write_text("", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", ".keep"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "commit", "-m", "init"], check=True, capture_output=True)


def main() -> int:
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            src = tmp_path / ".millhouse"
            src.mkdir()
            (src / "keep").mkdir()
            (src / "keep" / "file.txt").write_text("hello", encoding="utf-8")
            (src / "wiki").mkdir()
            (src / "wiki" / "decoy.txt").write_text("wiki-alias", encoding="utf-8")
            (src / "active").mkdir()
            (src / "active" / "decoy.txt").write_text("active-alias", encoding="utf-8")
            (src / "plainfile.txt").write_text("top-level", encoding="utf-8")

            dst = tmp_path / "worktree" / ".millhouse"
            copy_millhouse(src, dst, exclude={"wiki", "active"})

            assert (dst / "keep" / "file.txt").read_text(encoding="utf-8") == "hello"
            assert (dst / "plainfile.txt").read_text(encoding="utf-8") == "top-level"
            assert not (dst / "wiki").exists(), "wiki junction alias must not be copied"
            assert not (dst / "active").exists(), "active junction alias must not be copied"
            print("PASS: copy_millhouse propagates non-excluded entries (excludes junction aliases)")

        # --- list_worktrees: single main worktree ---
        with tempfile.TemporaryDirectory() as tmp:
            hub = Path(tmp)
            _git_init(hub)
            wt_result = list_worktrees(hub)
            assert len(wt_result) == 1, f"expected 1 worktree, got {len(wt_result)}"
            assert Path(wt_result[0]["path"]) == hub, f"expected path={hub!s}, got {wt_result[0]['path']!r}"
            assert wt_result[0]["branch"] == "main", f"expected branch='main', got {wt_result[0]['branch']!r}"
            print("PASS list_worktrees — single main worktree")

        # --- list_worktrees: two worktrees ---
        with tempfile.TemporaryDirectory() as tmp:
            hub = Path(tmp) / "hub"
            hub.mkdir()
            _git_init(hub)
            wt_path = Path(tmp) / "wt"
            subprocess.run(
                ["git", "-C", str(hub), "worktree", "add", "-b", "wt-branch", str(wt_path)],
                check=True, capture_output=True,
            )
            wt_result = list_worktrees(hub)
            assert len(wt_result) == 2, f"expected 2 worktrees, got {len(wt_result)}"
            assert wt_result[1]["branch"] == "wt-branch", f"expected wt-branch, got {wt_result[1]['branch']!r}"
            assert Path(wt_result[1]["path"]) == wt_path, f"expected path={wt_path!s}, got {wt_result[1]['path']!r}"
            print("PASS list_worktrees — two worktrees")

        # --- list_worktrees: detached HEAD ---
        with tempfile.TemporaryDirectory() as tmp:
            hub = Path(tmp) / "hub"
            hub.mkdir()
            _git_init(hub)
            detached_path = Path(tmp) / "detached"
            subprocess.run(
                ["git", "-C", str(hub), "worktree", "add", "--detach", str(detached_path), "HEAD"],
                check=True, capture_output=True,
            )
            wt_result = list_worktrees(hub)
            detached_entries = [e for e in wt_result if Path(e["path"]) == detached_path]
            assert len(detached_entries) == 1, "detached worktree not found"
            assert detached_entries[0]["branch"] is None, f"expected None branch, got {detached_entries[0]['branch']!r}"
            print("PASS list_worktrees — detached HEAD branch is None")

        # --- remove: worktree removed from git and disk ---
        with tempfile.TemporaryDirectory() as tmp:
            hub = Path(tmp) / "hub"
            hub.mkdir()
            _git_init(hub)
            wt_path = Path(tmp) / "wt"
            subprocess.run(
                ["git", "-C", str(hub), "worktree", "add", "-b", "remove-branch", str(wt_path)],
                check=True, capture_output=True,
            )
            remove(wt_path, cwd=hub)
            wt_result = list_worktrees(hub)
            assert len(wt_result) == 1, f"expected 1 worktree after remove, got {len(wt_result)}"
            assert not wt_path.exists(), f"worktree dir still exists at {wt_path}"
            print("PASS remove — worktree removed from git and disk")

        # --- remove: nonexistent path raises WorktreeError ---
        with tempfile.TemporaryDirectory() as tmp:
            hub = Path(tmp)
            _git_init(hub)
            raised = False
            try:
                remove(hub / "nonexistent", cwd=hub, force=True)
            except WorktreeError:
                raised = True
            assert raised, "expected WorktreeError for nonexistent path"
            print("PASS remove — nonexistent path raises WorktreeError")

        # --- WorktreeLockedError is a WorktreeError subclass ---
        assert issubclass(WorktreeLockedError, WorktreeError)
        print("PASS: WorktreeLockedError is WorktreeError subclass")

        # --- remove_safe raises WorktreeLockedError on "Permission denied" in git stderr ---
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "wt"
            path.mkdir()
            cwd = Path(tmp) / "cwd"
            cwd.mkdir()
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stderr = "fatal: Permission denied"
            raised_locked = False
            with patch("_worktree._subprocess_util.run", return_value=mock_result):
                with patch("_worktree.kill_stale_holders"):
                    try:
                        remove_safe(path, cwd=cwd, junctions_cfg={})
                    except WorktreeLockedError:
                        raised_locked = True
            assert raised_locked, "expected WorktreeLockedError for Permission denied"
            print("PASS: remove_safe raises WorktreeLockedError on Permission denied")

        # --- remove_safe raises WorktreeLockedError on "is in use" in git stderr ---
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "wt"
            path.mkdir()
            cwd = Path(tmp) / "cwd"
            cwd.mkdir()
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stderr = "fatal: is in use"
            raised_locked = False
            with patch("_worktree._subprocess_util.run", return_value=mock_result):
                with patch("_worktree.kill_stale_holders"):
                    try:
                        remove_safe(path, cwd=cwd, junctions_cfg={})
                    except WorktreeLockedError:
                        raised_locked = True
            assert raised_locked, "expected WorktreeLockedError for is in use"
            print("PASS: remove_safe raises WorktreeLockedError on is in use")

        # --- remove_safe raises base WorktreeError (not subclass) for unrecognized git errors ---
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "wt"
            path.mkdir()
            cwd = Path(tmp) / "cwd"
            cwd.mkdir()
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stderr = "fatal: some unknown error"
            raised_base = False
            raised_locked_wrong = False
            with patch("_worktree._subprocess_util.run", return_value=mock_result):
                with patch("_worktree.kill_stale_holders"):
                    try:
                        remove_safe(path, cwd=cwd, junctions_cfg={})
                    except WorktreeLockedError:
                        raised_locked_wrong = True
                    except WorktreeError:
                        raised_base = True
            assert raised_base and not raised_locked_wrong, "expected base WorktreeError (not locked) for unrecognized error"
            print("PASS: remove_safe raises WorktreeError (not locked) for unrecognized error")

        # --- remove_safe raises WorktreeLockedError when shutil.rmtree raises PermissionError (long-path fallback) ---
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "wt"
            path.mkdir()
            cwd = Path(tmp) / "cwd"
            cwd.mkdir()
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stderr = "Filename too long"
            raised_locked = False
            with patch("_worktree._subprocess_util.run", return_value=mock_result):
                with patch("_safe_rmtree.shutil.rmtree", side_effect=PermissionError("locked")):
                    with patch("_safe_rmtree._blacklist_for", return_value=[]):
                        with patch("_worktree.kill_stale_holders"):
                            try:
                                remove_safe(path, cwd=cwd, junctions_cfg={})
                            except WorktreeLockedError:
                                raised_locked = True
            assert raised_locked, "expected WorktreeLockedError when rmtree fallback raises PermissionError"
            print("PASS: remove_safe raises WorktreeLockedError when rmtree fallback raises PermissionError")

        # --- remove_safe retries safe_rmtree once after WinError 145 and succeeds ---
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "wt"
            path.mkdir()
            cwd = Path(tmp) / "cwd"
            cwd.mkdir()
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stderr = "Directory not empty"
            lock_exc = OSError("[WinError 145] The directory is not empty")
            lock_exc.winerror = 145
            with patch("_worktree._subprocess_util.run", return_value=mock_result):
                with patch("_safe_rmtree.shutil.rmtree", side_effect=[lock_exc, None]) as mock_rmtree:
                    with patch("_safe_rmtree._blacklist_for", return_value=[]):
                        with patch("_worktree.kill_stale_holders"):
                            with patch("_worktree.subprocess.run", return_value=MagicMock()) as mock_dotnet_run:
                                remove_safe(path, cwd=cwd, junctions_cfg={})
            assert mock_rmtree.call_count == 2, "expected safe_rmtree to be called twice (initial attempt + one retry)"
            assert mock_dotnet_run.call_count == 1, "expected exactly one dotnet build-server shutdown call"
            assert mock_dotnet_run.call_args.args[0] == ["dotnet", "build-server", "shutdown"], "expected the dotnet build-server shutdown command to be invoked"
            print("PASS: remove_safe retries safe_rmtree once after WinError 145 and succeeds")

        # --- remove_safe raises WorktreeLockedError when retry also raises WinError 145 ---
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "wt"
            path.mkdir()
            cwd = Path(tmp) / "cwd"
            cwd.mkdir()
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stderr = "Directory not empty"
            lock_exc_1 = OSError("[WinError 145] The directory is not empty")
            lock_exc_1.winerror = 145
            lock_exc_2 = OSError("[WinError 145] The directory is not empty")
            lock_exc_2.winerror = 145
            raised_locked = False
            with patch("_worktree._subprocess_util.run", return_value=mock_result):
                with patch("_safe_rmtree.shutil.rmtree", side_effect=[lock_exc_1, lock_exc_2]) as mock_rmtree:
                    with patch("_safe_rmtree._blacklist_for", return_value=[]):
                        with patch("_worktree.kill_stale_holders"):
                            with patch("_worktree.subprocess.run", return_value=MagicMock()):
                                try:
                                    remove_safe(path, cwd=cwd, junctions_cfg={})
                                except WorktreeLockedError:
                                    raised_locked = True
            assert raised_locked, "expected WorktreeLockedError when retry also raises WinError 145"
            assert mock_rmtree.call_count == 2, "expected safe_rmtree to be called twice (initial attempt + one retry, not more)"
            print("PASS: remove_safe raises WorktreeLockedError when retry also raises WinError 145")

        # --- remove_safe re-raises a non-145 OSError from rmtree fallback unchanged (no retry) ---
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "wt"
            path.mkdir()
            cwd = Path(tmp) / "cwd"
            cwd.mkdir()
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stderr = "Directory not empty"
            plain_exc = OSError("some other rmtree failure")
            raised = False
            with patch("_worktree._subprocess_util.run", return_value=mock_result):
                with patch("_safe_rmtree.shutil.rmtree", side_effect=plain_exc):
                    with patch("_safe_rmtree._blacklist_for", return_value=[]):
                        with patch("_worktree.kill_stale_holders"):
                            with patch("_worktree.subprocess.run", return_value=MagicMock()):
                                try:
                                    remove_safe(path, cwd=cwd, junctions_cfg={})
                                except OSError as exc:
                                    raised = True
                                    assert exc is plain_exc, "expected the original OSError instance to propagate unchanged"
            assert raised, "expected a non-145 OSError to propagate uncaught past remove_safe"
            print("PASS: remove_safe re-raises a non-145 OSError from rmtree fallback unchanged (no retry)")

        # --- remove_safe raises WorktreeLockedError on "Invalid argument" in git stderr ---
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "wt"
            path.mkdir()
            cwd = Path(tmp) / "cwd"
            cwd.mkdir()
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stderr = "error: Invalid argument"
            raised_locked = False
            locked_exc = None
            with patch("_worktree._subprocess_util.run", return_value=mock_result):
                with patch("_worktree.kill_stale_holders"):
                    try:
                        remove_safe(path, cwd=cwd, junctions_cfg={})
                    except WorktreeLockedError as exc:
                        raised_locked = True
                        locked_exc = exc
            assert raised_locked, "expected WorktreeLockedError for Invalid argument"
            assert locked_exc is not None and "Invalid argument" in str(locked_exc), (
                f"expected 'Invalid argument' in error message: {locked_exc}"
            )
            print("PASS: remove_safe raises WorktreeLockedError on Invalid argument")

        # --- remove_safe exits cleanly via rmtree fallback on "is not a working tree" (path exists) ---
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "wt"
            path.mkdir()
            cwd = Path(tmp) / "cwd"
            cwd.mkdir()
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stderr = "fatal: 'path' is not a working tree"
            mock_prune = MagicMock()
            mock_prune.returncode = 0
            mock_prune.stderr = ""
            with patch("_worktree._subprocess_util.run", side_effect=[mock_result, mock_prune]):
                with patch("_safe_rmtree._blacklist_for", return_value=[]):
                    with patch("_worktree.kill_stale_holders"):
                        remove_safe(path, cwd=cwd, junctions_cfg={})
            assert not path.exists(), f"expected path to be removed by rmtree, but it still exists: {path}"
            print("PASS: remove_safe exits cleanly via rmtree fallback on 'is not a working tree' (path exists)")

        # --- remove_safe raises WorktreeLockedError when rmtree raises PermissionError on "is not a working tree" ---
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "wt"
            path.mkdir()
            cwd = Path(tmp) / "cwd"
            cwd.mkdir()
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stderr = "fatal: 'path' is not a working tree"
            raised_locked = False
            with patch("_worktree._subprocess_util.run", return_value=mock_result):
                with patch("_safe_rmtree.shutil.rmtree", side_effect=PermissionError("locked")):
                    with patch("_safe_rmtree._blacklist_for", return_value=[]):
                        with patch("_worktree.kill_stale_holders"):
                            try:
                                remove_safe(path, cwd=cwd, junctions_cfg={})
                            except WorktreeLockedError:
                                raised_locked = True
            assert raised_locked, "expected WorktreeLockedError when rmtree raises PermissionError on 'is not a working tree'"
            print("PASS: remove_safe raises WorktreeLockedError when rmtree raises PermissionError on 'is not a working tree'")

        # --- remove_safe exits cleanly when path absent and "is not a working tree" ---
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "wt"
            cwd = Path(tmp) / "cwd"
            cwd.mkdir()
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stderr = "fatal: 'path' is not a working tree"
            mock_prune = MagicMock()
            mock_prune.returncode = 1
            mock_prune.stderr = "warning: prune warning"
            with patch("_worktree._subprocess_util.run", side_effect=[mock_result, mock_prune]):
                with patch("_worktree.kill_stale_holders"):
                    remove_safe(path, cwd=cwd, junctions_cfg={})
            print("PASS: remove_safe exits cleanly when path absent and 'is not a working tree'")

        # --- remove_safe prunes a stale nested-worktree registration after force-removing the enclosing task worktree ---
        # Real git, no mocks: reproduces the exact orphan scenario from GitHub issue tracking
        # _verify_baseline.py's transient nested worktree — a task worktree force-removed mid
        # computation leaves its nested `.scratch/nested` worktree's administrative entry behind
        # in the hub's common gitdir until `git worktree prune` clears it.
        with tempfile.TemporaryDirectory() as tmp:
            hub = Path(tmp) / "hub"
            hub.mkdir()
            _git_init(hub)

            # Register the outer task worktree off the hub on its own branch.
            task_wt = Path(tmp) / "task"
            subprocess.run(
                ["git", "-C", str(hub), "worktree", "add", "-b", "task-branch", str(task_wt)],
                check=True, capture_output=True,
            )

            # Register a nested worktree inside the task worktree's .scratch/ dir, against the
            # hub's common gitdir — mirroring _verify_baseline._checkout_parent_branch's real
            # detached-HEAD baseline-checkout behavior.
            nested_path = task_wt / ".scratch" / "nested"
            (task_wt / ".scratch").mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["git", "-C", str(hub), "worktree", "add", "--detach", str(nested_path), "HEAD"],
                check=True, capture_output=True,
            )

            # Force-remove the outer task worktree via the real remove_safe (no mocks), capturing
            # stderr so we can later confirm which removal branch actually ran.
            captured = io.StringIO()
            with contextlib.redirect_stderr(captured):
                remove_safe(task_wt, cwd=hub, junctions_cfg={})

            assert not task_wt.exists(), f"expected task worktree dir removed, still exists: {task_wt}"

            # The nested worktree's directory went with it, so its stale git administrative entry
            # must have been pruned rather than left orphaned in the hub's common gitdir.
            wt_result = list_worktrees(hub)
            surviving_nested = [e for e in wt_result if Path(e["path"]) == nested_path]
            assert not surviving_nested, (
                f"expected nested worktree registration pruned, found surviving entries: {surviving_nested}"
            )

            # Pin down that the outer removal went through the direct-success branch (git
            # worktree remove --force returning 0), not the fallback branch — otherwise this
            # test could silently pass by only re-exercising the fallback branch's pre-existing
            # prune call.
            assert "removed via git" in captured.getvalue(), (
                f"expected direct-success removal branch, captured stderr: {captured.getvalue()!r}"
            )
            print("PASS: remove_safe prunes stale nested-worktree registration after force-removing enclosing task worktree")

        # --- remove_safe passes -c core.longpaths=true in both the worktree-remove
        # and worktree-prune argv, mirroring _verify_baseline.py's creation-side placement ---
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "wt"
            path.mkdir()
            cwd = Path(tmp) / "cwd"
            cwd.mkdir()
            captured_argv = []

            def _fake_run_capture_all(argv, **kwargs):
                captured_argv.append(argv)
                return MagicMock(returncode=0, stdout="", stderr="")

            with patch("_worktree._subprocess_util.run", side_effect=_fake_run_capture_all):
                with patch("_worktree.kill_stale_holders"):
                    remove_safe(path, cwd=cwd, junctions_cfg={})

            assert len(captured_argv) == 2, (
                f"expected exactly 2 subprocess calls (remove, prune), got {len(captured_argv)}: {captured_argv!r}"
            )

            for argv in captured_argv:
                # -c core.longpaths=true must appear as an adjacent pair.
                longpaths_index = None
                for i, token in enumerate(argv[:-1]):
                    if token == "-c" and argv[i + 1] == "core.longpaths=true":
                        longpaths_index = i
                        break
                assert longpaths_index is not None, (
                    f"expected '-c core.longpaths=true' pair in argv: {argv!r}"
                )

                # It must sit after the -C <cwd> pair and before the 'worktree' token.
                c_index = argv.index("-C")
                worktree_index = argv.index("worktree")
                assert c_index < longpaths_index < worktree_index, (
                    f"expected order -C ... -c core.longpaths=true ... worktree, got {argv!r}"
                )
            print(
                "PASS: remove_safe's git worktree remove/prune argv carries "
                "-c core.longpaths=true between -C <cwd> and 'worktree'"
            )

        # --- processes_holding_path: only records whose cmdline references worktree ---
        with tempfile.TemporaryDirectory() as tmp:
            worktree = Path(tmp) / "my-worktree"
            worktree.mkdir()
            records = [
                {"pid": 100, "command_line": "bash /path/to/script.sh"},
                {"pid": 101, "command_line": f"python -c 'poll {worktree}/file'"},
                {"pid": 102, "command_line": "python other.py"},
                {"pid": 103, "command_line": None},
                {"pid": 104, "command_line": ""},
            ]
            result = processes_holding_path(worktree, records)
            assert result == [101], f"Expected [101], got {result}"
            print("PASS: processes_holding_path — only records with worktree in cmdline returned")

        # --- processes_holding_path: case-insensitive match ---
        with tempfile.TemporaryDirectory() as tmp:
            worktree = Path(tmp) / "MyWorktree"
            worktree.mkdir()
            resolved_path = str(worktree.resolve()).lower()
            records = [
                {"pid": 200, "command_line": f"bash {resolved_path}/poll.sh"},
                {"pid": 201, "command_line": "python other.py"},
            ]
            result = processes_holding_path(worktree, records)
            assert result == [200], f"Expected [200] for case-insensitive match, got {result}"
            print("PASS: processes_holding_path — case-insensitive path matching")

        # --- processes_holding_path: empty cmdline dict key is skipped ---
        with tempfile.TemporaryDirectory() as tmp:
            worktree = Path(tmp) / "wt"
            worktree.mkdir()
            records = [
                {"pid": 300},  # missing command_line key
                {"pid": 301, "command_line": f"bash {worktree}/poll"},
            ]
            result = processes_holding_path(worktree, records)
            assert result == [301], f"Expected [301], got {result}"
            print("PASS: processes_holding_path — missing command_line key handled")

        # --- kill_stale_holders: calls enumerator and taskkill for matching pids ---
        with tempfile.TemporaryDirectory() as tmp:
            worktree = Path(tmp) / "wt"
            worktree.mkdir()
            enumerated_records = [
                {"pid": 400, "command_line": f"poll {worktree}/file"},
                {"pid": 401, "command_line": "other process"},
            ]
            kill_calls = []

            def _fake_enumerate():
                return enumerated_records

            def _fake_run(argv, **kwargs):
                if "taskkill" in argv:
                    kill_calls.append(argv)
                return MagicMock(returncode=0, stdout="", stderr="")

            with patch("_worktree._subprocess_util.run", side_effect=_fake_run):
                kill_stale_holders(worktree, enumerate_processes=_fake_enumerate)

            taskkill_calls = [c for c in kill_calls if "taskkill" in c]
            assert len(taskkill_calls) == 1, f"Expected 1 taskkill call, got {len(taskkill_calls)}"
            assert "400" in taskkill_calls[0], f"Expected pid 400 in taskkill call, got {taskkill_calls[0]}"
            print("PASS: kill_stale_holders — enumerator called, matching pid taskkilled")

        # --- kill_stale_holders: enumerator error is swallowed ---
        with tempfile.TemporaryDirectory() as tmp:
            worktree = Path(tmp) / "wt"
            worktree.mkdir()

            def _bad_enumerate():
                raise RuntimeError("enumeration failed")

            try:
                kill_stale_holders(worktree, enumerate_processes=_bad_enumerate)
            except RuntimeError:
                raise AssertionError("kill_stale_holders must swallow enumerator exceptions")
            print("PASS: kill_stale_holders — enumerator exceptions swallowed")

        # --- kill_stale_holders: taskkill error is swallowed ---
        with tempfile.TemporaryDirectory() as tmp:
            worktree = Path(tmp) / "wt"
            worktree.mkdir()
            enumerated_records = [
                {"pid": 500, "command_line": f"poll {worktree}"},
            ]

            def _fake_enumerate_500():
                return enumerated_records

            def _fake_run_error(argv, **kwargs):
                if "taskkill" in argv:
                    raise OSError("taskkill failed")
                return MagicMock(returncode=0, stdout="", stderr="")

            try:
                with patch("_worktree._subprocess_util.run", side_effect=_fake_run_error):
                    kill_stale_holders(worktree, enumerate_processes=_fake_enumerate_500)
            except OSError:
                raise AssertionError("kill_stale_holders must swallow taskkill exceptions")
            print("PASS: kill_stale_holders — taskkill exceptions swallowed")

        # --- kill_stale_holders: real default enumerator command shape and single-dict JSON ---
        if sys.platform == "win32":
            with tempfile.TemporaryDirectory() as tmp:
                worktree = Path(tmp) / "wt"
                worktree.mkdir()

                # Capture the argv passed to the default enumerator's subprocess call so we can assert on the exact PowerShell command shape, regressing #602 (the -AsArray flag is PowerShell-7-only and fails on the default PS 5.1 alias).
                captured_argv = []

                def _fake_run_capture_argv(argv, **kwargs):
                    captured_argv.append(argv)
                    return MagicMock(returncode=0, stdout="[]", stderr="")

                with patch("_worktree._subprocess_util.run", side_effect=_fake_run_capture_argv):
                    kill_stale_holders(worktree, enumerate_processes=None)

                assert len(captured_argv) == 1, f"Expected 1 subprocess call, got {len(captured_argv)}"
                command_text = " ".join(captured_argv[0])
                assert "-AsArray" not in command_text, (
                    f"Regression #602: -AsArray must not appear in the PowerShell command, got {command_text}"
                )
                print("PASS: kill_stale_holders — default enumerator omits PS7-only -AsArray flag")

                # Re-invoke with the default enumerator returning a single JSON object (not a list), the exact shape PS 5.1's ConvertTo-Json produces for one process.
                # The existing `data = [data] if data else []` normalization must still wrap it.
                single_dict_json = json.dumps({"ProcessId": 999, "CommandLine": f"poll {worktree}/file"})
                kill_calls = []

                def _fake_run_single_dict(argv, **kwargs):
                    if "taskkill" in argv:
                        kill_calls.append(argv)
                        return MagicMock(returncode=0, stdout="", stderr="")
                    return MagicMock(returncode=0, stdout=single_dict_json, stderr="")

                with patch("_worktree._subprocess_util.run", side_effect=_fake_run_single_dict):
                    kill_stale_holders(worktree, enumerate_processes=None)

                taskkill_calls = [c for c in kill_calls if "taskkill" in c]
                assert len(taskkill_calls) == 1, f"Expected 1 taskkill call, got {len(taskkill_calls)}"
                assert "999" in taskkill_calls[0], f"Expected pid 999 in taskkill call, got {taskkill_calls[0]}"
                print("PASS: kill_stale_holders — single-dict JSON from default enumerator is normalized")
        else:
            print("SKIP: kill_stale_holders default enumerator test (Windows-only)")

        # --- move: relocates a worktree registered via create() ---
        with tempfile.TemporaryDirectory() as tmp:
            hub = Path(tmp) / "hub"
            hub.mkdir()
            _git_init(hub)
            old_path = Path(tmp) / "old"
            new_path = Path(tmp) / "new"
            create("move-branch", old_path, cwd=hub)
            move(old_path, new_path, cwd=hub)

            wt_result = list_worktrees(hub)
            paths = [Path(e["path"]) for e in wt_result]
            assert new_path in paths, f"expected {new_path} registered after move, got {paths}"
            assert old_path not in paths, f"expected {old_path} no longer registered after move, got {paths}"

            list_output = subprocess.run(
                ["git", "-C", str(hub), "worktree", "list"],
                check=True, capture_output=True, text=True,
            ).stdout
            assert str(old_path) not in list_output, (
                f"old path {old_path} still appears in git worktree list output: {list_output!r}"
            )
            print("PASS move — relocates a registered worktree and updates git worktree list")

        # --- move: target path already occupied by a regular file raises WorktreeError ---
        # (git worktree move behaves like `mv`: an existing *directory* target nests the worktree inside it rather than failing, so the genuine collision case is a pre-existing regular file at the target path.)
        with tempfile.TemporaryDirectory() as tmp:
            hub = Path(tmp) / "hub"
            hub.mkdir()
            _git_init(hub)
            old_path = Path(tmp) / "old2"
            new_path = Path(tmp) / "new2"
            new_path.write_text("occupied", encoding="utf-8")
            create("move-branch-2", old_path, cwd=hub)
            raised = False
            try:
                move(old_path, new_path, cwd=hub)
            except WorktreeError:
                raised = True
            assert raised, "expected WorktreeError when move target already exists as a file"
            print("PASS move — target path already occupied by a regular file raises WorktreeError")

        print("All _worktree unit tests passed.")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
