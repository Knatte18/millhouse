"""Unit tests for plugins/mill/scripts/_treeguard.py."""
from __future__ import annotations

import contextlib
import io
import subprocess
import sys
import tempfile
import unittest.mock
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _treeguard import check_and_restore  # noqa: E402

# Seeded file contents, keyed by hub-relative path -- shared by every scenario that builds a fresh seeded repo via _seed_repo.
_SEED_FILES = {
    "_mill/status.md": "status content\n",
    "_mill/discussion.md": "discussion content\n",
    "_mill/briefs/x.md": "brief x content\n",
    "_mill/reviews/y.md": "review y content\n",
}


def _run_git(args: list[str], cwd: Path) -> None:
    """Run a git command in cwd, raising on failure (fixture setup only)."""
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _seed_repo(repo_root: Path) -> None:
    """
    Initialize a real git repo at repo_root with a committed _mill/ tree.

    Creates status.md, discussion.md, briefs/x.md, reviews/y.md under repo_root/_mill (per
    _SEED_FILES), configures a throwaway user.email/ user.name so the commit succeeds without
    relying on global git config, then commits the whole tree with `git add -A && git commit -m
    "seed"`.
    """
    _run_git(["init"], repo_root)
    _run_git(["config", "user.email", "treeguard-test@example.com"], repo_root)
    _run_git(["config", "user.name", "Treeguard Test"], repo_root)

    for rel_path, content in _SEED_FILES.items():
        full_path = repo_root / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")

    _run_git(["add", "-A"], repo_root)
    _run_git(["commit", "-m", "seed"], repo_root)


