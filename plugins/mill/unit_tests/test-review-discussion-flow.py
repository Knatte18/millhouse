"""Unit-test flow harness for _review_discussion.run.

Uses _reviewer_test_stub as the reviewer backend. All tests run in-process
with no real LLM. Covers the per-scope (holistic) round counter for
discussion reviews (#21 regression pin).

Discussion review is exempt from the NEED_CONTEXT resume-fallback path
(per discussion.md decision), so no retry tests are included.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _active  # noqa: E402
import _reviewer_test_stub as stub  # noqa: E402
from _review_discussion import run as discussion_run  # noqa: E402

SLUG = "test-slug"

APPROVE_TEXT = "# Review: test\n\n```yaml\nverdict: APPROVE\n```\n"


def _make_fixture(tmp: Path) -> tuple[Path, Path]:
    """Create a container/wts/<slug> worktree fixture.

    Returns (mill_dir, project_root). project_root is the worktree path;
    callers must os.chdir(project_root) before invoking discussion_run.
    """
    worktree = tmp / "container" / "wts" / SLUG
    worktree.mkdir(parents=True)
    subprocess.run(["git", "-C", str(worktree), "init"], check=True, capture_output=True)
    mill_dir = worktree / ".millhouse"
    _active.write(
        mill_dir,
        slug=SLUG,
        task_title="Test Task",
        branch="test-branch",
        spawned_at="2026-01-01T00:00:00Z",
    )
    return mill_dir, worktree


def main() -> int:
    errors = 0

    # ------------------------------------------------------------------
    # Single test — per-scope round counter for holistic discussion review
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        mill_dir, project_root = _make_fixture(Path(tmpdir))

        # Create discussion file at worktree root
        (project_root / "discussion.md").write_text(
            "# Discussion\n\nThis is a test discussion.\n", encoding="utf-8"
        )

        cfg = {
            "paths": {
                "discussion_file": "discussion.md",
                "plan_dir":        "plan/",
                "reviews_dir":     "reviews/",
            },
            "review": {
                "discussion": {"rounds": 2, "holistic": "test_stub"},
            },
        }

        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            # Round 1
            stub.seed([(APPROVE_TEXT, "sid-1")])
            r = discussion_run(cfg, SLUG, mill_dir, project_root)
            assert r.verdict == "APPROVE", f"expected APPROVE, got {r.verdict}"
            assert r.round == 1, f"expected round 1, got {r.round}"
            fname = Path(r.reviews[0]["file"]).name
            assert "discussion-review-r1" in fname, f"unexpected filename: {fname}"
            assert r.reviews[0]["scope"] == "holistic", (
                f"expected scope 'holistic', got {r.reviews[0]['scope']!r}"
            )
            assert r.reviews[0]["session_id"] == "sid-1", (
                f"expected session_id 'sid-1', got {r.reviews[0]['session_id']!r}"
            )
            print(f"PASS test-discussion round 1: {fname} scope=holistic session_id=sid-1")

            # Round 2 — same reviews_dir, counter should increment
            stub.seed([(APPROVE_TEXT, "sid-2")])
            r2 = discussion_run(cfg, SLUG, mill_dir, project_root)
            assert r2.verdict == "APPROVE"
            assert r2.round == 2, f"expected round 2, got {r2.round}"
            fname2 = Path(r2.reviews[0]["file"]).name
            assert "discussion-review-r2" in fname2, f"unexpected r2 filename: {fname2}"
            assert r2.reviews[0]["scope"] == "holistic"
            print(f"PASS test-discussion round 2: {fname2} (per-scope counter increments)")

        except AssertionError as exc:
            errors += 1
            print(f"FAIL test-discussion: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test-discussion (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All _review_discussion flow tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
