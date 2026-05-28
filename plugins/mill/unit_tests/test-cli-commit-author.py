"""Unit tests for _subprocess_util.git_commit helper.

Tests that CLI state commits can pin author name/email explicitly,
independent of worktree-local git config drift.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _subprocess_util as _subprocess_util_mod  # noqa: E402


def main() -> int:
    errors = 0

    # Test 1: explicit author overrides local config
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            # Initialize repo with local config pollution
            _subprocess_util_mod.run(["git", "init"], cwd=tmp)
            _subprocess_util_mod.run(
                ["git", "config", "user.email", "test@test.com"],
                cwd=tmp
            )
            _subprocess_util_mod.run(
                ["git", "config", "user.name", "Test Pollution"],
                cwd=tmp
            )
            # Write and add a test file
            (tmp / "test.txt").write_text("test content")
            _subprocess_util_mod.run(["git", "add", "test.txt"], cwd=tmp)

            # Commit with explicit author
            result = _subprocess_util_mod.git_commit(
                tmp,
                "feat: thing",
                name="Real Author",
                email="real@example.com"
            )
            assert result.returncode == 0, f"git_commit failed: {result.stderr}"

            # Verify commit author
            log_result = _subprocess_util_mod.run(
                ["git", "-C", str(tmp), "log", "-1", "--format=%an<%ae>"]
            )
            author_line = log_result.stdout.strip()
            assert author_line == "Real Author<real@example.com>", \
                f"Expected 'Real Author<real@example.com>', got '{author_line}'"
            print("PASS: explicit author overrides local config")
    except Exception as e:
        print(f"FAIL: test_explicit_author_overrides_local_config: {e}")
        errors += 1

    # Test 2: returns CompletedProcess shape
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            _subprocess_util_mod.run(["git", "init"], cwd=tmp)
            _subprocess_util_mod.run(
                ["git", "config", "user.email", "test@test.com"],
                cwd=tmp
            )
            _subprocess_util_mod.run(
                ["git", "config", "user.name", "Test User"],
                cwd=tmp
            )
            (tmp / "test.txt").write_text("test")
            _subprocess_util_mod.run(["git", "add", "test.txt"], cwd=tmp)

            result = _subprocess_util_mod.git_commit(
                tmp,
                "chore: test",
                name="Author",
                email="author@test.com"
            )
            assert isinstance(result, subprocess.CompletedProcess)
            assert hasattr(result, "returncode")
            assert hasattr(result, "stdout")
            assert hasattr(result, "stderr")
            print("PASS: returns CompletedProcess shape")
    except Exception as e:
        print(f"FAIL: test_returns_completed_process_shape: {e}")
        errors += 1

    # Test 3: message with special chars preserved
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            _subprocess_util_mod.run(["git", "init"], cwd=tmp)
            _subprocess_util_mod.run(
                ["git", "config", "user.email", "test@test.com"],
                cwd=tmp
            )
            _subprocess_util_mod.run(
                ["git", "config", "user.name", "Test User"],
                cwd=tmp
            )
            (tmp / "test.txt").write_text("test")
            _subprocess_util_mod.run(["git", "add", "test.txt"], cwd=tmp)

            message = "chore(merge): pre-merge cleanup"
            result = _subprocess_util_mod.git_commit(
                tmp,
                message,
                name="Author",
                email="author@test.com"
            )
            assert result.returncode == 0

            # Verify message
            log_result = _subprocess_util_mod.run(
                ["git", "-C", str(tmp), "log", "-1", "--format=%s"]
            )
            commit_msg = log_result.stdout.strip()
            assert commit_msg == message, \
                f"Expected '{message}', got '{commit_msg}'"
            print("PASS: message with special chars preserved")
    except Exception as e:
        print(f"FAIL: test_message_with_special_chars_preserved: {e}")
        errors += 1

    # Test 4: local config unchanged
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            _subprocess_util_mod.run(["git", "init"], cwd=tmp)
            _subprocess_util_mod.run(
                ["git", "config", "user.email", "test@test.com"],
                cwd=tmp
            )
            _subprocess_util_mod.run(
                ["git", "config", "user.name", "Test Pollution"],
                cwd=tmp
            )
            (tmp / "test.txt").write_text("test")
            _subprocess_util_mod.run(["git", "add", "test.txt"], cwd=tmp)

            result = _subprocess_util_mod.git_commit(
                tmp,
                "feat: test",
                name="Real Author",
                email="real@example.com"
            )
            assert result.returncode == 0

            # Verify local config unchanged
            email_result = _subprocess_util_mod.run(
                ["git", "-C", str(tmp), "config", "--get", "user.email"]
            )
            local_email = email_result.stdout.strip()
            assert local_email == "test@test.com", \
                f"Expected 'test@test.com', got '{local_email}'"
            print("PASS: local config unchanged")
    except Exception as e:
        print(f"FAIL: test_local_config_unchanged: {e}")
        errors += 1

    if errors == 0:
        print(f"\n{4} tests passed")
        return 0
    else:
        print(f"\n{errors} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
