"""Unit tests for the no-op commit path in _wiki.write_commit_push.

Tests that write_commit_push correctly detects when no changes are staged
(even when files are rewritten with identical content) and skips the commit
and push without raising an error.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _wiki  # noqa: E402


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


def _get_head_sha(wiki_path: Path) -> str:
    """Get the current HEAD SHA."""
    result = _git(["rev-parse", "HEAD"], wiki_path)
    return result.stdout.strip()


def main() -> int:
    passed = 0
    failed = 0

    def ok(name: str) -> None:
        nonlocal passed
        passed += 1
        msg = f"PASS: {name}\n"
        sys.stdout.buffer.write(msg.encode("utf-8", errors="backslashreplace"))
        sys.stdout.buffer.flush()

    def fail(name: str, exc: Exception) -> None:
        nonlocal failed
        failed += 1
        msg = f"FAIL: {name}: {exc}\n"
        sys.stderr.buffer.write(msg.encode("utf-8", errors="backslashreplace"))
        sys.stderr.buffer.flush()

    # --- (1) test_noop_unchanged_file ---
    try:
        with tempfile.TemporaryDirectory() as tmp_str:
            wiki = Path(tmp_str)
            _setup_wiki(wiki)
            initial_sha = _get_head_sha(wiki)

            # Stage and try to commit without changing the file
            _wiki.write_commit_push(wiki, ["Home.md"], "no-op commit", slug="test")

            final_sha = _get_head_sha(wiki)
            assert initial_sha == final_sha, \
                f"HEAD must not advance for unchanged file: {initial_sha} != {final_sha}"

        ok("test_noop_unchanged_file: no commit when file unchanged")
    except Exception as exc:
        fail("test_noop_unchanged_file", exc)

    # --- (2) test_noop_rewrite_identical_content ---
    try:
        with tempfile.TemporaryDirectory() as tmp_str:
            wiki = Path(tmp_str)
            _setup_wiki(wiki)
            initial_sha = _get_head_sha(wiki)

            # Get current content
            home_file = wiki / "Home.md"
            original_content = home_file.read_text(encoding="utf-8")

            # Rewrite with identical content (changes mtime but not content)
            home_file.write_text(original_content, encoding="utf-8")

            # Stage and try to commit
            _wiki.write_commit_push(wiki, ["Home.md"], "rewrite identical", slug="test")

            final_sha = _get_head_sha(wiki)
            assert initial_sha == final_sha, \
                f"HEAD must not advance for identical-content rewrite: {initial_sha} != {final_sha}"

        ok("test_noop_rewrite_identical_content: no commit for identical-content rewrite")
    except Exception as exc:
        fail("test_noop_rewrite_identical_content", exc)

    # --- (3) test_real_change_commits_normally ---
    try:
        with tempfile.TemporaryDirectory() as tmp_str:
            wiki = Path(tmp_str)
            _setup_wiki(wiki)
            initial_sha = _get_head_sha(wiki)

            # Modify the file with different content
            home_file = wiki / "Home.md"
            home_file.write_text("# Wiki\n\nNew content\n", encoding="utf-8")

            # Stage and commit
            _wiki.write_commit_push(wiki, ["Home.md"], "real change", slug="test")

            final_sha = _get_head_sha(wiki)
            assert initial_sha != final_sha, \
                f"HEAD must advance for real change: {initial_sha} == {final_sha}"

            # Verify the commit message
            result = _git(["log", "-1", "--format=%B"], wiki)
            commit_msg = result.stdout.strip()
            assert commit_msg == "real change", \
                f"Commit message mismatch: {commit_msg!r} != 'real change'"

        ok("test_real_change_commits_normally: HEAD advances for real change")
    except Exception as exc:
        fail("test_real_change_commits_normally", exc)

    print(f"\n{passed} passed, {failed} failed.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