def main() -> int:
    try:
        # --- Scenario 1: no deletion -> not triggered, nothing touched ---
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            _seed_repo(repo_root)

            result = check_and_restore(repo_root)
            assert result["triggered"] is False, f"expected not triggered, got {result!r}"
            assert result["restored_paths"] == [], f"expected [], got {result['restored_paths']!r}"
            assert result["timestamp"] is None, f"expected None, got {result['timestamp']!r}"
            for rel_path, content in _SEED_FILES.items():
                full_path = repo_root / rel_path
                assert full_path.exists(), f"{rel_path} unexpectedly missing"
                assert full_path.read_text(encoding="utf-8") == content, f"{rel_path} content changed"
        print("PASS: no deletion -> not triggered, all seeded files untouched")

        # --- Scenario 2: single file deleted -> restored ---
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            _seed_repo(repo_root)
            (repo_root / "_mill" / "status.md").unlink()

            result = check_and_restore(repo_root)
            assert result["triggered"] is True, f"expected triggered, got {result!r}"
            assert result["restored_paths"] == ["_mill/status.md"], (
                f"expected ['_mill/status.md'], got {result['restored_paths']!r}"
            )
            restored = repo_root / "_mill" / "status.md"
            assert restored.exists(), "status.md was not restored to disk"
            assert restored.read_text(encoding="utf-8") == _SEED_FILES["_mill/status.md"], (
                "restored status.md content does not match committed blob"
            )
        print("PASS: single file deleted -> restored")

        # --- Scenario 3: multiple files deleted across subdirectories -> both restored ---
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            _seed_repo(repo_root)
            (repo_root / "_mill" / "status.md").unlink()
            (repo_root / "_mill" / "briefs" / "x.md").unlink()

            result = check_and_restore(repo_root)
            assert result["triggered"] is True, f"expected triggered, got {result!r}"
            assert result["restored_paths"] == ["_mill/briefs/x.md", "_mill/status.md"], (
                f"expected both paths sorted, got {result['restored_paths']!r}"
            )
            for rel_path in ("_mill/status.md", "_mill/briefs/x.md"):
                full_path = repo_root / rel_path
                assert full_path.exists(), f"{rel_path} was not restored"
                assert full_path.read_text(encoding="utf-8") == _SEED_FILES[rel_path], (
                    f"restored {rel_path} content does not match committed blob"
                )
        print("PASS: multiple files deleted across subdirectories -> both restored in one call")

        # --- Scenario 4: staged deletion ("D ") -> restored and tracked again ---
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            _seed_repo(repo_root)
            _run_git(["rm", "_mill/discussion.md"], repo_root)

            result = check_and_restore(repo_root)
            assert result["triggered"] is True, f"expected triggered, got {result!r}"
            restored = repo_root / "_mill" / "discussion.md"
            assert restored.exists(), "discussion.md was not restored to disk"
            assert restored.read_text(encoding="utf-8") == _SEED_FILES["_mill/discussion.md"], (
                "restored discussion.md content does not match committed blob"
            )

            # Confirm the file is tracked and unmodified again -- no leftover porcelain entry for it.
            status_result = subprocess.run(
                ["git", "status", "--porcelain", "--", "_mill/discussion.md"],
                cwd=repo_root,
                check=True,
                capture_output=True,
                text=True,
            )
            assert status_result.stdout == "", (
                f"expected no porcelain entry for discussion.md, got {status_result.stdout!r}"
            )
        print("PASS: staged deletion ('D ') -> restored to disk and tracked again as unmodified")

        # --- Scenario 5: untracked file alongside a real deletion -> untracked file untouched ---
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            _seed_repo(repo_root)
            scratch = repo_root / "_mill" / "scratch-leftover.txt"
            scratch.write_text("never committed\n", encoding="utf-8")
            (repo_root / "_mill" / "status.md").unlink()

            result = check_and_restore(repo_root)
            assert result["triggered"] is True, f"expected triggered, got {result!r}"
            assert (repo_root / "_mill" / "status.md").exists(), "status.md was not restored"
            assert scratch.exists(), "untracked scratch file was removed"
            assert scratch.read_text(encoding="utf-8") == "never committed\n", (
                "untracked scratch file content changed"
            )
            assert "_mill/scratch-leftover.txt" not in result["restored_paths"], (
                f"untracked file leaked into restored_paths: {result['restored_paths']!r}"
            )
        print("PASS: untracked file alongside a real deletion -> untracked file untouched, never restored")

        # --- Scenario 6: legitimate uncommitted modification alongside a real deletion ---
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            _seed_repo(repo_root)
            status_md = repo_root / "_mill" / "status.md"
            with open(status_md, "a", encoding="utf-8") as f:
                f.write("uncommitted appended line\n")
            captured_mtime = status_md.stat().st_mtime
            captured_content = status_md.read_text(encoding="utf-8")
            (repo_root / "_mill" / "reviews" / "y.md").unlink()

            result = check_and_restore(repo_root)
            assert result["triggered"] is True, f"expected triggered, got {result!r}"
            restored = repo_root / "_mill" / "reviews" / "y.md"
            assert restored.exists(), "reviews/y.md was not restored"
            assert restored.read_text(encoding="utf-8") == _SEED_FILES["_mill/reviews/y.md"], (
                "restored reviews/y.md content does not match committed blob"
            )
            assert status_md.stat().st_mtime == captured_mtime, (
                "status.md mtime changed -- check_and_restore touched an ' M' file"
            )
            assert status_md.read_text(encoding="utf-8") == captured_content, (
                "status.md content changed -- check_and_restore reverted an uncommitted append"
            )
            assert result["restored_paths"] == ["_mill/reviews/y.md"], (
                f"expected only reviews/y.md restored, got {result['restored_paths']!r}"
            )
        print("PASS: legitimate uncommitted modification alongside a real deletion -> modification left alone")

        # --- Scenario 7: failed restore is never reported as triggered ---
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            _seed_repo(repo_root)
            (repo_root / "_mill" / "status.md").unlink()

            with unittest.mock.patch("_treeguard._subprocess_util.run") as mock_run:
                mock_run.return_value = unittest.mock.Mock(
                    returncode=1, stdout="", stderr="mock: simulated total checkout failure"
                )
                result = check_and_restore(repo_root)

            assert result["triggered"] is False, f"expected not triggered, got {result!r}"
            assert result["restored_paths"] == [], f"expected [], got {result['restored_paths']!r}"
            assert not (repo_root / "_mill" / "status.md").exists(), (
                "status.md should still be absent after a total restore failure"
            )
        print("PASS: failed restore (non-zero returncode, no disk change) -> never reported as triggered")

        # --- Scenario 8: nested-hub layout rebases git-root-relative porcelain paths ---
        with tempfile.TemporaryDirectory() as tmp:
            git_root = Path(tmp)
            hub_root = git_root / "hub"
            for rel_path, content in _SEED_FILES.items():
                full_path = hub_root / rel_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content, encoding="utf-8")

            _run_git(["init"], git_root)
            _run_git(["config", "user.email", "treeguard-test@example.com"], git_root)
            _run_git(["config", "user.name", "Treeguard Test"], git_root)
            _run_git(["add", "-A"], git_root)
            _run_git(["commit", "-m", "seed"], git_root)

            (hub_root / "_mill" / "status.md").unlink()

            result = check_and_restore(hub_root, "_mill", git_root=git_root)
            assert result["triggered"] is True, f"expected triggered, got {result!r}"
            restored = hub_root / "_mill" / "status.md"
            assert restored.exists(), "status.md was not restored under hub_root"
            assert restored.read_text(encoding="utf-8") == _SEED_FILES["_mill/status.md"], (
                "restored status.md content does not match committed blob"
            )
            assert result["restored_paths"] == ["_mill/status.md"], (
                f"expected hub-relative path, got {result['restored_paths']!r}"
            )
        print("PASS: nested-hub layout rebases git-root-relative porcelain paths onto the hub before matching")

        # --- Scenario 9: git_root=None behaves like a flat layout ---
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            _seed_repo(repo_root)
            (repo_root / "_mill" / "status.md").unlink()

            result = check_and_restore(repo_root, "_mill", git_root=None)
            assert result["triggered"] is True, f"expected triggered, got {result!r}"
            assert result["restored_paths"] == ["_mill/status.md"], (
                f"expected ['_mill/status.md'], got {result['restored_paths']!r}"
            )
            restored = repo_root / "_mill" / "status.md"
            assert restored.exists(), "status.md was not restored to disk"
            assert restored.read_text(encoding="utf-8") == _SEED_FILES["_mill/status.md"], (
                "restored status.md content does not match committed blob"
            )
        print("PASS: git_root=None explicit behaves identically to a flat layout, not a TypeError")

        # --- Scenario 10: partial restore is reported accurately, not upgraded to full success ---
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            _seed_repo(repo_root)
            (repo_root / "_mill" / "status.md").unlink()
            (repo_root / "_mill" / "reviews" / "y.md").unlink()

            def _partial_restore_side_effect(argv, cwd=None, **kwargs):
                # Simulate git's real per-pathspec partial-success behavior: only reviews/y.md actually gets restored from HEAD, while status.md is deliberately left missing.
                subprocess.run(
                    ["git", "checkout", "HEAD", "--", "_mill/reviews/y.md"],
                    cwd=cwd,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                return unittest.mock.Mock(
                    returncode=1, stdout="", stderr="mock: simulated partial checkout failure"
                )

            stderr_buf = io.StringIO()
            with unittest.mock.patch("_treeguard._subprocess_util.run") as mock_run:
                mock_run.side_effect = _partial_restore_side_effect
                with contextlib.redirect_stderr(stderr_buf):
                    result = check_and_restore(repo_root)

            assert result["triggered"] is True, f"expected triggered, got {result!r}"
            assert result["restored_paths"] == ["_mill/reviews/y.md"], (
                f"expected only the actually-restored path, got {result['restored_paths']!r}"
            )
            assert not (repo_root / "_mill" / "status.md").exists(), (
                "status.md should still be missing after a partial restore"
            )
            assert "_mill/status.md" in stderr_buf.getvalue(), (
                f"expected still-missing path in stderr diagnostic, got {stderr_buf.getvalue()!r}"
            )
        print("PASS: partial restore reports only the actually-restored path, surfaces the rest via stderr")

        print("All _treeguard unit tests passed.")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
