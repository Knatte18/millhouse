"""Unit tests for millpy-fix.py finalize arg wiring."""
from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest.mock
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _implementer_common import finalize_from_output  # noqa: E402


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


def main() -> int:
    errors = 0

    # Test 1: arg passthrough with start_sha and session_id
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        (project_root / "_mill").mkdir(parents=True)
        (project_root / "_mill/plan").mkdir(parents=True)
        review_file = project_root / "review.json"
        review_file.write_text("{}", encoding="utf-8")
        agent_output_file = project_root / "agent_output.txt"
        agent_output_file.write_text("test output", encoding="utf-8")

        # Create mock overview file
        overview_file = project_root / "_mill/plan/00-overview.md"
        overview_file.write_text("```yaml\nbatches: []\n```", encoding="utf-8")

        try:
            import importlib.util

            # Create mock modules that will be imported by millpy-fix
            mock_modules = {
                "_review_common": unittest.mock.MagicMock(),
                "_marker": unittest.mock.MagicMock(),
                "_status": unittest.mock.MagicMock(),
                "_reviewers": unittest.mock.MagicMock(),
                "_plan_dag": unittest.mock.MagicMock(),
                "_subprocess_util": unittest.mock.MagicMock(),
                "_paths": unittest.mock.MagicMock(),
                "_agent_dispatch": unittest.mock.MagicMock(),
                "_render": unittest.mock.MagicMock(),
                "_timestamp": unittest.mock.MagicMock(),
            }

            # Setup mock returns
            mock_modules["_review_common"].load_config = unittest.mock.MagicMock(
                return_value={
                    "paths": {"reviews_dir": "_mill/reviews/", "status_md": "_mill/status.md", "plan_dir": "_mill/plan/"},
                    "roles": {"fixer": {"model": "haiku"}, "implementer": {"self_fix_rounds": 2}},
                }
            )
            mock_modules["_marker"].slug_from_branch = unittest.mock.MagicMock(return_value="test-slug")
            mock_modules["_status"].read_full = unittest.mock.MagicMock(
                return_value={"yaml": {"task": "Test", "branch": "test-branch"}, "timeline": []}
            )
            mock_modules["_status"].read_branch = unittest.mock.MagicMock(return_value="test-branch")
            mock_modules["_reviewers"].load = unittest.mock.MagicMock(return_value={})
            mock_modules["_reviewers"].resolve = unittest.mock.MagicMock(
                return_value={"model": "claude-haiku-4-5-20251001"}
            )
            mock_modules["_plan_dag"].extract_batch_index = unittest.mock.MagicMock(return_value=[])

            def mock_subprocess_run(*args, **kwargs):
                result = unittest.mock.MagicMock()
                result.returncode = 0
                # Return git config values for user.name and user.email
                if args and ("user.name" in str(args) or "user.email" in str(args)):
                    result.stdout = "Test User" if "user.name" in str(args) else "test@example.com"
                else:
                    result.stdout = ""
                result.stderr = ""
                return result

            mock_modules["_subprocess_util"].run = unittest.mock.MagicMock(side_effect=mock_subprocess_run)
            def mock_resolve_task_path(project_root_arg, rel_path):
                return project_root / rel_path.lstrip("/")

            mock_modules["_paths"].status_path = unittest.mock.MagicMock(
                return_value=project_root / "_mill/status.md"
            )
            mock_modules["_paths"].resolve_task_path = unittest.mock.MagicMock(
                side_effect=mock_resolve_task_path
            )
            mock_modules["_paths"].resolve_git_root = unittest.mock.MagicMock(return_value=project_root)
            mock_modules["_paths"].resolve_wiki_path = unittest.mock.MagicMock(return_value=project_root)

            # Patch sys.modules
            with unittest.mock.patch.dict(sys.modules, mock_modules):
                spec = importlib.util.spec_from_file_location(
                    "millpy_fix_test1",
                    HUB / "plugins/mill/scripts/millpy-fix.py",
                )
                millpy_fix = importlib.util.module_from_spec(spec)

                # Create mock for finalize_from_output
                mock_finalize = unittest.mock.MagicMock(return_value=0)

                # Patch in sys.modules before executing the module
                sys.modules["millpy_fix_test1"] = millpy_fix
                with unittest.mock.patch.object(
                    millpy_fix, "finalize_from_output", mock_finalize, create=True
                ):
                    spec.loader.exec_module(millpy_fix)
                    millpy_fix.finalize_from_output = mock_finalize

                    rc = millpy_fix.main(
                        [
                            "--scope",
                            "holistic",
                            "--review-file",
                            str(review_file),
                            "--round",
                            "1",
                            "--stage",
                            "finalize",
                            "--agent-output",
                            str(agent_output_file),
                            "--start-sha",
                            "abc123",
                            "--session-id",
                            "sid-xyz",
                        ]
                    )

                    if mock_finalize.called:
                        call_args = mock_finalize.call_args
                        if (
                            call_args[1].get("start_sha") == "abc123"
                            and call_args[1].get("session_id") == "sid-xyz"
                        ):
                            print("PASS: arg passthrough with start_sha and session_id")
                        else:
                            print(
                                f"FAIL: arg passthrough - call_args={call_args}",
                                file=sys.stderr,
                            )
                            errors += 1
                    else:
                        print("FAIL: finalize_from_output not called", file=sys.stderr)
                        errors += 1
        except Exception as exc:
            print(f"FAIL: test 1 ({exc})", file=sys.stderr)
            errors += 1

    # Test 2: no start_sha -> start_sha=None passed
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        (project_root / "_mill").mkdir(parents=True)
        (project_root / "_mill/plan").mkdir(parents=True)
        review_file = project_root / "review.json"
        review_file.write_text("{}", encoding="utf-8")
        agent_output_file = project_root / "agent_output.txt"
        agent_output_file.write_text("test output", encoding="utf-8")

        overview_file = project_root / "_mill/plan/00-overview.md"
        overview_file.write_text("```yaml\nbatches: []\n```", encoding="utf-8")

        try:
            import importlib.util

            mock_modules = {
                "_review_common": unittest.mock.MagicMock(),
                "_marker": unittest.mock.MagicMock(),
                "_status": unittest.mock.MagicMock(),
                "_reviewers": unittest.mock.MagicMock(),
                "_plan_dag": unittest.mock.MagicMock(),
                "_subprocess_util": unittest.mock.MagicMock(),
                "_paths": unittest.mock.MagicMock(),
                "_agent_dispatch": unittest.mock.MagicMock(),
                "_render": unittest.mock.MagicMock(),
                "_timestamp": unittest.mock.MagicMock(),
            }

            mock_modules["_review_common"].load_config = unittest.mock.MagicMock(
                return_value={
                    "paths": {"reviews_dir": "_mill/reviews/", "status_md": "_mill/status.md", "plan_dir": "_mill/plan/"},
                    "roles": {"fixer": {"model": "haiku"}, "implementer": {"self_fix_rounds": 2}},
                }
            )
            mock_modules["_marker"].slug_from_branch = unittest.mock.MagicMock(return_value="test-slug")
            mock_modules["_status"].read_full = unittest.mock.MagicMock(
                return_value={"yaml": {"task": "Test", "branch": "test-branch"}, "timeline": []}
            )
            mock_modules["_status"].read_branch = unittest.mock.MagicMock(return_value="test-branch")
            mock_modules["_reviewers"].load = unittest.mock.MagicMock(return_value={})
            mock_modules["_reviewers"].resolve = unittest.mock.MagicMock(
                return_value={"model": "claude-haiku-4-5-20251001"}
            )
            mock_modules["_plan_dag"].extract_batch_index = unittest.mock.MagicMock(return_value=[])

            def mock_subprocess_run(*args, **kwargs):
                result = unittest.mock.MagicMock()
                result.returncode = 0
                if args and ("user.name" in str(args) or "user.email" in str(args)):
                    result.stdout = "Test User" if "user.name" in str(args) else "test@example.com"
                else:
                    result.stdout = ""
                result.stderr = ""
                return result

            def mock_resolve_task_path(project_root_arg, rel_path):
                return project_root / rel_path.lstrip("/")

            mock_modules["_subprocess_util"].run = unittest.mock.MagicMock(side_effect=mock_subprocess_run)
            mock_modules["_paths"].status_path = unittest.mock.MagicMock(
                return_value=project_root / "_mill/status.md"
            )
            mock_modules["_paths"].resolve_task_path = unittest.mock.MagicMock(
                side_effect=mock_resolve_task_path
            )
            mock_modules["_paths"].resolve_git_root = unittest.mock.MagicMock(return_value=project_root)
            mock_modules["_paths"].resolve_wiki_path = unittest.mock.MagicMock(return_value=project_root)

            with unittest.mock.patch.dict(sys.modules, mock_modules):
                spec = importlib.util.spec_from_file_location(
                    "millpy_fix_test2",
                    HUB / "plugins/mill/scripts/millpy-fix.py",
                )
                millpy_fix = importlib.util.module_from_spec(spec)

                mock_finalize = unittest.mock.MagicMock(return_value=0)

                sys.modules["millpy_fix_test2"] = millpy_fix
                with unittest.mock.patch.object(
                    millpy_fix, "finalize_from_output", mock_finalize, create=True
                ):
                    spec.loader.exec_module(millpy_fix)
                    millpy_fix.finalize_from_output = mock_finalize

                    rc = millpy_fix.main(
                        [
                            "--scope",
                            "holistic",
                            "--review-file",
                            str(review_file),
                            "--round",
                            "1",
                            "--stage",
                            "finalize",
                            "--agent-output",
                            str(agent_output_file),
                            "--session-id",
                            "sid-xyz",
                        ]
                    )

                    if mock_finalize.called:
                        call_args = mock_finalize.call_args
                        if call_args[1].get("start_sha") is None:
                            print("PASS: no start_sha -> start_sha=None passed")
                        else:
                            print(
                                f"FAIL: no start_sha - call_args={call_args}",
                                file=sys.stderr,
                            )
                            errors += 1
                    else:
                        print("FAIL: finalize_from_output not called", file=sys.stderr)
                        errors += 1
        except Exception as exc:
            print(f"FAIL: test 2 ({exc})", file=sys.stderr)
            errors += 1

    # Test 3: inferred success end-to-end (real git fixture)
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        start_sha = _setup_fixture(project_root)

        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "second"],
            check=True,
            capture_output=True,
        )

        agent_output_file = project_root / "agent_output.txt"
        agent_output_file.write_text("some prose output", encoding="utf-8")

        try:
            rc, captured = _capture_stdout(
                lambda: finalize_from_output(
                    agent_output_file,
                    project_root,
                    start_sha=start_sha,
                    session_id="sid-abc",
                )
            )
            data = json.loads(captured.strip())
            if (
                data["status"] == "success"
                and data.get("inferred") is True
                and data["session_id"] == "sid-abc"
            ):
                print("PASS: inferred success end-to-end (real git fixture)")
            else:
                print(f"FAIL: inferred success - got {data}", file=sys.stderr)
                errors += 1
        except Exception as exc:
            print(f"FAIL: test 3 ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Test 4: no start_sha disables inferred success
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        _setup_fixture(project_root)

        agent_output_file = project_root / "agent_output.txt"
        agent_output_file.write_text("prose only", encoding="utf-8")

        try:
            rc, captured = _capture_stdout(
                lambda: finalize_from_output(
                    agent_output_file,
                    project_root,
                    start_sha=None,
                    session_id=None,
                )
            )
            data = json.loads(captured.strip())
            if data["status"] == "stuck":
                print("PASS: no start_sha disables inferred success")
            else:
                print(
                    f"FAIL: no start_sha - expected stuck, got {data}",
                    file=sys.stderr,
                )
                errors += 1
        except Exception as exc:
            print(f"FAIL: test 4 ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All fix-finalize unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
