"""Unit tests for the trailing-JSON contract for millpy-bg dispatched CLIs.

The completion-detection fallback depends on an invariant: every millpy-bg-dispatched
CLI MUST emit a parseable JSON line as its final stdout. These tests pin that invariant
by asserting the JSON contract at both the consumer (_bg._has_valid_json_result) and
emitter seams (_implementer_common._forward_output).
"""
from __future__ import annotations

import contextlib
import json
import sys
import unittest
import unittest.mock
from io import StringIO
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _bg  # noqa: E402
import _implementer_common  # noqa: E402


class TestJsonContractConsumer(unittest.TestCase):
    """Consumer acceptance: _has_valid_json_result recognizes valid envelopes."""

    def test_review_discussion_envelope(self) -> None:
        """Review discussion envelope (type=discussion) is recognized as valid JSON."""
        log_text = (
            "[mill-bg] WORKER PID=12345 START ...\n"
            "some output\n"
            '{"type": "discussion", "round": 1, "verdict": "APPROVE"}\n'
        )
        self.assertTrue(_bg._has_valid_json_result(log_text))

    def test_review_plan_envelope(self) -> None:
        """Review plan envelope (type=plan) is recognized as valid JSON."""
        log_text = (
            "[mill-bg] WORKER PID=12345 START ...\n"
            "some output\n"
            '{"type": "plan", "round": 2, "verdict": "GAPS_FOUND"}\n'
        )
        self.assertTrue(_bg._has_valid_json_result(log_text))

    def test_review_code_envelope(self) -> None:
        """Review code envelope (type=code) is recognized as valid JSON."""
        log_text = (
            "[mill-bg] WORKER PID=12345 START ...\n"
            "some output\n"
            '{"type": "code", "round": 1, "verdict": "REQUEST_CHANGES"}\n'
        )
        self.assertTrue(_bg._has_valid_json_result(log_text))

    def test_implementer_success_envelope(self) -> None:
        """Implementer success envelope is recognized as valid JSON."""
        log_text = (
            "[mill-bg] WORKER PID=12345 START ...\n"
            "some output\n"
            '{"status": "success", "commit_sha": "abc123def456", "session_id": "x"}\n'
        )
        self.assertTrue(_bg._has_valid_json_result(log_text))

    def test_stuck_transient_envelope(self) -> None:
        """Stuck (transient) envelope is recognized as valid JSON."""
        log_text = (
            "[mill-bg] WORKER PID=12345 START ...\n"
            "some output\n"
            '{"status": "stuck", "stuck_type": "transient", "reason": "timeout"}\n'
        )
        self.assertTrue(_bg._has_valid_json_result(log_text))

    def test_stuck_verify_envelope(self) -> None:
        """Stuck (verify) envelope is recognized as valid JSON."""
        log_text = (
            "[mill-bg] WORKER PID=12345 START ...\n"
            "some output\n"
            '{"status": "stuck", "stuck_type": "verify", "reason": "tests failed"}\n'
        )
        self.assertTrue(_bg._has_valid_json_result(log_text))

    def test_truncated_json_not_valid(self) -> None:
        """Truncated JSON is not recognized as valid."""
        log_text = (
            "[mill-bg] WORKER PID=12345 START ...\n"
            "some output\n"
            '{"status": "success", "commit_sha": "abc123\n'
        )
        self.assertFalse(_bg._has_valid_json_result(log_text))

    def test_malformed_json_not_valid(self) -> None:
        """Malformed JSON is not recognized as valid."""
        log_text = (
            "[mill-bg] WORKER PID=12345 START ...\n"
            "some output\n"
            '{"status": "success" commit_sha: "abc123"}\n'
        )
        self.assertFalse(_bg._has_valid_json_result(log_text))

    def test_no_json_not_valid(self) -> None:
        """Log with no JSON is not recognized as valid."""
        log_text = (
            "[mill-bg] WORKER PID=12345 START ...\n"
            "some output\n"
            "normal text output\n"
        )
        self.assertFalse(_bg._has_valid_json_result(log_text))


