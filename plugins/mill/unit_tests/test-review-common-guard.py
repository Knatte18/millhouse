"""Unit tests for worktree_snapshot_guard in _review_common.py."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SCRIPTS = _HERE.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import _review_common  # noqa: E402


class TestWorktreeSnapshotGuard(unittest.TestCase):
    """Test worktree_snapshot_guard behavior across all four exception/state cells."""

    def setUp(self) -> None:
        """Create a temporary git repository for each test."""
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.repo_path = Path(self.tmp_dir.name)

        # Initialize git repo
        result = subprocess.run(
            ["git", "init", "--initial-branch=main", str(self.repo_path)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            subprocess.run(
                ["git", "init", str(self.repo_path)],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(self.repo_path), "checkout", "-b", "main"],
                capture_output=True,
            )

        # Configure git user
        subprocess.run(
            ["git", "-C", str(self.repo_path), "config", "user.email", "test@test.com"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(self.repo_path), "config", "user.name", "Test"],
            check=True,
            capture_output=True,
        )

        # Create initial commit
        (self.repo_path / ".keep").write_text("", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(self.repo_path), "add", ".keep"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(self.repo_path), "commit", "-m", "init"],
            check=True,
            capture_output=True,
        )

    def tearDown(self) -> None:
        """Clean up temporary directory."""
        self.tmp_dir.cleanup()

    def test_clean_exit_clean_state(self) -> None:
        """Body runs without raising; state unchanged. Expect: no exception."""
        with _review_common.worktree_snapshot_guard(self.repo_path):
            pass
        # If we reach here, no exception was raised (test passes).

    def test_clean_exit_state_mutated(self) -> None:
        """Body runs without raising; state is mutated. Expect: ReviewerOverstepError."""
        with self.assertRaises(_review_common.ReviewerOverstepError):
            with _review_common.worktree_snapshot_guard(self.repo_path):
                # Create an empty commit to mutate state
                subprocess.run(
                    ["git", "-C", str(self.repo_path), "commit", "--allow-empty", "-m", "x"],
                    check=True,
                    capture_output=True,
                )

    def test_inner_raises_clean_state(self) -> None:
        """Body raises; state unchanged. Expect: RuntimeError propagates unchanged."""
        with self.assertRaises(RuntimeError) as ctx:
            with _review_common.worktree_snapshot_guard(self.repo_path):
                raise RuntimeError("inner sentinel")
        self.assertEqual(str(ctx.exception), "inner sentinel")

    def test_inner_raises_state_mutated(self) -> None:
        """Body mutates state then raises. Expect: ReviewerOverstepError with chained RuntimeError."""
        with self.assertRaises(_review_common.ReviewerOverstepError) as ctx:
            with _review_common.worktree_snapshot_guard(self.repo_path):
                # Mutate state
                subprocess.run(
                    ["git", "-C", str(self.repo_path), "commit", "--allow-empty", "-m", "x"],
                    check=True,
                    capture_output=True,
                )
                # Then raise
                raise RuntimeError("inner sentinel")

        # Verify the exception was chained
        self.assertIsNotNone(ctx.exception.__cause__)
        self.assertIsInstance(ctx.exception.__cause__, RuntimeError)
        self.assertEqual(str(ctx.exception.__cause__), "inner sentinel")


if __name__ == "__main__":
    unittest.main()
