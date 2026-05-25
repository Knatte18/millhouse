"""Unit tests for the no-op commit path in wiki._sync.commit_push.

Tests that commit_push correctly detects when no changes are staged
(even when files are rewritten with identical content) and skips the commit
and push without raising an error.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from wiki._sync import commit_push  # noqa: E402


def _git(argv: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run git command and return the result."""
    return subprocess.run(
        ["git"] + argv,
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def _setup_wiki(wiki_path: Path) -> None:
    """Initialize a git repo with one commit and configure user."""
    wiki_path.mkdir(parents=True, exist_ok=True)
    _git(["init", "--initial-branch=main", str(wiki_path)], wiki_path.parent)
    _git(["config", "user.email", "test@test.com"], wiki_path)
    _git(["config", "user.name", "Test"], wiki_path)
    # Create an initial commit so HEAD has a SHA
    (wiki_path / "Home.md").write_text("# Wiki\n", encoding="utf-8")
    _git(["add", "Home.md"], wiki_path)
    _git(["commit", "-m", "init"], wiki_path)
    # Bare-clone "origin" so commit_push's git push has a destination.
    bare = wiki_path.parent / f"{wiki_path.name}.git"
    subprocess.run(["git", "init", "--bare", str(bare)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(wiki_path), "remote", "add", "origin", str(bare)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(wiki_path), "push", "-u", "origin", "HEAD"], check=True, capture_output=True)


def _get_head_sha(wiki_path: Path) -> str:
    """Get the current HEAD SHA."""
    result = _git(["rev-parse", "HEAD"], wiki_path)
    return result.stdout.strip()


class TestWikiNoop(unittest.TestCase):
    """Test the no-op commit detection in wiki._sync.commit_push."""

    def test_noop_unchanged_file(self) -> None:
        """Test that unchanged files do not trigger a commit."""
        with tempfile.TemporaryDirectory() as tmp_str:
            wiki = Path(tmp_str)
            _setup_wiki(wiki)
            initial_sha = _get_head_sha(wiki)

            # Call commit_push without changing the file
            commit_push(wiki, ["Home.md"], "no-op commit")

            final_sha = _get_head_sha(wiki)
            self.assertEqual(
                initial_sha,
                final_sha,
                f"HEAD must not advance for unchanged file: {initial_sha} != {final_sha}",
            )

    def test_noop_rewrite_identical_content(self) -> None:
        """Test that rewriting with identical content does not trigger a commit."""
        with tempfile.TemporaryDirectory() as tmp_str:
            wiki = Path(tmp_str)
            _setup_wiki(wiki)
            initial_sha = _get_head_sha(wiki)

            # Get current content
            home_file = wiki / "Home.md"
            original_content = home_file.read_text(encoding="utf-8")

            # Rewrite with identical content (changes mtime but not content)
            home_file.write_text(original_content, encoding="utf-8")

            # Call commit_push
            commit_push(wiki, ["Home.md"], "rewrite identical")

            final_sha = _get_head_sha(wiki)
            self.assertEqual(
                initial_sha,
                final_sha,
                f"HEAD must not advance for identical-content rewrite: {initial_sha} != {final_sha}",
            )

    def test_real_change_commits_normally(self) -> None:
        """Test that real changes are committed normally."""
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            wiki = tmp / "wiki"

            # Set up the wiki
            _setup_wiki(wiki)

            initial_sha = _get_head_sha(wiki)

            # Modify the file with different content
            home_file = wiki / "Home.md"
            home_file.write_text("# Wiki\n\nNew content\n", encoding="utf-8")

            # Call commit_push
            commit_push(wiki, ["Home.md"], "real change")

            final_sha = _get_head_sha(wiki)
            self.assertNotEqual(
                initial_sha,
                final_sha,
                f"HEAD must advance for real change: {initial_sha} == {final_sha}",
            )

            # Verify the commit message
            result = _git(["log", "-1", "--format=%B"], wiki)
            commit_msg = result.stdout.strip()
            self.assertEqual(
                commit_msg,
                "real change",
                f"Commit message mismatch: {commit_msg!r} != 'real change'",
            )


if __name__ == "__main__":
    unittest.main()
