"""Unit tests for plugins/mill/scripts/_archive_tag.py.

Covers:
  - create_or_resolve: no existing tag -- creates new archive tag
  - create_or_resolve: same SHA -- returns noop action
  - create_or_resolve: ancestor SHA -- force updates tag to new SHA
  - create_or_resolve: divergent SHA -- moves old tag aside with -01 suffix
  - create_or_resolve: multiple divergences -- increments suffix to -02, -03, etc.
  - create_or_resolve: push outcomes (push_failed/push_error) for each of the
    four actions, using a bare-remote fixture with a pre-receive hook that
    deterministically accepts or rejects specific ref pushes.
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

    def _get_head_sha(self, worktree: Path) -> str:
        """Get the current HEAD SHA."""
        result = subprocess.run(
            ["git", "-C", str(worktree), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    def _init_bare_remote(
        self, worktree: Path, tmp: Path, reject_ref_names: set[str] | None = None
    ) -> Path:
        """
        Create a bare "origin" remote for worktree, optionally rejecting specific refs.

        When reject_ref_names is given, installs a pre-receive hook that reads each
        "<old> <new> <refname>" line git feeds it on stdin and exits non-zero (after
        printing "rejected: <refname>" to stderr) if any line's refname is in
        reject_ref_names, else exits 0. This gives deterministic, per-push
        accept/reject control without depending on --force-with-lease's
        remote-tracking-ref semantics (this fixture never runs `git fetch`, so real
        lease-conflict detection would be git-version-dependent).

        Returns the bare repo path.
        """
        remote_path = tmp / "remote.git"
        subprocess.run(
            ["git", "init", "--bare", str(remote_path)],
            check=True,
            capture_output=True,
        )
        if reject_ref_names:
            hook_path = remote_path / "hooks" / "pre-receive"
            reject_list = " ".join(sorted(reject_ref_names))
            hook_script = (
                "#!/bin/sh\n"
                "while read old new refname; do\n"
                "  for rejected in {}; do\n"
                '    if [ "$refname" = "$rejected" ]; then\n'
                '      echo "rejected: $refname" >&2\n'
                "      exit 1\n"
                "    fi\n"
                "  done\n"
                "done\n"
                "exit 0\n"
            ).format(reject_list)
            hook_path.write_text(hook_script)
            hook_path.chmod(0o755)
        subprocess.run(
            ["git", "-C", str(worktree), "remote", "add", "origin", str(remote_path)],
            check=True,
            capture_output=True,
        )
        return remote_path

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

            # Create an orphan branch (completely unrelated history)
            subprocess.run(
                ["git", "-C", str(worktree), "checkout", "--orphan", "orphan-branch"],
                check=True,
                capture_output=True,
            )
            # Clear the staging area
            subprocess.run(
                ["git", "-C", str(worktree), "rm", "-rf", "."],
                check=False,
                capture_output=True,
            )
            # Create a new commit on the orphan branch
            (worktree / "orphan-file.txt").write_text("orphan commit")
            subprocess.run(
                ["git", "-C", str(worktree), "add", "orphan-file.txt"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(worktree), "commit", "-m", "orphan commit"],
                check=True,
                capture_output=True,
            )
            new_sha = self._get_head_sha(worktree)

            result = _archive_tag.create_or_resolve(worktree, "test-slug", "HEAD")

            self.assertEqual(result["action"], "moved_aside")
            self.assertEqual(result["tag"], "archive/test-slug")
            self.assertEqual(result["moved_aside_to"], "archive/test-slug-01")

            # Verify old tag moved to -01 and points at original SHA
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

            # First divergence: create -01 using orphan branch
            subprocess.run(
                ["git", "-C", str(worktree), "checkout", "--orphan", "orphan1"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(worktree), "rm", "-rf", "."],
                check=False,
                capture_output=True,
            )
            (worktree / "orphan1-file.txt").write_text("orphan1")
            subprocess.run(
                ["git", "-C", str(worktree), "add", "orphan1-file.txt"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(worktree), "commit", "-m", "orphan1"],
                check=True,
                capture_output=True,
            )
            sha_after_first = self._get_head_sha(worktree)

            result1 = _archive_tag.create_or_resolve(worktree, "test-slug", "HEAD")
            self.assertEqual(result1["moved_aside_to"], "archive/test-slug-01")

            # Second divergence: create -02 using another orphan branch
            subprocess.run(
                ["git", "-C", str(worktree), "checkout", "--orphan", "orphan2"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(worktree), "rm", "-rf", "."],
                check=False,
                capture_output=True,
            )
            (worktree / "orphan2-file.txt").write_text("orphan2")
            subprocess.run(
                ["git", "-C", str(worktree), "add", "orphan2-file.txt"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(worktree), "commit", "-m", "orphan2"],
                check=True,
                capture_output=True,
            )
            sha_after_second = self._get_head_sha(worktree)

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

    def test_created_push_success_reports_no_failure(self) -> None:
        """When the remote accepts the push, created action reports push_failed=False."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            worktree, _ = self._init_repo(tmp_path / "work")
            self._init_bare_remote(worktree, tmp_path)

            result = _archive_tag.create_or_resolve(worktree, "test-slug", "HEAD")

            self.assertEqual(result["action"], "created")
            self.assertIs(result["push_failed"], False)
            self.assertIsNone(result["push_error"])

    def test_noop_reports_no_push_attempted(self) -> None:
        """The noop action never attempts a push, so it always reports push_failed=False."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            worktree, _ = self._init_repo(tmp_path / "work")

            # Create the tag pointing at HEAD -- no remote needed since noop never pushes.
            subprocess.run(
                ["git", "-C", str(worktree), "tag", "archive/test-slug", "HEAD"],
                check=True,
                capture_output=True,
            )

            result = _archive_tag.create_or_resolve(worktree, "test-slug", "HEAD")

            self.assertEqual(result["action"], "noop")
            self.assertIs(result["push_failed"], False)
            self.assertIsNone(result["push_error"])

    def test_created_push_rejected_reports_push_failed_true(self) -> None:
        """When the remote's pre-receive hook rejects the new tag, push_failed is True."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            worktree, _ = self._init_repo(tmp_path / "work")
            self._init_bare_remote(
                worktree, tmp_path, reject_ref_names={"refs/tags/archive/test-slug"}
            )

            result = _archive_tag.create_or_resolve(worktree, "test-slug", "HEAD")

            self.assertEqual(result["action"], "created")
            self.assertIs(result["push_failed"], True)
            self.assertTrue(result["push_error"])

    def test_force_update_push_rejected_reports_push_failed_true(self) -> None:
        """When the remote rejects the force-with-lease push, push_failed is True."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            worktree, _ = self._init_repo(tmp_path / "work")

            # Create tag pointing at ancestor, then advance HEAD -- mirrors
            # test_ancestor_sha_force_updates's setup.
            subprocess.run(
                ["git", "-C", str(worktree), "tag", "archive/test-slug", "HEAD"],
                check=True,
                capture_output=True,
            )
            self._make_commit(worktree, "commit2")
            self._make_commit(worktree, "commit3")

            self._init_bare_remote(
                worktree, tmp_path, reject_ref_names={"refs/tags/archive/test-slug"}
            )

            result = _archive_tag.create_or_resolve(worktree, "test-slug", "HEAD")

            self.assertEqual(result["action"], "force_update")
            self.assertIs(result["push_failed"], True)
            self.assertTrue(result["push_error"])

    def test_moved_aside_partial_push_failure_names_which_tag(self) -> None:
        """When only the primary-tag push is rejected, push_error names "primary" only."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            worktree, _ = self._init_repo(tmp_path / "work")

            # Create tag, then diverge via an orphan branch -- mirrors
            # test_divergent_sha_moves_aside_to_01's setup.
            subprocess.run(
                ["git", "-C", str(worktree), "tag", "archive/test-slug", "HEAD"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(worktree), "checkout", "--orphan", "orphan-branch"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(worktree), "rm", "-rf", "."],
                check=False,
                capture_output=True,
            )
            (worktree / "orphan-file.txt").write_text("orphan commit")
            subprocess.run(
                ["git", "-C", str(worktree), "add", "orphan-file.txt"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(worktree), "commit", "-m", "orphan commit"],
                check=True,
                capture_output=True,
            )

            # Reject only the primary tag; the moved-aside tag push is allowed.
            self._init_bare_remote(
                worktree, tmp_path, reject_ref_names={"refs/tags/archive/test-slug"}
            )

            result = _archive_tag.create_or_resolve(worktree, "test-slug", "HEAD")

            self.assertEqual(result["action"], "moved_aside")
            self.assertEqual(result["moved_aside_to"], "archive/test-slug-01")
            self.assertIs(result["push_failed"], True)
            self.assertIn("primary", result["push_error"])
            self.assertNotIn("moved-aside", result["push_error"])

    def test_moved_aside_both_pushes_rejected_combines_errors(self) -> None:
        """When both moved-aside and primary pushes are rejected, both are named in push_error."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            worktree, _ = self._init_repo(tmp_path / "work")

            subprocess.run(
                ["git", "-C", str(worktree), "tag", "archive/test-slug", "HEAD"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(worktree), "checkout", "--orphan", "orphan-branch"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(worktree), "rm", "-rf", "."],
                check=False,
                capture_output=True,
            )
            (worktree / "orphan-file.txt").write_text("orphan commit")
            subprocess.run(
                ["git", "-C", str(worktree), "add", "orphan-file.txt"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(worktree), "commit", "-m", "orphan commit"],
                check=True,
                capture_output=True,
            )

            self._init_bare_remote(
                worktree,
                tmp_path,
                reject_ref_names={
                    "refs/tags/archive/test-slug",
                    "refs/tags/archive/test-slug-01",
                },
            )

            result = _archive_tag.create_or_resolve(worktree, "test-slug", "HEAD")

            self.assertEqual(result["action"], "moved_aside")
            self.assertIs(result["push_failed"], True)
            self.assertIn("primary", result["push_error"])
            self.assertIn("moved-aside", result["push_error"])


if __name__ == "__main__":
    unittest.main()
