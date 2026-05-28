"""Unit tests for review CLI exit-code contract (#338).

Tests that the three review CLIs (discussion, code, plan) maintain the
correct exit-code contract:
- exit 0 + ERROR envelope: engine-internal failure
- exit 1 + ERROR envelope + stderr: pre-launch failure
- exit 0 + APPROVE envelope: success

Uses unittest.mock.patch to stub all pre-launch dependencies and the
backend run() function, avoiding real LLM calls.
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Add scripts dir to path for imports
scripts_dir = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))


def _load_cli_module(cli_name: str):
    """Load a CLI module by name (e.g., 'discussion', 'code', 'plan').

    Returns the loaded module object with main() function.
    """
    filename = f"millpy-review-{cli_name}.py"
    spec = importlib.util.spec_from_file_location(
        f"millpy_review_{cli_name}",
        scripts_dir / filename,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestReviewCliErrorEnvelope(unittest.TestCase):
    """Tests for review CLI exit-code contract across discussion/code/plan."""

    def setUp(self):
        """Create a temporary directory for test fixtures."""
        self.tempdir = tempfile.TemporaryDirectory()
        self.tempdir_path = Path(self.tempdir.name)

    def tearDown(self):
        """Clean up temporary directory."""
        self.tempdir.cleanup()

    def _run_cli_test(
        self,
        cli_name: str,
        backend_return: dict | None = None,
        raise_find_slug: bool = False,
        skip_validate_flag: bool = True,
    ) -> tuple[int, str, str]:
        """Run a CLI module and capture exit code + stdout + stderr.

        Args:
            cli_name: "discussion", "code", or "plan"
            backend_return: dict to return from backend.run() (mocked), or None to skip mocking
            raise_find_slug: if True, make find_active_slug raise ReviewError
            skip_validate_flag: for plan CLI, whether to use --skip-validate

        Returns:
            (exit_code, stdout, stderr)
        """
        # Load the CLI module
        cli_module = _load_cli_module(cli_name)

        # Determine backend module name
        backend_module_name = f"_review_{cli_name}"

        # Build argv
        argv = []
        if cli_name == "plan" and skip_validate_flag:
            argv.append("--skip-validate")

        # Capture stdout/stderr
        captured_stdout = io.StringIO()
        captured_stderr = io.StringIO()

        with patch("sys.stdout", captured_stdout), \
             patch("sys.stderr", captured_stderr), \
             patch("_paths.resolve_wiki_path", return_value=self.tempdir_path), \
             patch("_paths.resolve_git_root", return_value=self.tempdir_path), \
             patch("_review_common.load_config", return_value={"paths": {}, "roles": {}}), \
             patch("_reviewers.load", return_value={}), \
             patch("_reviewers.validate_role_refs", return_value=None), \
             patch("pathlib.Path.cwd", return_value=self.tempdir_path):

            # Mock the backend run() function if backend_return is provided
            if backend_return is not None:
                with patch(f"{backend_module_name}.run", return_value=backend_return):
                    # Mock find_active_slug if needed
                    if raise_find_slug:
                        from _review_common import ReviewError
                        with patch("_review_common.find_active_slug", side_effect=ReviewError("pre-launch test")):
                            exit_code = cli_module.main(argv)
                    else:
                        with patch("_review_common.find_active_slug", return_value="test-slug"):
                            exit_code = cli_module.main(argv)
            else:
                # Mock find_active_slug if raising
                if raise_find_slug:
                    from _review_common import ReviewError
                    with patch("_review_common.find_active_slug", side_effect=ReviewError("pre-launch test")):
                        exit_code = cli_module.main(argv)
                else:
                    with patch("_review_common.find_active_slug", return_value="test-slug"):
                        exit_code = cli_module.main(argv)

        return exit_code, captured_stdout.getvalue(), captured_stderr.getvalue()

    def test_discussion_engine_internal_error(self):
        """Discussion CLI: engine-internal ERROR returns exit 0 with ERROR envelope."""
        from _review_common import ReviewResult

        backend_return = ReviewResult(
            type="discussion",
            round=1,
            verdict="ERROR",
            blocking_count=0,
            reviews=[{
                "scope": "holistic",
                "verdict": "ERROR",
                "file": None,
                "error": "LLM failed",
                "session_id": None,
            }],
        )

        exit_code, stdout, stderr = self._run_cli_test(
            "discussion",
            backend_return=backend_return,
        )

        self.assertEqual(exit_code, 0, f"Expected exit 0, got {exit_code}. stderr: {stderr}")
        result = json.loads(stdout)
        self.assertEqual(result["verdict"], "ERROR")

    def test_discussion_pre_launch_error(self):
        """Discussion CLI: pre-launch error returns exit 1 with ERROR envelope + stderr."""
        exit_code, stdout, stderr = self._run_cli_test(
            "discussion",
            raise_find_slug=True,
        )

        self.assertEqual(exit_code, 1, f"Expected exit 1, got {exit_code}")
        result = json.loads(stdout)
        self.assertEqual(result["verdict"], "ERROR")
        self.assertIn("pre-launch test", stderr)

    def test_discussion_success(self):
        """Discussion CLI: success returns exit 0 with APPROVE envelope."""
        from _review_common import ReviewResult

        backend_return = ReviewResult(
            type="discussion",
            round=1,
            verdict="APPROVE",
            blocking_count=0,
            reviews=[{
                "scope": "holistic",
                "verdict": "APPROVE",
                "file": "/tmp/x.md",
                "session_id": "abc",
            }],
        )

        exit_code, stdout, stderr = self._run_cli_test(
            "discussion",
            backend_return=backend_return,
        )

        self.assertEqual(exit_code, 0)
        result = json.loads(stdout)
        self.assertEqual(result["verdict"], "APPROVE")

    def test_code_engine_internal_error(self):
        """Code CLI: engine-internal ERROR returns exit 0 with ERROR envelope."""
        from _review_common import ReviewResult

        backend_return = ReviewResult(
            type="code",
            round=1,
            verdict="ERROR",
            blocking_count=0,
            reviews=[{
                "scope": "batch",
                "verdict": "ERROR",
                "file": None,
                "error": "parse_verdict failed",
                "session_id": "xyz",
            }],
        )

        exit_code, stdout, stderr = self._run_cli_test(
            "code",
            backend_return=backend_return,
        )

        self.assertEqual(exit_code, 0, f"Expected exit 0, got {exit_code}. stderr: {stderr}")
        result = json.loads(stdout)
        self.assertEqual(result["verdict"], "ERROR")

    def test_code_pre_launch_error(self):
        """Code CLI: pre-launch error returns exit 1 with ERROR envelope + stderr."""
        exit_code, stdout, stderr = self._run_cli_test(
            "code",
            raise_find_slug=True,
        )

        self.assertEqual(exit_code, 1)
        result = json.loads(stdout)
        self.assertEqual(result["verdict"], "ERROR")
        self.assertIn("pre-launch test", stderr)

    def test_code_success(self):
        """Code CLI: success returns exit 0 with APPROVE envelope."""
        from _review_common import ReviewResult

        backend_return = ReviewResult(
            type="code",
            round=1,
            verdict="APPROVE",
            blocking_count=0,
            reviews=[{
                "scope": "batch",
                "verdict": "APPROVE",
                "file": "/tmp/code.md",
                "session_id": "def",
            }],
        )

        exit_code, stdout, stderr = self._run_cli_test(
            "code",
            backend_return=backend_return,
        )

        self.assertEqual(exit_code, 0)
        result = json.loads(stdout)
        self.assertEqual(result["verdict"], "APPROVE")

    def test_plan_engine_internal_error(self):
        """Plan CLI: engine-internal ERROR returns exit 0 with ERROR envelope."""
        from _review_common import ReviewResult

        backend_return = ReviewResult(
            type="plan",
            round=1,
            verdict="ERROR",
            blocking_count=0,
            reviews=[{
                "scope": "holistic",
                "round": 1,
                "verdict": "ERROR",
                "blocking_count": 0,
                "file": str(self.tempdir_path / "plan.md"),
                "error": "parse_verdict failed",
                "session_id": "ghi",
            }],
        )

        exit_code, stdout, stderr = self._run_cli_test(
            "plan",
            backend_return=backend_return,
            skip_validate_flag=True,
        )

        self.assertEqual(exit_code, 0, f"Expected exit 0, got {exit_code}. stderr: {stderr}")
        result = json.loads(stdout)
        self.assertEqual(result["verdict"], "ERROR")

    def test_plan_pre_launch_error(self):
        """Plan CLI: pre-launch error returns exit 1 with ERROR envelope + stderr."""
        exit_code, stdout, stderr = self._run_cli_test(
            "plan",
            raise_find_slug=True,
            skip_validate_flag=True,
        )

        self.assertEqual(exit_code, 1)
        result = json.loads(stdout)
        self.assertEqual(result["verdict"], "ERROR")
        self.assertIn("pre-launch test", stderr)

    def test_plan_success(self):
        """Plan CLI: success returns exit 0 with APPROVE envelope."""
        from _review_common import ReviewResult

        backend_return = ReviewResult(
            type="plan",
            round=1,
            verdict="APPROVE",
            blocking_count=0,
            reviews=[{
                "scope": "holistic",
                "round": 1,
                "verdict": "APPROVE",
                "blocking_count": 0,
                "file": str(self.tempdir_path / "plan.md"),
                "session_id": "jkl",
            }],
        )

        exit_code, stdout, stderr = self._run_cli_test(
            "plan",
            backend_return=backend_return,
            skip_validate_flag=True,
        )

        self.assertEqual(exit_code, 0)
        result = json.loads(stdout)
        self.assertEqual(result["verdict"], "APPROVE")

    def test_plan_uncaught_exception(self):
        """Plan CLI: uncaught exception from backend returns exit 1 with ERROR envelope."""
        cli_module = _load_cli_module("plan")
        argv = ["--skip-validate"]
        captured_stdout = io.StringIO()
        captured_stderr = io.StringIO()

        with patch("sys.stdout", captured_stdout), \
             patch("sys.stderr", captured_stderr), \
             patch("_paths.resolve_wiki_path", return_value=self.tempdir_path), \
             patch("_paths.resolve_git_root", return_value=self.tempdir_path), \
             patch("_review_common.load_config", return_value={"paths": {}, "roles": {}}), \
             patch("_reviewers.load", return_value={}), \
             patch("_reviewers.validate_role_refs", return_value=None), \
             patch("pathlib.Path.cwd", return_value=self.tempdir_path), \
             patch("_review_common.find_active_slug", return_value="test-slug"), \
             patch("_review_plan.run", side_effect=RuntimeError("backend failure")):
            exit_code = cli_module.main(argv)

        self.assertEqual(exit_code, 1)
        result = json.loads(captured_stdout.getvalue())
        self.assertEqual(result["verdict"], "ERROR")
        self.assertEqual(result["type"], "plan")
        self.assertIn("unhandled review error", result["reviews"][0]["error"])


if __name__ == "__main__":
    unittest.main()
