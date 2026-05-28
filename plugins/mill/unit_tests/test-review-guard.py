"""Unit tests for worktree_snapshot_guard and ReviewerOverstepError.

Covers:
  - Clean snapshot (no exception)
  - HEAD change detection
  - Porcelain (working tree) change detection
  - expected_paths filtering
  - ReviewerOverstepError class hierarchy
  - Error message formatting
  - Fast-forward HEAD advance tolerance
"""
from __future__ import annotations

import io
import subprocess
import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _review_common import (  # noqa: E402
    ReviewError,
    ReviewerOverstepError,
    worktree_snapshot_guard,
)


def _init_repo(tmp: Path) -> Path:
    """Initialize a git repo with a seed commit."""
    subprocess.run(
        ["git", "-C", str(tmp), "init"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp), "config", "user.name", "Test User"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp), "config", "user.email", "test@example.com"],
        check=True,
        capture_output=True,
    )
    seed_file = tmp / "seed.txt"
    seed_file.write_text("seed")
    subprocess.run(
        ["git", "-C", str(tmp), "add", "seed.txt"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp), "commit", "-m", "seed"],
        check=True,
        capture_output=True,
    )
    return tmp


def main() -> int:
    """Run all test cases. Return 0 on success, 1 on any failure."""
    errors = 0

    # Case A -- clean snapshot, no raise
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            _init_repo(tmp)
            with worktree_snapshot_guard(tmp):
                pass
        print("PASS: Case A -- clean snapshot, no raise")
    except Exception as e:
        print(f"FAIL: Case A -- {e}")
        errors += 1

    # Case B -- git commit inside (fast-forward) no raise, HEAD differs (now allowed)
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            _init_repo(tmp)
            stderr_capture = io.StringIO()
            old_stderr = sys.stderr
            try:
                sys.stderr = stderr_capture
                with worktree_snapshot_guard(tmp):
                    Path(tmp / "foo.txt").write_text("foo")
                    subprocess.run(
                        ["git", "-C", str(tmp), "add", "foo.txt"],
                        check=True,
                        capture_output=True,
                    )
                    subprocess.run(
                        ["git", "-C", str(tmp), "commit", "-m", "add foo"],
                        check=True,
                        capture_output=True,
                    )
            finally:
                sys.stderr = old_stderr
            stderr_output = stderr_capture.getvalue()
            if "fast-forward" in stderr_output:
                print("PASS: Case B -- fast-forward commit inside no raise, fast-forward warning emitted")
            else:
                print(f"FAIL: Case B -- expected fast-forward warning in stderr, got: {stderr_output!r}")
                errors += 1
    except ReviewerOverstepError as e:
        print(f"FAIL: Case B -- unexpected ReviewerOverstepError: {e}")
        errors += 1
    except Exception as e:
        print(f"FAIL: Case B -- unexpected error: {e}")
        errors += 1

    # Case C -- untracked file dropped raises (porcelain differs, HEAD same)
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            _init_repo(tmp)
            try:
                with worktree_snapshot_guard(tmp):
                    Path(tmp / "scratch.tmp").write_text("x")
                print("FAIL: Case C -- expected ReviewerOverstepError")
                errors += 1
            except ReviewerOverstepError as e:
                if e.before_sha == e.after_sha and "scratch.tmp" in e.porcelain_diff:
                    print("PASS: Case C -- untracked file raises (porcelain differs, HEAD same)")
                else:
                    print(f"FAIL: Case C -- SHAs or diff incorrect: {e}")
                    errors += 1
    except Exception as e:
        print(f"FAIL: Case C -- unexpected error: {e}")
        errors += 1

    # Case D -- modified tracked file raises (porcelain M, HEAD same)
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            _init_repo(tmp)
            try:
                with worktree_snapshot_guard(tmp):
                    Path(tmp / "seed.txt").write_text("seed modified")
                print("FAIL: Case D -- expected ReviewerOverstepError")
                errors += 1
            except ReviewerOverstepError as e:
                if e.before_sha == e.after_sha and "seed.txt" in e.porcelain_diff:
                    print("PASS: Case D -- modified tracked file raises (porcelain M, HEAD same)")
                else:
                    print(f"FAIL: Case D -- SHAs or diff incorrect: {e}")
                    errors += 1
    except Exception as e:
        print(f"FAIL: Case D -- unexpected error: {e}")
        errors += 1

    # Case E -- expected_paths filters allowed write
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            _init_repo(tmp)
            with worktree_snapshot_guard(tmp, expected_paths=["allowed/"]):
                (tmp / "allowed").mkdir(parents=True, exist_ok=True)
                Path(tmp / "allowed" / "output.md").write_text("x")
        print("PASS: Case E -- expected_paths filters allowed write")
    except Exception as e:
        print(f"FAIL: Case E -- {e}")
        errors += 1

    # Case F -- fast-forward commit inside expected_paths (now allowed)
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            _init_repo(tmp)
            stderr_capture = io.StringIO()
            old_stderr = sys.stderr
            try:
                sys.stderr = stderr_capture
                with worktree_snapshot_guard(tmp, expected_paths=["allowed/"]):
                    (tmp / "allowed").mkdir(parents=True, exist_ok=True)
                    Path(tmp / "allowed" / "output.md").write_text("x")
                    subprocess.run(
                        ["git", "-C", str(tmp), "add", "allowed/output.md"],
                        check=True,
                        capture_output=True,
                    )
                    subprocess.run(
                        ["git", "-C", str(tmp), "commit", "-m", "add output"],
                        check=True,
                        capture_output=True,
                    )
            finally:
                sys.stderr = old_stderr
            stderr_output = stderr_capture.getvalue()
            if "fast-forward" in stderr_output:
                print("PASS: Case F -- fast-forward commit inside expected_paths no raise, fast-forward warning emitted")
            else:
                print(f"FAIL: Case F -- expected fast-forward warning in stderr, got: {stderr_output!r}")
                errors += 1
    except ReviewerOverstepError as e:
        print(f"FAIL: Case F -- unexpected ReviewerOverstepError: {e}")
        errors += 1
    except Exception as e:
        print(f"FAIL: Case F -- unexpected error: {e}")
        errors += 1

    # Case G -- ReviewerOverstepError is a ReviewError subclass
    try:
        if issubclass(ReviewerOverstepError, ReviewError):
            try:
                raise ReviewerOverstepError("abcdef0123456789" * 2 + "01234567", "fedcba9876543210" * 2 + "76543210", "test")
            except ReviewError:
                print("PASS: Case G -- ReviewerOverstepError is ReviewError subclass")
            except Exception as e:
                print(f"FAIL: Case G -- not caught by ReviewError except: {e}")
                errors += 1
        else:
            print("FAIL: Case G -- ReviewerOverstepError is not a ReviewError subclass")
            errors += 1
    except Exception as e:
        print(f"FAIL: Case G -- unexpected error: {e}")
        errors += 1

    # Case H -- error message includes both SHAs and porcelain diff
    try:
        e = ReviewerOverstepError("abcdef0123456789" * 2 + "01234567", "fedcba9876543210" * 2 + "76543210", "  + ?? foo.txt")
        msg = str(e)
        if "abcdef01" in msg and "fedcba98" in msg and "?? foo.txt" in msg:
            print("PASS: Case H -- error message includes both SHAs and porcelain diff")
        else:
            print(f"FAIL: Case H -- missing parts in message: {msg!r}")
            errors += 1
    except Exception as e:
        print(f"FAIL: Case H -- unexpected error: {e}")
        errors += 1

    # Case I -- fast-forward commit that only removes prior dirt passes
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            _init_repo(tmp)
            # Create a dirty file before the guard
            Path(tmp / "dirty.txt").write_text("dirty")
            stderr_capture = io.StringIO()
            old_stderr = sys.stderr
            try:
                sys.stderr = stderr_capture
                with worktree_snapshot_guard(tmp):
                    # Add and commit the dirty file
                    subprocess.run(
                        ["git", "-C", str(tmp), "add", "dirty.txt"],
                        check=True,
                        capture_output=True,
                    )
                    subprocess.run(
                        ["git", "-C", str(tmp), "commit", "-m", "commit dirty"],
                        check=True,
                        capture_output=True,
                    )
            finally:
                sys.stderr = old_stderr
            stderr_output = stderr_capture.getvalue()
            if "fast-forward" in stderr_output:
                print("PASS: Case I -- fast-forward removing prior dirt passes")
            else:
                print(f"FAIL: Case I -- expected fast-forward warning, got: {stderr_output!r}")
                errors += 1
    except ReviewerOverstepError as e:
        print(f"FAIL: Case I -- unexpected ReviewerOverstepError: {e}")
        errors += 1
    except Exception as e:
        print(f"FAIL: Case I -- unexpected error: {e}")
        errors += 1

    # Case J -- git reset --hard to non-descendant raises
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            _init_repo(tmp)
            original_sha = subprocess.run(
                ["git", "-C", str(tmp), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            # Create a new orphan branch (no ancestor relationship)
            subprocess.run(
                ["git", "-C", str(tmp), "checkout", "--orphan", "other"],
                capture_output=True,
                check=True,
            )
            (tmp / ".keep").write_text("other", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(tmp), "add", ".keep"],
                capture_output=True,
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(tmp), "commit", "-m", "other"],
                capture_output=True,
                check=True,
            )
            other_sha = subprocess.run(
                ["git", "-C", str(tmp), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            # Reset back to original and start guard
            subprocess.run(
                ["git", "-C", str(tmp), "reset", "--hard", original_sha],
                capture_output=True,
                check=True,
            )
            try:
                with worktree_snapshot_guard(tmp):
                    # Reset to non-descendant
                    subprocess.run(
                        ["git", "-C", str(tmp), "reset", "--hard", other_sha],
                        capture_output=True,
                        check=True,
                    )
                print("FAIL: Case J -- expected ReviewerOverstepError for reset to non-descendant")
                errors += 1
            except ReviewerOverstepError as e:
                if e.before_sha != e.after_sha:
                    print("PASS: Case J -- reset to non-descendant raises")
                else:
                    print(f"FAIL: Case J -- HEAD should have changed: {e}")
                    errors += 1
    except Exception as e:
        print(f"FAIL: Case J -- unexpected error: {e}")
        errors += 1

    # Case K -- fast-forward commit PLUS new untracked file raises
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            _init_repo(tmp)
            try:
                with worktree_snapshot_guard(tmp):
                    # Create a new file and commit it
                    Path(tmp / "foo.txt").write_text("foo")
                    subprocess.run(
                        ["git", "-C", str(tmp), "add", "foo.txt"],
                        check=True,
                        capture_output=True,
                    )
                    subprocess.run(
                        ["git", "-C", str(tmp), "commit", "-m", "add foo"],
                        check=True,
                        capture_output=True,
                    )
                    # Also create a new untracked file (new dirt)
                    Path(tmp / "extra.txt").write_text("extra")
                print("FAIL: Case K -- expected ReviewerOverstepError for fast-forward + new dirt")
                errors += 1
            except ReviewerOverstepError as e:
                if "extra.txt" in e.porcelain_diff:
                    print("PASS: Case K -- fast-forward + new untracked file raises")
                else:
                    print(f"FAIL: Case K -- expected extra.txt in diff: {e}")
                    errors += 1
    except Exception as e:
        print(f"FAIL: Case K -- unexpected error: {e}")
        errors += 1

    if errors:
        return 1
    print("All review-guard tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
