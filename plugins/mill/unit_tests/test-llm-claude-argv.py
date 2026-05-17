"""Unit tests for _build_argv argv shape — regression guard for issue #335.

This test ensures that the sandbox-defeating bug is fixed: when allowed_tools
is an empty string (as passed by run_bulk), --allowedTools "" is emitted
explicitly so the subprocess inherits the empty allow-list, not the CLI's
default full tool surface.

Tests cover:
  1. Empty allowed_tools: emits --allowedTools "" + --disallowedTools deny-list
  2. Populated allowed_tools (read-only): emits --allowedTools + --disallowedTools
  3. Full tool set (implementer): emits --allowedTools + no --disallowedTools
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _llm_claude import _build_argv  # noqa: E402


class TestBuildArgvShape(unittest.TestCase):
    """Test the argv shape of _build_argv for allow-list/deny-list combinations."""

    def test_empty_allowed_tools_emits_explicit_empty_string(self) -> None:
        """Empty allowed_tools must emit --allowedTools "" explicitly.

        Regression test for issue #335: if allowed_tools is falsy (empty string),
        the old `if allowed_tools` test would omit --allowedTools entirely, and
        the subprocess would inherit Claude CLI's default full tool surface.
        The fix uses `if allowed_tools is not None` so the empty string is
        emitted explicitly.
        """
        argv = _build_argv(model="m", effort=None, allowed_tools="")

        # Check that --allowedTools "" is present as a contiguous pair
        self.assertIn("--allowedTools", argv)
        tools_idx = argv.index("--allowedTools")
        self.assertEqual(argv[tools_idx + 1], "", "must emit --allowedTools ''")

        # Check that --disallowedTools deny-list is present (defence-in-depth)
        self.assertIn("--disallowedTools", argv)
        deny_idx = argv.index("--disallowedTools")
        self.assertEqual(argv[deny_idx + 1], "Edit,Write,Bash,NotebookEdit")

    def test_read_only_tools_emits_allow_and_deny_lists(self) -> None:
        """Populated allow-list (read-only) must emit both allow and deny lists."""
        argv = _build_argv(model="m", effort=None, allowed_tools="Read,Grep,Glob")

        # Check that --allowedTools is present with the correct value
        self.assertIn("--allowedTools", argv)
        tools_idx = argv.index("--allowedTools")
        self.assertEqual(argv[tools_idx + 1], "Read,Grep,Glob")

        # Check that --disallowedTools deny-list is present (defence-in-depth)
        self.assertIn("--disallowedTools", argv)
        deny_idx = argv.index("--disallowedTools")
        self.assertEqual(argv[deny_idx + 1], "Edit,Write,Bash,NotebookEdit")

    def test_full_tool_set_emits_allow_only(self) -> None:
        """Full tool set (implementer) must emit allow-list, NOT deny-list.

        When allowed_tools includes all mutating tools, the deny-list is
        redundant and not emitted (optimisation).
        """
        argv = _build_argv(
            model="m",
            effort=None,
            allowed_tools="Read,Edit,Write,Bash,Grep,Glob,Skill",
        )

        # Check that --allowedTools is present with the full set
        self.assertIn("--allowedTools", argv)
        tools_idx = argv.index("--allowedTools")
        self.assertEqual(argv[tools_idx + 1], "Read,Edit,Write,Bash,Grep,Glob,Skill")

        # Check that --disallowedTools is NOT present (no defence needed)
        self.assertNotIn("--disallowedTools", argv)


def main() -> int:
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestBuildArgvShape)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
