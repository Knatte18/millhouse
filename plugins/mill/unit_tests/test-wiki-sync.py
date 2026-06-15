"""Unit tests for wiki._sync git operations layer.

Covers: pull() on up-to-date; atomic_write() writes and reads back;
commit_push() after changes; commit_push() idempotent on no changes;
non-fast-forward rebase retry; path_guard validation.

Uses a real tempfile bare repo + working clone (fast, deterministic, no mocks).
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _safe_rmtree  # noqa: E402, F401
from wiki._sync import (  # noqa: E402
    pull,
    atomic_write,
    commit_push,
    path_guard,
    _run,
    _git_env,
)
from wiki import WikiPathError, WikiPushError  # noqa: E402


def _run_quiet(args: list[str], cwd: Path) -> int:
    """Run a command quietly and return the exit code."""
    result = subprocess.run(
        args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )
    return result.returncode


def main() -> int:
    passed = 0
    failed = 0

    def ok(name: str) -> None:
        nonlocal passed
        passed += 1
        print(f"PASS: {name}")

    def fail(name: str, exc: Exception) -> None:
        nonlocal failed
        failed += 1
        print(f"FAIL: {name}: {exc}", file=sys.stderr)

    # Set up a temp bare repo + working clone
    tmp = Path(tempfile.mkdtemp())
    try:
        bare = tmp / "bare.git"
        clone = tmp / "clone"

        # Initialize bare repo with main branch
        subprocess.run(
            ["git", "init", "--bare", "-b", "main", str(bare)],
            check=True,
            capture_output=True,
        )

        # Initialize clone with main branch
        clone.mkdir(parents=True)
        subprocess.run(["git", "init", "-b", "main", str(clone)], check=True, capture_output=True)

        # Configure git user in clone
        subprocess.run(
            ["git", "-C", str(clone), "config", "user.email", "test@test.com"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(clone), "config", "user.name", "Test User"],
            check=True,
            capture_output=True,
        )

        # Add remote pointing to bare
        subprocess.run(
            ["git", "-C", str(clone), "remote", "add", "origin", str(bare)],
            check=True,
            capture_output=True,
        )

        # Initial commit
        (clone / "Home.md").write_text("# Home\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(clone), "add", "Home.md"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(clone), "commit", "-m", "init"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(clone), "push", "-u", "origin", "main"],
            check=True,
            capture_output=True,
        )

        # --- (a) pull() on up-to-date (does not raise) ---
        try:
            pull(clone)
            ok("pull() on up-to-date (does not raise)")
        except Exception as exc:
            fail("pull() on up-to-date (does not raise)", exc)

        # --- (b) atomic_write writes content, readable back ---
        try:
            atomic_write(clone, "test.md", "test content")
            content = (clone / "test.md").read_text(encoding="utf-8")
            assert content == "test content"
            ok("atomic_write writes content, readable back")
        except Exception as exc:
            fail("atomic_write writes content, readable back", exc)

        # --- (c) commit_push after changes succeeds ---
        try:
            (clone / "Home.md").write_text("# Home Updated\n", encoding="utf-8")
            commit_push(clone, ["Home.md"], "update home")
            log_result = subprocess.run(
                ["git", "-C", str(bare), "log", "--oneline"],
                capture_output=True,
                text=True,
            )
            assert "update home" in log_result.stdout
            ok("commit_push after changes succeeds")
        except Exception as exc:
            fail("commit_push after changes succeeds", exc)

        # --- (d) commit_push idempotent on no changes (no new commit) ---
        try:
            (clone / "Home.md").write_text("# Home Updated\n", encoding="utf-8")
            commit_push(clone, ["Home.md"], "idempotent test")
            log_result = subprocess.run(
                ["git", "-C", str(bare), "log", "--oneline"],
                capture_output=True,
                text=True,
            )
            assert "idempotent test" not in log_result.stdout, "no new commit should be made"
            ok("commit_push idempotent on no changes")
        except Exception as exc:
            fail("commit_push idempotent on no changes", exc)

        # --- (e) non-fast-forward rebase-retry ---
        try:
            clone2 = tmp / "clone2"
            clone2.mkdir(parents=True)
            subprocess.run(
                ["git", "init", "-b", "main", str(clone2)],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(clone2), "config", "user.email", "test@test.com"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(clone2), "config", "user.name", "Test User"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(clone2), "remote", "add", "origin", str(bare)],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(clone2), "fetch", "origin", "main"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(clone2), "checkout", "-b", "main", "origin/main"],
                check=True,
                capture_output=True,
            )

            (clone2 / "other.md").write_text("clone2 content\n", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(clone2), "add", "other.md"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(clone2), "commit", "-m", "from clone2"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(clone2), "push"],
                check=True,
                capture_output=True,
            )

            (clone / "another.md").write_text("clone1 content\n", encoding="utf-8")
            commit_push(clone, ["another.md"], "from clone1")
            ok("non-fast-forward rebase-retry")
        except WikiPushError:
            fail("non-fast-forward rebase-retry", Exception("WikiPushError raised"))
        except Exception as exc:
            fail("non-fast-forward rebase-retry", exc)

        # --- (f) path_guard("") raises WikiPathError ---
        try:
            path_guard("")
            fail("path_guard('') raises WikiPathError", Exception("Did not raise"))
        except WikiPathError:
            ok("path_guard('') raises WikiPathError")
        except Exception as exc:
            fail("path_guard('') raises WikiPathError", exc)

        # --- (g) path_guard("../escape") raises WikiPathError ---
        try:
            path_guard("../escape")
            fail("path_guard('../escape') raises WikiPathError", Exception("Did not raise"))
        except WikiPathError:
            ok("path_guard('../escape') raises WikiPathError")
        except Exception as exc:
            fail("path_guard('../escape') raises WikiPathError", exc)

        # --- (h) path_guard with absolute path raises WikiPathError ---
        try:
            import platform
            if platform.system() == "Windows":
                path_guard("C:\\absolute")
            else:
                path_guard("/absolute")
            fail("path_guard with absolute path raises WikiPathError", Exception("Did not raise"))
        except WikiPathError:
            ok("path_guard with absolute path raises WikiPathError")
        except Exception as exc:
            fail("path_guard with absolute path raises WikiPathError", exc)

        # --- (i) path_guard("Home.md") does not raise ---
        try:
            path_guard("Home.md")
            ok("path_guard('Home.md') does not raise")
        except Exception as exc:
            fail("path_guard('Home.md') does not raise", exc)

        # --- (j) path_guard("subdir/file.md") does not raise ---
        try:
            path_guard("subdir/file.md")
            ok("path_guard('subdir/file.md') does not raise")
        except Exception as exc:
            fail("path_guard('subdir/file.md') does not raise", exc)

        # --- (k) _run kills and raises WikiPushError when it exceeds timeout ---
        try:
            raised = False
            error_msg = ""
            try:
                _run(
                    [sys.executable, "-c", "import time; time.sleep(10)"],
                    clone,
                    timeout=0.5,
                )
            except WikiPushError as e:
                raised = True
                error_msg = str(e)
            assert raised, "Command exceeding timeout should raise WikiPushError"
            assert "timed out" in error_msg, f"Error should say 'timed out', got: {error_msg}"
            ok("_run raises WikiPushError on timeout")
        except Exception as exc:
            fail("_run raises WikiPushError on timeout", exc)

        # --- (l) _git_env disables interactive prompts ---
        try:
            env = _git_env()
            assert env.get("GIT_TERMINAL_PROMPT") == "0", \
                f"GIT_TERMINAL_PROMPT should be '0', got {env.get('GIT_TERMINAL_PROMPT')!r}"
            assert env.get("GCM_INTERACTIVE") == "Never", \
                f"GCM_INTERACTIVE should be 'Never', got {env.get('GCM_INTERACTIVE')!r}"
            ok("_git_env disables interactive prompts")
        except Exception as exc:
            fail("_git_env disables interactive prompts", exc)

        # --- (m) commit_push with explicit refspec (no upstream tracking) ---
        try:
            # Create a clone without upstream tracking configured
            clone3 = tmp / "clone3"
            clone3.mkdir(parents=True)
            subprocess.run(
                ["git", "init", "-b", "main", str(clone3)],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(clone3), "config", "user.email", "test@test.com"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(clone3), "config", "user.name", "Test User"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(clone3), "remote", "add", "origin", str(bare)],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(clone3), "fetch", "origin", "main"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(clone3), "checkout", "-b", "main", "origin/main"],
                check=True,
                capture_output=True,
            )
            # Explicitly unset tracking to test refspec-based push
            subprocess.run(
                ["git", "-C", str(clone3), "config", "--unset", "branch.main.remote"],
                check=False,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(clone3), "config", "--unset", "branch.main.merge"],
                check=False,
                capture_output=True,
            )

            (clone3 / "tracked.md").write_text("tracked content\n", encoding="utf-8")
            commit_push(clone3, ["tracked.md"], "test explicit refspec")
            log_result = subprocess.run(
                ["git", "-C", str(bare), "log", "--oneline"],
                capture_output=True,
                text=True,
            )
            assert "test explicit refspec" in log_result.stdout
            ok("commit_push with explicit refspec (no upstream tracking)")
        except Exception as exc:
            fail("commit_push with explicit refspec (no upstream tracking)", exc)

        # --- (n) commit_push against non-git-repo raises WikiPushError ---
        try:
            not_git = tmp / "not_git"
            not_git.mkdir(parents=True)
            (not_git / "file.md").write_text("content\n", encoding="utf-8")

            raised = False
            error_msg = ""
            try:
                commit_push(not_git, ["file.md"], "should fail")
            except WikiPushError as e:
                raised = True
                error_msg = str(e)

            assert raised, "commit_push on non-git-repo should raise WikiPushError"
            assert "not a git repository" in error_msg, \
                f"Error should mention 'not a git repository', got: {error_msg}"
            assert str(not_git) in error_msg, \
                f"Error should name the path {not_git}, got: {error_msg}"
            ok("commit_push against non-git-repo raises WikiPushError")
        except Exception as exc:
            fail("commit_push against non-git-repo raises WikiPushError", exc)

        # --- (o) clone_or_init plain-clone paths set upstream tracking ---
        try:
            # Import the setup module for clone_or_init
            import _setup
            clone4 = tmp / "clone4"

            # Test Path C (clone without branch)
            result = _setup.clone_or_init(str(bare), None, clone4)
            assert result["action"] == "cloned"

            # Verify tracking is set
            get_tracking = subprocess.run(
                ["git", "-C", str(clone4), "config", "--get", "branch.main.remote"],
                capture_output=True,
                text=True,
            )
            assert get_tracking.returncode == 0 and "origin" in get_tracking.stdout, \
                f"branch.main.remote should be configured, got: {get_tracking.stderr}"

            get_merge = subprocess.run(
                ["git", "-C", str(clone4), "config", "--get", "branch.main.merge"],
                capture_output=True,
                text=True,
            )
            assert get_merge.returncode == 0 and "refs/heads/main" in get_merge.stdout, \
                f"branch.main.merge should be configured, got: {get_merge.stderr}"

            ok("clone_or_init plain-clone path C sets upstream tracking")
        except Exception as exc:
            fail("clone_or_init plain-clone path C sets upstream tracking", exc)

    finally:
        _safe_rmtree.safe_rmtree(tmp, allowed_root=tmp, ignore_errors=True)

    print("", file=sys.stderr)
    if failed:
        print(f"FAIL -- {failed} of {passed + failed}", file=sys.stderr)
        return 1
    print(f"PASS -- all {passed} tests", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
