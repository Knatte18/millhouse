"""Unit tests for wiki._sync git operations layer.

Covers: pull() on up-to-date; atomic_write() writes and reads back;
commit_push() after changes; commit_push() idempotent on no changes;
non-fast-forward rebase retry; path_guard validation.

Uses a real tempfile bare repo + working clone (fast, deterministic, no mocks).
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from wiki._sync import (
    pull,
    atomic_write,
    commit_push,
    path_guard,
)  # noqa: E402
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
        temp_clone = tmp / "temp"

        # Initialize bare repo
        subprocess.run(["git", "init", "--bare", str(bare)], check=True, capture_output=True)

        # Clone it to temp for initial commit
        subprocess.run(["git", "clone", str(bare), str(temp_clone)], check=True, capture_output=True)

        # Configure git user in temp
        subprocess.run(
            ["git", "-C", str(temp_clone), "config", "user.email", "test@test.com"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(temp_clone), "config", "user.name", "Test User"],
            check=True,
            capture_output=True,
        )

        # Initial commit in temp
        (temp_clone / "Home.md").write_text("# Home\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(temp_clone), "add", "Home.md"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(temp_clone), "commit", "-m", "init"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(temp_clone), "push", "-u", "origin", "main"],
            check=True,
            capture_output=True,
        )

        # Clone again for the actual test
        subprocess.run(["git", "clone", str(bare), str(clone)], check=True, capture_output=True)

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

        # --- (a) pull() on up-to-date (does not raise) ---
        try:
            result = pull(clone)
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
            subprocess.run(
                ["git", "clone", str(bare), str(clone2)],
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

        # --- (h) path_guard("/absolute") raises WikiPathError ---
        try:
            path_guard("/absolute")
            fail("path_guard('/absolute') raises WikiPathError", Exception("Did not raise"))
        except WikiPathError:
            ok("path_guard('/absolute') raises WikiPathError")
        except Exception as exc:
            fail("path_guard('/absolute') raises WikiPathError", exc)

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

    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    print("", file=sys.stderr)
    if failed:
        print(f"FAIL -- {failed} of {passed + failed}", file=sys.stderr)
        return 1
    print(f"PASS -- all {passed} tests", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
