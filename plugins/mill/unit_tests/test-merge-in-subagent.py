"""Unit tests for millpy-merge-in-subagent.py verify-fix success gating."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest.mock
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _implementer_claude  # noqa: E402
import _implementer_common  # noqa: E402
import _marker  # noqa: E402
import _review_common  # noqa: E402
import _subprocess_util  # noqa: E402

# Load the subagent module (name contains hyphen)
_subagent_path = Path(__file__).resolve().parent.parent / "scripts" / "millpy-merge-in-subagent.py"
_spec = importlib.util.spec_from_file_location("millpy_merge_in_subagent", _subagent_path)
millpy_merge_in_subagent = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(millpy_merge_in_subagent)


def _capture_stdout(fn):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = fn()
    return rc, buf.getvalue()


def _setup_fixture(project_root: Path) -> str:
    """Init git repo with a README.md base commit; return base SHA."""
    subprocess.run(["git", "init", "-q", str(project_root)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(project_root), "config", "user.email", "test@test.com"],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(project_root), "config", "user.name", "Test"],
        check=True, capture_output=True,
    )
    (project_root / "README.md").write_text("seed", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(project_root), "add", "README.md"],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(project_root), "commit", "-m", "initial"],
        check=True, capture_output=True,
    )
    return subprocess.run(
        ["git", "-C", str(project_root), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


def _setup_mill_config(project_root: Path, mill_dir: Path):
    """Setup .millhouse config and mock marker/config resolution."""
    mill_dir.mkdir(parents=True, exist_ok=True)
    config_file = mill_dir / "config.local.yaml"
    config_file.write_text("merge:\n  model: haiku\n", encoding="utf-8")


def main() -> int:
    errors = 0

    # Case A: verify passes before any fixer runs (initial verify returncode == 0)
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        mill_dir = project_root / ".millhouse"
        _setup_fixture(project_root)
        _setup_mill_config(project_root, mill_dir)

        # Mock the dependencies
        def mock_slug_from_branch(*args, **kwargs):
            return "test-task"

        def mock_load_config(git_root, mill_dir):
            return {
                "merge": {"model": "haiku"},
                "roles": {"implementer": {"model": "haiku"}},
            }

        try:
            with unittest.mock.patch.object(_marker, "slug_from_branch", side_effect=mock_slug_from_branch):
                with unittest.mock.patch.object(_review_common, "load_config", side_effect=mock_load_config):
                    # Mock subprocess.run to return success for verify command
                    original_run = subprocess.run

                    def mock_subprocess_run(cmd, *args, **kwargs):
                        if isinstance(cmd, str) or (isinstance(cmd, list) and "verify" in str(cmd)):
                            return subprocess.CompletedProcess(
                                args=cmd,
                                returncode=0,
                                stdout="Verify passed",
                                stderr="",
                            )
                        return original_run(cmd, *args, **kwargs)

                    with unittest.mock.patch("subprocess.run", side_effect=mock_subprocess_run):
                        rc, captured = _capture_stdout(
                            lambda: millpy_merge_in_subagent.main([
                                "--mode", "verify-fix",
                                "--cmd", "verify",
                                "--checkpoint", "abc123",
                                "--stage", "full",
                            ])
                        )

                        try:
                            data = json.loads(captured.strip())
                            assert data["status"] == "success", f"expected status=success, got {data}"
                            assert "commit_sha" in data, f"expected commit_sha in {data}"
                            print("PASS: Case A - verify passes before fixer -> success")
                        except Exception as exc:
                            print(f"FAIL: Case A ({exc}) captured={captured!r}", file=sys.stderr)
                            errors += 1
        except Exception as exc:
            print(f"FAIL: Case A setup error ({exc})", file=sys.stderr)
            errors += 1

    # Case B: fixer ran, post-fix verify passes (returncode == 0)
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        mill_dir = project_root / ".millhouse"
        _setup_fixture(project_root)
        _setup_mill_config(project_root, mill_dir)

        def mock_slug_from_branch(*args, **kwargs):
            return "test-task"

        def mock_load_config(git_root, mill_dir):
            return {
                "merge": {"model": "haiku"},
                "roles": {"implementer": {"model": "haiku"}},
            }

        try:
            with unittest.mock.patch.object(_marker, "slug_from_branch", side_effect=mock_slug_from_branch):
                with unittest.mock.patch.object(_review_common, "load_config", side_effect=mock_load_config):
                    # Mock subprocess.run: first verify fails, then finalize verify passes
                    call_count = [0]
                    original_run = subprocess.run

                    def mock_subprocess_run(cmd, *args, **kwargs):
                        if isinstance(cmd, str) or (isinstance(cmd, list) and "verify" in str(cmd)):
                            call_count[0] += 1
                            if call_count[0] == 1:
                                # Initial verify fails
                                return subprocess.CompletedProcess(
                                    args=cmd,
                                    returncode=1,
                                    stdout="Verify failed initially",
                                    stderr="Error: test",
                                )
                            else:
                                # Post-fix verify passes
                                return subprocess.CompletedProcess(
                                    args=cmd,
                                    returncode=0,
                                    stdout="Verify passed after fix",
                                    stderr="",
                                )
                        return original_run(cmd, *args, **kwargs)

                    def mock_implementer_run(*args, **kwargs):
                        # Simulate implementer fixing the issue (making a commit)
                        subprocess.run(
                            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "fix"],
                            check=True, capture_output=True,
                        )
                        return "Agent output", None

                    with unittest.mock.patch("subprocess.run", side_effect=mock_subprocess_run):
                        with unittest.mock.patch.object(_implementer_claude, "run", side_effect=mock_implementer_run):
                            rc, captured = _capture_stdout(
                                lambda: millpy_merge_in_subagent.main([
                                    "--mode", "verify-fix",
                                    "--cmd", "verify",
                                    "--checkpoint", "abc123",
                                    "--stage", "full",
                                ])
                            )

                            try:
                                data = json.loads(captured.strip())
                                assert data["status"] == "success", f"expected status=success, got {data}"
                                assert "commit_sha" in data, f"expected commit_sha in {data}"
                                print("PASS: Case B - fixer ran, post-fix verify passes -> success")
                            except Exception as exc:
                                print(f"FAIL: Case B ({exc}) captured={captured!r}", file=sys.stderr)
                                errors += 1
        except Exception as exc:
            print(f"FAIL: Case B setup error ({exc})", file=sys.stderr)
            errors += 1

    # Case C: fixer ran, post-fix verify still fails (returncode != 0)
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        mill_dir = project_root / ".millhouse"
        _setup_fixture(project_root)
        _setup_mill_config(project_root, mill_dir)

        def mock_slug_from_branch(*args, **kwargs):
            return "test-task"

        def mock_load_config(git_root, mill_dir):
            return {
                "merge": {"model": "haiku"},
                "roles": {"implementer": {"model": "haiku"}},
            }

        try:
            with unittest.mock.patch.object(_marker, "slug_from_branch", side_effect=mock_slug_from_branch):
                with unittest.mock.patch.object(_review_common, "load_config", side_effect=mock_load_config):
                    # Mock subprocess.run: verify always fails
                    original_run = subprocess.run

                    def mock_subprocess_run(cmd, *args, **kwargs):
                        if isinstance(cmd, str) or (isinstance(cmd, list) and "verify" in str(cmd)):
                            return subprocess.CompletedProcess(
                                args=cmd,
                                returncode=1,
                                stdout="Verify failed",
                                stderr="Error details",
                            )
                        return original_run(cmd, *args, **kwargs)

                    def mock_implementer_run(*args, **kwargs):
                        # Simulate implementer attempting fix (making a commit)
                        subprocess.run(
                            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "attempted fix"],
                            check=True, capture_output=True,
                        )
                        return "Agent output claiming success", None

                    with unittest.mock.patch("subprocess.run", side_effect=mock_subprocess_run):
                        with unittest.mock.patch.object(_implementer_claude, "run", side_effect=mock_implementer_run):
                            rc, captured = _capture_stdout(
                                lambda: millpy_merge_in_subagent.main([
                                    "--mode", "verify-fix",
                                    "--cmd", "verify",
                                    "--checkpoint", "abc123",
                                    "--stage", "full",
                                ])
                            )

                            try:
                                data = json.loads(captured.strip())
                                assert data["status"] == "stuck", f"expected status=stuck, got {data}"
                                assert data.get("stuck_type") == "verify", f"expected stuck_type=verify, got {data}"
                                assert "reason" in data, f"expected reason in {data}"
                                # Verify it's NOT success even though agent claimed it
                                assert "success" not in str(data).lower() or data["status"] != "success", \
                                    f"expected not success despite agent output, got {data}"
                                print("PASS: Case C - fixer ran, post-fix verify fails -> stuck/verify (not success)")
                            except Exception as exc:
                                print(f"FAIL: Case C ({exc}) captured={captured!r}", file=sys.stderr)
                                errors += 1
        except Exception as exc:
            print(f"FAIL: Case C setup error ({exc})", file=sys.stderr)
            errors += 1

    # Case C-finalize: finalize stage with post-fix verify failure
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        mill_dir = project_root / ".millhouse"
        _setup_fixture(project_root)
        _setup_mill_config(project_root, mill_dir)

        agent_output_file = project_root / "agent-output.txt"
        agent_output_file.write_text("Agent claimed success", encoding="utf-8")

        def mock_slug_from_branch(*args, **kwargs):
            return "test-task"

        def mock_load_config(git_root, mill_dir):
            return {
                "merge": {"model": "haiku"},
                "roles": {"implementer": {"model": "haiku"}},
            }

        try:
            with unittest.mock.patch.object(_marker, "slug_from_branch", side_effect=mock_slug_from_branch):
                with unittest.mock.patch.object(_review_common, "load_config", side_effect=mock_load_config):
                    original_run = subprocess.run

                    def mock_subprocess_run(cmd, *args, **kwargs):
                        if isinstance(cmd, str) or (isinstance(cmd, list) and "verify" in str(cmd)):
                            return subprocess.CompletedProcess(
                                args=cmd,
                                returncode=1,
                                stdout="Verify still fails",
                                stderr="Error in finalize",
                            )
                        return original_run(cmd, *args, **kwargs)

                    with unittest.mock.patch("subprocess.run", side_effect=mock_subprocess_run):
                        rc, captured = _capture_stdout(
                            lambda: millpy_merge_in_subagent.main([
                                "--mode", "verify-fix",
                                "--cmd", "verify",
                                "--stage", "finalize",
                                "--agent-output", str(agent_output_file),
                            ])
                        )

                        try:
                            data = json.loads(captured.strip())
                            assert data["status"] == "stuck", f"expected status=stuck, got {data}"
                            assert data.get("stuck_type") == "verify", f"expected stuck_type=verify, got {data}"
                            assert "reason" in data, f"expected reason in {data}"
                            print("PASS: Case C-finalize - finalize stage with verify failure -> stuck/verify")
                        except Exception as exc:
                            print(f"FAIL: Case C-finalize ({exc}) captured={captured!r}", file=sys.stderr)
                            errors += 1
        except Exception as exc:
            print(f"FAIL: Case C-finalize setup error ({exc})", file=sys.stderr)
            errors += 1

    # Test _posix_shell_run_args: Windows with bash available
    try:
        with unittest.mock.patch("_implementer_common.os") as mock_os:
            with unittest.mock.patch("_implementer_common.shutil") as mock_shutil:
                mock_os.name = "nt"
                mock_shutil.which.return_value = "/usr/bin/bash"
                run_args, run_kwargs = _implementer_common._posix_shell_run_args("PYTHONPATH= uv run foo")
                assert run_args == ["/usr/bin/bash", "-c", "PYTHONPATH= uv run foo"], \
                    f"expected bash args, got {run_args}"
                assert run_kwargs == {}, f"expected empty kwargs, got {run_kwargs}"
                print("PASS: posix-shell-args-windows-with-bash")
    except Exception as exc:
        print(f"FAIL: posix-shell-args-windows-with-bash ({exc})", file=sys.stderr)
        errors += 1

    # Test _posix_shell_run_args: Windows without bash
    try:
        with unittest.mock.patch("_implementer_common.os") as mock_os:
            with unittest.mock.patch("_implementer_common.shutil") as mock_shutil:
                mock_os.name = "nt"
                mock_shutil.which.return_value = None
                run_args, run_kwargs = _implementer_common._posix_shell_run_args("PYTHONPATH= uv run foo")
                assert run_args == "PYTHONPATH= uv run foo", f"expected cmd string, got {run_args}"
                assert run_kwargs == {"shell": True}, f"expected shell=True kwargs, got {run_kwargs}"
                print("PASS: posix-shell-args-windows-no-bash")
    except Exception as exc:
        print(f"FAIL: posix-shell-args-windows-no-bash ({exc})", file=sys.stderr)
        errors += 1

    # Test _posix_shell_run_args: POSIX (not Windows)
    try:
        with unittest.mock.patch("_implementer_common.os") as mock_os:
            mock_os.name = "posix"
            run_args, run_kwargs = _implementer_common._posix_shell_run_args("PYTHONPATH= uv run foo")
            assert run_args == "PYTHONPATH= uv run foo", f"expected cmd string, got {run_args}"
            assert run_kwargs == {"shell": True}, f"expected shell=True kwargs, got {run_kwargs}"
            print("PASS: posix-shell-args-posix")
    except Exception as exc:
        print(f"FAIL: posix-shell-args-posix ({exc})", file=sys.stderr)
        errors += 1

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All merge-in-subagent verify-fix success gating tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