class TestJsonContractEmitter(unittest.TestCase):
    """Emitter seam guard: _forward_output emits valid JSON for success and stuck branches."""

    def test_forward_output_success_with_json_in_output(self) -> None:
        """_forward_output extracts and enriches success envelope from output."""
        agent_output = (
            "some log output\n"
            '{"status": "success", "commit_sha": "old_sha", "session_id": "test-123"}\n'
        )
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        output_buffer = StringIO()
        with contextlib.redirect_stdout(output_buffer):
            with unittest.mock.patch.object(_implementer_common._subprocess_util, "run") as mock_run:
                # Mock git rev-parse HEAD
                mock_run_result = unittest.mock.MagicMock()
                mock_run_result.returncode = 0
                mock_run_result.stdout = "new_sha_123\n"
                mock_run.return_value = mock_run_result
                with unittest.mock.patch.object(
                    _implementer_common._cleanliness, "compute_scope_violations", return_value=[]
                ):
                    _implementer_common._forward_output(agent_output, project_root)
        emitted = output_buffer.getvalue().strip()
        try:
            parsed = json.loads(emitted)
            self.assertEqual(parsed["status"], "success")
            self.assertEqual(parsed["session_id"], "test-123")
        except json.JSONDecodeError as e:
            self.fail(f"_forward_output did not emit valid JSON: {emitted!r}, error: {e}")

    def test_forward_output_stuck_transient(self) -> None:
        """_forward_output correctly handles stuck (transient) envelope."""
        agent_output = (
            "some log output\n"
            '{"status": "stuck", "stuck_type": "transient", "reason": "quota exceeded"}\n'
        )
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        output_buffer = StringIO()
        with contextlib.redirect_stdout(output_buffer):
            with unittest.mock.patch.object(_implementer_common._subprocess_util, "run") as mock_run:
                mock_run_result = unittest.mock.MagicMock()
                mock_run_result.returncode = 0
                mock_run_result.stdout = "sha_123\n"
                mock_run.return_value = mock_run_result
                with unittest.mock.patch.object(
                    _implementer_common._cleanliness, "compute_scope_violations", return_value=[]
                ):
                    _implementer_common._forward_output(agent_output, project_root)
        emitted = output_buffer.getvalue().strip()
        try:
            parsed = json.loads(emitted)
            self.assertEqual(parsed["status"], "stuck")
            self.assertEqual(parsed["stuck_type"], "transient")
        except json.JSONDecodeError as e:
            self.fail(f"_forward_output did not emit valid JSON: {emitted!r}, error: {e}")

    def test_forward_output_stuck_verify(self) -> None:
        """_forward_output correctly handles stuck (verify) envelope."""
        agent_output = (
            "test output\n"
            '{"status": "stuck", "stuck_type": "verify", "reason": "test case failed"}\n'
        )
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        output_buffer = StringIO()
        with contextlib.redirect_stdout(output_buffer):
            with unittest.mock.patch.object(_implementer_common._subprocess_util, "run") as mock_run:
                mock_run_result = unittest.mock.MagicMock()
                mock_run_result.returncode = 0
                mock_run_result.stdout = "sha_456\n"
                mock_run.return_value = mock_run_result
                with unittest.mock.patch.object(
                    _implementer_common._cleanliness, "compute_scope_violations", return_value=[]
                ):
                    _implementer_common._forward_output(agent_output, project_root)
        emitted = output_buffer.getvalue().strip()
        try:
            parsed = json.loads(emitted)
            self.assertEqual(parsed["status"], "stuck")
            self.assertEqual(parsed["stuck_type"], "verify")
        except json.JSONDecodeError as e:
            self.fail(f"_forward_output did not emit valid JSON: {emitted!r}, error: {e}")

    def test_forward_output_stuck_no_json_fallback(self) -> None:
        """When no JSON is found in output, _forward_output emits stuck sentinel."""
        agent_output = (
            "some output without JSON\n"
            "no structured report\n"
        )
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        output_buffer = StringIO()
        with contextlib.redirect_stdout(output_buffer):
            with unittest.mock.patch.object(
                _implementer_common._cleanliness, "compute_scope_violations", return_value=[]
            ):
                _implementer_common._forward_output(agent_output, project_root)
        emitted = output_buffer.getvalue().strip()
        try:
            parsed = json.loads(emitted)
            self.assertEqual(parsed["status"], "stuck")
            self.assertEqual(parsed["stuck_type"], "logic")
            self.assertIn("no structured report", parsed.get("reason", ""))
        except json.JSONDecodeError as e:
            self.fail(f"_forward_output did not emit valid JSON fallback: {emitted!r}, error: {e}")


if __name__ == "__main__":
    unittest.main()
