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
import _paths  # noqa: E402
import _review_common  # noqa: E402
import _reviewers  # noqa: E402
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
            with (
                unittest.mock.patch.object(_marker, "slug_from_branch", side_effect=mock_slug_from_branch),
                # project_root's rebind (Card 11) now calls resolve_git_root/resolve_active_hub
                # for real; mock both to keep project_root pinned to this fixture's own tempdir.
                unittest.mock.patch.object(_paths, "resolve_git_root", return_value=project_root),
            ):
                with unittest.mock.patch.object(_review_common, "load_config", side_effect=mock_load_config), \
                        unittest.mock.patch.object(_paths, "resolve_active_hub", return_value=project_root):
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
            with (
                unittest.mock.patch.object(_marker, "slug_from_branch", side_effect=mock_slug_from_branch),
                # project_root's rebind (Card 11) now calls resolve_git_root/resolve_active_hub
                # for real; mock both to keep project_root pinned to this fixture's own tempdir.
                unittest.mock.patch.object(_paths, "resolve_git_root", return_value=project_root),
            ):
                with unittest.mock.patch.object(_review_common, "load_config", side_effect=mock_load_config), \
                        unittest.mock.patch.object(_paths, "resolve_active_hub", return_value=project_root):
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
            with (
                unittest.mock.patch.object(_marker, "slug_from_branch", side_effect=mock_slug_from_branch),
                # project_root's rebind (Card 11) now calls resolve_git_root/resolve_active_hub
                # for real; mock both to keep project_root pinned to this fixture's own tempdir.
                unittest.mock.patch.object(_paths, "resolve_git_root", return_value=project_root),
            ):
                with unittest.mock.patch.object(_review_common, "load_config", side_effect=mock_load_config), \
                        unittest.mock.patch.object(_paths, "resolve_active_hub", return_value=project_root):
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
            with (
                unittest.mock.patch.object(_marker, "slug_from_branch", side_effect=mock_slug_from_branch),
                # project_root's rebind (Card 11) now calls resolve_git_root/resolve_active_hub
                # for real; mock both to keep project_root pinned to this fixture's own tempdir.
                unittest.mock.patch.object(_paths, "resolve_git_root", return_value=project_root),
            ):
                with unittest.mock.patch.object(_review_common, "load_config", side_effect=mock_load_config), \
                        unittest.mock.patch.object(_paths, "resolve_active_hub", return_value=project_root):
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

    # Case D: hub lives in a subdirectory of the outer git repo (#728 repro).
    # load_config must be invoked with the resolved hub root -- bootstrap via
    # _paths.resolve_hub_path(), and again after resolve_active_hub -- never
    # the outer git-repo root, or the hub's own mill-config.yaml is silently
    # missed in favor of a template/primary-clone fallback found by walking
    # from git_root.
    with tempfile.TemporaryDirectory() as tmpdir:
        outer_root = Path(tmpdir)
        hub_dir = outer_root / "sub" / "hub"
        hub_dir.mkdir(parents=True, exist_ok=True)
        mill_dir = hub_dir / ".millhouse"
        _setup_fixture(outer_root)
        _setup_mill_config(hub_dir, mill_dir)

        def mock_slug_from_branch(*args, **kwargs):
            return "test-task"

        observed_cfgs = []

        def mock_load_config(hub_root, mill_dir):
            if hub_root == hub_dir:
                cfg = {
                    "spawn": {"branch_prefix": "hub-own-prefix"},
                    "merge": {"model": "haiku"},
                    "roles": {"implementer": {"model": "haiku"}},
                }
            else:
                # Stand-in for the template/primary-clone fallback the pre-fix
                # code would silently pick up when passed the outer git-repo root.
                cfg = {
                    "spawn": {"branch_prefix": "template-fallback-prefix"},
                    "merge": {"model": "haiku"},
                    "roles": {"implementer": {"model": "haiku"}},
                }
            observed_cfgs.append((hub_root, cfg))
            return cfg

        try:
            with (
                unittest.mock.patch.object(_marker, "slug_from_branch", side_effect=mock_slug_from_branch),
                unittest.mock.patch.object(_paths, "resolve_git_root", return_value=outer_root),
                # project_root's bootstrap value (resolve_hub_path) and its
                # resolve_active_hub-corrected value both land on the hub
                # subdirectory -- neither must ever fall back to outer_root.
                unittest.mock.patch.object(_paths, "resolve_hub_path", return_value=hub_dir),
                unittest.mock.patch.object(_paths, "resolve_active_hub", return_value=hub_dir),
                unittest.mock.patch.object(_review_common, "load_config", side_effect=mock_load_config),
            ):
                original_run = subprocess.run

                def mock_subprocess_run(cmd, *args, **kwargs):
                    if isinstance(cmd, str) or (isinstance(cmd, list) and "verify" in str(cmd)):
                        return subprocess.CompletedProcess(
                            args=cmd, returncode=0, stdout="Verify passed", stderr="",
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
                    assert observed_cfgs, "expected load_config to be called at least once"
                    for hub_root_arg, cfg in observed_cfgs:
                        assert hub_root_arg == hub_dir, \
                            f"load_config called with wrong hub_root: {hub_root_arg}"
                        assert cfg["spawn"]["branch_prefix"] == "hub-own-prefix", \
                            f"unexpected cfg observed: {cfg}"
                    print("PASS: Case D - load_config uses hub root when hub in subdirectory")
                except Exception as exc:
                    print(f"FAIL: Case D ({exc}) captured={captured!r}", file=sys.stderr)
                    errors += 1
        except Exception as exc:
            print(f"FAIL: Case D setup error ({exc})", file=sys.stderr)
            errors += 1

    # Case E: bootstrap cfg and the resolve_active_hub-corrected reload can
    # genuinely differ. Downstream consumers -- the merge model name passed
    # to _reviewers.resolve, and the timeout passed to _implementer_claude.run
    # -- must come from the reloaded config, not the stale bootstrap one.
    with tempfile.TemporaryDirectory() as tmpdir:
        bootstrap_root = Path(tmpdir) / "bootstrap"
        corrected_root = Path(tmpdir) / "corrected"
        bootstrap_root.mkdir(parents=True, exist_ok=True)
        corrected_root.mkdir(parents=True, exist_ok=True)
        _setup_fixture(corrected_root)
        _setup_mill_config(corrected_root, corrected_root / ".millhouse")

        def mock_slug_from_branch(*args, **kwargs):
            return "test-task"

        bootstrap_cfg = {
            "merge": {"model": "bootstrap-model"},
            "roles": {"implementer": {"model": "bootstrap-model"}},
            "llm": {"implementer_timeout": 111},
        }
        reloaded_cfg = {
            "merge": {"model": "reloaded-model"},
            "roles": {"implementer": {"model": "reloaded-model"}},
            "llm": {"implementer_timeout": 999},
        }

        def mock_load_config(hub_root, mill_dir):
            return reloaded_cfg if hub_root == corrected_root else bootstrap_cfg

        captured_resolve_calls = []

        def mock_reviewers_resolve(registry, name):
            captured_resolve_calls.append(name)
            return {"type": "single", "provider": "claude", "model": "claude-haiku-4-5-20251001"}

        captured_timeouts = []

        def mock_implementer_run(*args, **kwargs):
            captured_timeouts.append(kwargs.get("timeout"))
            subprocess.run(
                ["git", "-C", str(corrected_root), "commit", "--allow-empty", "-m", "fix"],
                check=True, capture_output=True,
            )
            return "Agent output", None

        try:
            with (
                unittest.mock.patch.object(_marker, "slug_from_branch", side_effect=mock_slug_from_branch),
                # resolve_git_root stays pinned to the real git repo (corrected_root)
                # so downstream real git plumbing (resolve_container_path, git diff)
                # keeps working; only the hub-root resolution (resolve_hub_path,
                # resolve_active_hub) diverges, which is what this test targets.
                unittest.mock.patch.object(_paths, "resolve_git_root", return_value=corrected_root),
                unittest.mock.patch.object(_paths, "resolve_hub_path", return_value=bootstrap_root),
                unittest.mock.patch.object(_paths, "resolve_active_hub", return_value=corrected_root),
                unittest.mock.patch.object(_review_common, "load_config", side_effect=mock_load_config),
                unittest.mock.patch.object(_reviewers, "resolve", side_effect=mock_reviewers_resolve),
            ):
                original_run = subprocess.run
                call_count = [0]

                def mock_subprocess_run(cmd, *args, **kwargs):
                    if isinstance(cmd, str) or (isinstance(cmd, list) and "verify" in str(cmd)):
                        call_count[0] += 1
                        if call_count[0] == 1:
                            return subprocess.CompletedProcess(
                                args=cmd, returncode=1, stdout="Verify failed initially", stderr="",
                            )
                        return subprocess.CompletedProcess(
                            args=cmd, returncode=0, stdout="Verify passed after fix", stderr="",
                        )
                    return original_run(cmd, *args, **kwargs)

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
                    assert captured_resolve_calls, "expected _reviewers.resolve to be called"
                    assert captured_resolve_calls[-1] == "reloaded-model", \
                        f"expected _reviewers.resolve called with reloaded model_name, got {captured_resolve_calls}"
                    assert captured_timeouts, "expected _implementer_claude.run to be invoked"
                    assert captured_timeouts[-1] == 999, \
                        f"expected reloaded timeout (999), got {captured_timeouts}"
                    print("PASS: Case E - cfg reload after resolve_active_hub used for downstream model/timeout")
                except Exception as exc:
                    print(f"FAIL: Case E ({exc}) captured={captured!r}", file=sys.stderr)
                    errors += 1
        except Exception as exc:
            print(f"FAIL: Case E setup error ({exc})", file=sys.stderr)
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
