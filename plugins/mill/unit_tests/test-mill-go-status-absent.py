"""Unit tests for plugins/mill/scripts/_phase_gate.absent_status_halt_message.

Tests the absent_status_halt_message helper which generates readable error
messages when mill-go Entry Step 5 encounters a missing _mill/status.md
(indicating mill-merge cleanup ran but did not complete).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _phase_gate  # noqa: E402


class TestAbsentStatusHaltMessage(unittest.TestCase):
    """Test cases for absent_status_halt_message(task, slug)."""

    def test_ready_to_merge_routes_to_mill_merge(self):
        """Task with ready-to-merge status should suggest mill-merge."""
        task = {"status": "ready-to-merge"}
        slug = "foo"
        msg = _phase_gate.absent_status_halt_message(task, slug)
        self.assertIn("_mill/status.md", msg)
        self.assertIn("/mill-merge", msg)
        self.assertIn(slug, msg)

    def test_pr_pending_routes_to_mill_merge(self):
        """Task with pr-pending status should suggest mill-merge."""
        task = {"status": "pr-pending"}
        slug = "foo"
        msg = _phase_gate.absent_status_halt_message(task, slug)
        self.assertIn("_mill/status.md", msg)
        self.assertIn("/mill-merge", msg)
        self.assertIn(slug, msg)

    def test_done_says_already_merged(self):
        """Task with done status should indicate it's already merged."""
        task = {"status": "done"}
        slug = "foo"
        msg = _phase_gate.absent_status_halt_message(task, slug)
        self.assertIn("already merged", msg)
        self.assertIn(slug, msg)

    def test_task_none_says_not_in_home_md(self):
        """Task=None should indicate missing task in Home.md."""
        task = None
        slug = "foo"
        msg = _phase_gate.absent_status_halt_message(task, slug)
        self.assertIn("not in Home.md", msg)
        self.assertIn(slug, msg)

    def test_unknown_status_surfaces_value(self):
        """Unknown status should show the status value and ask for manual inspection."""
        task = {"status": "discussing"}
        slug = "foo"
        msg = _phase_gate.absent_status_halt_message(task, slug)
        self.assertIn("discussing", msg)
        self.assertIn("inspect manually", msg)


def main() -> int:
    """Run all tests and return exit code."""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestAbsentStatusHaltMessage)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
