"""Unit tests for _finalize_cleanup.base_tracks_task_dir detection.

Covers: base branch tracking task_dir/status.md; base branch without _mill/;
Step 3's delete-then-restore mechanic removing orphaned child-only files
under task_dir that a bare checkout would leave behind (#653).

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
from _finalize_cleanup import base_tracks_task_dir  # noqa: E402


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

        # --- (a) Base branch that tracks _mill/status.md ---
        try:
            # Create _mill directory and status.md on main
            mill_dir = clone / "_mill"
            mill_dir.mkdir(parents=True)
            (mill_dir / "status.md").write_text("# Status\nphase: done\n", encoding="utf-8")

            subprocess.run(
                ["git", "-C", str(clone), "add", "_mill/status.md"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(clone), "commit", "-m", "init with _mill"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(clone), "push", "-u", "origin", "main"],
                check=True,
                capture_output=True,
            )

            # base_tracks_task_dir should return True for main
            result = base_tracks_task_dir(clone, "main", mill_dir)
            if result:
                ok("base_tracks_task_dir returns True when base tracks _mill/status.md")
            else:
                fail(
                    "base_tracks_task_dir returns True when base tracks _mill/status.md",
                    Exception(f"Expected True, got {result}"),
                )
        except Exception as exc:
            fail("base_tracks_task_dir returns True when base tracks _mill/status.md", exc)

        # --- (b) Base branch without _mill/ ---
        try:
            # Create a new branch without _mill
            subprocess.run(
                ["git", "-C", str(clone), "checkout", "-b", "feature"],
                check=True,
                capture_output=True,
            )
            # Remove _mill
            subprocess.run(
                ["git", "-C", str(clone), "rm", "-r", "_mill"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(clone), "commit", "-m", "remove _mill"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(clone), "push", "-u", "origin", "feature"],
                check=True,
                capture_output=True,
            )

            # base_tracks_task_dir should return False for feature (no _mill)
            result = base_tracks_task_dir(clone, "feature", mill_dir)
            if not result:
                ok("base_tracks_task_dir returns False when base does not track _mill/status.md")
            else:
                fail(
                    "base_tracks_task_dir returns False when base does not track _mill/status.md",
                    Exception(f"Expected False, got {result}"),
                )
        except Exception as exc:
            fail(
                "base_tracks_task_dir returns False when base does not track _mill/status.md", exc
            )

        # --- (c) Step 3 delete-then-restore removes orphaned child-only files (#653) ---
        try:
            # Return to main (base) before branching off the "child" branch.
            subprocess.run(
                ["git", "-C", str(clone), "checkout", "main"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(clone), "checkout", "-b", "child-stack"],
                check=True,
                capture_output=True,
            )

            # Child branch has a superset _mill/ tree: status.md (inherited
            # from main) plus discussion.md and plan/00-overview.md that
            # main never had.
            (mill_dir / "discussion.md").write_text(
                "discussion placeholder\n", encoding="utf-8"
            )
            plan_dir = mill_dir / "plan"
            plan_dir.mkdir(parents=True)
            (plan_dir / "00-overview.md").write_text("plan placeholder\n", encoding="utf-8")
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(clone),
                    "add",
                    "_mill/discussion.md",
                    "_mill/plan/00-overview.md",
                ],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(clone), "commit", "-m", "child: add discussion.md and plan/"],
                check=True,
                capture_output=True,
            )

            # Card 3's exact two-command sequence: delete-then-restore.
            subprocess.run(
                ["git", "-C", str(clone), "rm", "-r", "--ignore-unmatch", "_mill"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(clone), "checkout", "main", "--", "_mill"],
                check=True,
                capture_output=True,
            )

            discussion_gone = not (mill_dir / "discussion.md").exists()
            plan_gone = not plan_dir.exists()
            status_matches_main = (mill_dir / "status.md").read_text(
                encoding="utf-8"
            ) == "# Status\nphase: done\n"

            if discussion_gone and plan_gone and status_matches_main:
                ok(
                    "delete-then-restore removes orphaned child-only files "
                    "and restores status.md to main's version"
                )
            else:
                fail(
                    "delete-then-restore removes orphaned child-only files "
                    "and restores status.md to main's version",
                    Exception(
                        f"discussion_gone={discussion_gone} plan_gone={plan_gone} "
                        f"status_matches_main={status_matches_main}"
                    ),
                )
        except Exception as exc:
            fail(
                "delete-then-restore removes orphaned child-only files "
                "and restores status.md to main's version",
                exc,
            )

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
