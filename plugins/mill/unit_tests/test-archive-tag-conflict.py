"""Unit tests for plugins/mill/scripts/_archive_tag.py.

Covers:
  - create_or_resolve: no existing tag -- creates new archive tag
  - create_or_resolve: same SHA -- returns noop action
  - create_or_resolve: ancestor SHA -- force updates tag to new SHA
  - create_or_resolve: divergent SHA -- moves old tag aside with -01 suffix
  - create_or_resolve: multiple divergences -- increments suffix to -02, -03, etc.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _archive_tag  # noqa: E402


class TestArchiveTagConflict(unittest.TestCase):
    """Test _archive_tag.create_or_resolve against various tag-conflict scenarios."""

    def _init_repo(self, tmp: Path) -> tuple[Path, str]:
        """Initialize a bare git repo and return (worktree, initial_sha)."""
        subprocess.run(
            ["git", "init", str(tmp)],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(tmp), "config", "user.email", "test@example.com"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(tmp), "config", "user.name", "Test User"],
            check=True,
            capture_output=True,
        )
        # Create initial commit
        (tmp / "file.txt").write_text("initial")
        subprocess.run(
            ["git", "-C", str(tmp), "add", "file.txt"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(tmp), "commit", "-m", "initial"],
            check=True,
            capture_output=True,
        )
        # Get initial SHA
        result = subprocess.run(
            ["git", "-C", str(tmp), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        return tmp, result.stdout.strip()

    def _make_commit(self, worktree: Path, message: str) -> str:
        """Create a new commit and return its SHA."""
        (worktree / "file.txt").write_text(message)
        subprocess.run(
            ["git", "-C", str(worktree), "add", "file.txt"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(worktree), "commit", "-m", message],
            check=True,
            capture_output=True,
        )
        result = subprocess.run(
            ["git", "-C", str(worktree), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    def test_no_existing_tag_creates(self) -> None:
        """When no tag exists, create_or_resolve creates the tag."""
        with tempfile.TemporaryDirectory() as tmp:
            worktree, _ = self._init_repo(Path(tmp))

            result = _archive_tag.create_or_resolve(worktree, "test-slug", "HEAD")

            self.assertEqual(result["action"], "created")
            self.assertEqual(result["tag"], "archive/test-slug")
            self.assertIsNone(result["moved_aside_to"])

            # Verify tag exists
            tag_list = subprocess.run(
                ["git", "-C", str(worktree), "tag", "-l", "archive/test-slug"],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("archive/test-slug", tag_list.stdout)

    def test_same_sha_is_noop(self) -> None:
        """When tag exists pointing at same SHA, return noop."""
        with tempfile.TemporaryDirectory() as tmp:
            worktree, initial_sha = self._init_repo(Path(tmp))

            # Create the tag pointing at HEAD
            subprocess.run(
                ["git", "-C", str(worktree), "tag", "archive/test-slug", "HEAD"],
                check=True,
                capture_output=True,
            )

            result = _archive_tag.create_or_resolve(worktree, "test-slug", "HEAD")

            self.assertEqual(result["action"], "noop")
            self.assertEqual(result["tag"], "archive/test-slug")
            self.assertIsNone(result["moved_aside_to"])

            # Verify tag still points to initial SHA
            tag_sha = subprocess.run(
                ["git", "-C", str(worktree), "rev-parse", "archive/test-slug"],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(tag_sha.stdout.strip(), initial_sha)

    def test_ancestor_sha_force_updates(self) -> None:
        """When tag points at ancestor commit, force update to new HEAD."""
        with tempfile.TemporaryDirectory() as tmp:
            worktree, ancestor_sha = self._init_repo(Path(tmp))

            # Create tag pointing at ancestor
            subprocess.run(
                ["git", "-C", str(worktree), "tag", "archive/test-slug", "HEAD"],
                check=True,
                capture_output=True,
            )

            # Create new commits
            self._make_commit(worktree, "commit2")
            new_sha = self._make_commit(worktree, "commit3")

            result = _archive_tag.create_or_resolve(worktree, "test-slug", "HEAD")

            self.assertEqual(result["action"], "force_update")
            self.assertEqual(result["tag"], "archive/test-slug")
            self.assertIsNone(result["moved_aside_to"])

            # Verify tag now points to new HEAD
            tag_sha = subprocess.run(
                ["git", "-C", str(worktree), "rev-parse", "archive/test-slug"],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(tag_sha.stdout.strip(), new_sha)

    def test_divergent_sha_moves_aside_to_01(self) -> None:
        """When tag points at divergent commit, move it aside and create new tag."""
        with tempfile.TemporaryDirectory() as tmp:
            worktree, initial_sha = self._init_repo(Path(tmp))

            # Create tag pointing at initial commit
            subprocess.run(
                ["git", "-C", str(worktree), "tag", "archive/test-slug", "HEAD"],
                check=True,
                capture_output=True,
            )

            # Create a new branch from initial and commit to it
            subprocess.run(
                ["git", "-C", str(worktree), "checkout", "-b", "newbranch", "HEAD"],
                check=True,
                capture_output=True,
            )
            divergent_sha = self._make_commit(worktree, "divergent")

            # Switch back to main and make different commits
            subprocess.run(
                ["git", "-C", str(worktree), "checkout", "-"],
                check=True,
                capture_output=True,
            )
            self._make_commit(worktree, "mainline2")
            new_sha = self._make_commit(worktree, "mainline3")

            result = _archive_tag.create_or_resolve(worktree, "test-slug", "HEAD")

            self.assertEqual(result["action"], "moved_aside")
            self.assertEqual(result["tag"], "archive/test-slug")
            self.assertEqual(result["moved_aside_to"], "archive/test-slug-01")

            # Verify old tag moved to -01 and points at divergent SHA
            old_tag_sha = subprocess.run(
                ["git", "-C", str(worktree), "rev-parse", "archive/test-slug-01"],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(old_tag_sha.stdout.strip(), initial_sha)

            # Verify new tag points at new HEAD
            new_tag_sha = subprocess.run(
                ["git", "-C", str(worktree), "rev-parse", "archive/test-slug"],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(new_tag_sha.stdout.strip(), new_sha)

    def test_second_divergence_moves_aside_to_02(self) -> None:
        """When archive/<slug>-01 exists, next divergence creates -02."""
        with tempfile.TemporaryDirectory() as tmp:
            worktree, initial_sha = self._init_repo(Path(tmp))

            # Create initial tag
            subprocess.run(
                ["git", "-C", str(worktree), "tag", "archive/test-slug", "HEAD"],
                check=True,
                capture_output=True,
            )

            # First divergence: create -01
            subprocess.run(
                ["git", "-C", str(worktree), "checkout", "-b", "branch1", "HEAD"],
                check=True,
                capture_output=True,
            )
            self._make_commit(worktree, "branch1-commit")
            subprocess.run(
                ["git", "-C", str(worktree), "checkout", "-"],
                check=True,
                capture_output=True,
            )
            sha_after_first = self._make_commit(worktree, "main-commit1")

            result1 = _archive_tag.create_or_resolve(worktree, "test-slug", "HEAD")
            self.assertEqual(result1["moved_aside_to"], "archive/test-slug-01")

            # Second divergence: create -02
            subprocess.run(
                ["git", "-C", str(worktree), "checkout", "-b", "branch2", "HEAD"],
                check=True,
                capture_output=True,
            )
            self._make_commit(worktree, "branch2-commit")
            subprocess.run(
                ["git", "-C", str(worktree), "checkout", "-"],
                check=True,
                capture_output=True,
            )
            sha_after_second = self._make_commit(worktree, "main-commit2")

            result2 = _archive_tag.create_or_resolve(worktree, "test-slug", "HEAD")

            self.assertEqual(result2["action"], "moved_aside")
            self.assertEqual(result2["tag"], "archive/test-slug")
            self.assertEqual(result2["moved_aside_to"], "archive/test-slug-02")

            # Verify -02 points at what was previously the current tag
            tag_02_sha = subprocess.run(
                ["git", "-C", str(worktree), "rev-parse", "archive/test-slug-02"],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(tag_02_sha.stdout.strip(), sha_after_first)

            # Verify main tag points at new HEAD
            main_tag_sha = subprocess.run(
                ["git", "-C", str(worktree), "rev-parse", "archive/test-slug"],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(main_tag_sha.stdout.strip(), sha_after_second)


if __name__ == "__main__":
    unittest.main()
