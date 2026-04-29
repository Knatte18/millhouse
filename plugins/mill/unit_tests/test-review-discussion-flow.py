"""Unit-test flow harness for _review_discussion.run.

Uses _reviewer_test_stub as the reviewer backend. All tests run in-process
with no real LLM. Covers the per-scope (holistic) round counter for
discussion reviews (#21 regression pin).

Discussion review is exempt from the NEED_CONTEXT resume-fallback path
(per discussion.md decision), so no retry tests are included.
"""
from __future__ import annotations

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


def main() -> int:
    errors = 0

    # ------------------------------------------------------------------
    # Single test — per-scope round counter for holistic discussion review
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        wiki_root = Path(tmpdir) / "wiki"
        project_root = Path(tmpdir) / "project"
        mill_dir = project_root / ".millhouse"

        _active.write(
            mill_dir,
            slug=SLUG,
            task_title="Test Task",
            branch="test-branch",
            spawned_at="2026-01-01T00:00:00Z",
        )

        # Create discussion file
        discussion_dir = wiki_root / "active" / SLUG
        discussion_dir.mkdir(parents=True)
        (discussion_dir / "discussion.md").write_text(
            "# Discussion\n\nThis is a test discussion.\n", encoding="utf-8"
        )

        cfg = {
            "paths": {
                "discussion_file": f"active/{SLUG}/discussion.md",
                "plan_dir":        f"active/{SLUG}/plan/",
                "reviews_dir":     f"active/{SLUG}/reviews/",
            },
            "review": {
                "discussion": {"rounds": 2, "holistic": "test_stub"},
            },
        }

        try:
            # Round 1
            stub.seed([(APPROVE_TEXT, "sid-1")])
            r = discussion_run(cfg, SLUG, mill_dir, wiki_root, project_root)
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
            r2 = discussion_run(cfg, SLUG, mill_dir, wiki_root, project_root)
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

    # ------------------------------------------------------------------
    # max_rounds override
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        wiki_root = Path(tmpdir) / "wiki"
        project_root = Path(tmpdir) / "project"
        mill_dir = project_root / ".millhouse"

        _active.write(
            mill_dir,
            slug=SLUG,
            task_title="Test Task",
            branch="test-branch",
            spawned_at="2026-01-01T00:00:00Z",
        )

        discussion_dir = wiki_root / "active" / SLUG
        discussion_dir.mkdir(parents=True)
        (discussion_dir / "discussion.md").write_text(
            "# Discussion\n\nTest.\n", encoding="utf-8"
        )

        cfg = {
            "paths": {
                "discussion_file": f"active/{SLUG}/discussion.md",
                "plan_dir":        f"active/{SLUG}/plan/",
                "reviews_dir":     f"active/{SLUG}/reviews/",
            },
            "review": {
                "discussion": {"rounds": 2, "holistic": "test_stub"},
            },
        }

        try:
            # Pre-populate 2 review files by running rounds 1 and 2
            stub.seed([(APPROVE_TEXT, "sid-r1"), (APPROVE_TEXT, "sid-r2")])
            discussion_run(cfg, SLUG, mill_dir, wiki_root, project_root)
            discussion_run(cfg, SLUG, mill_dir, wiki_root, project_root)

            # Round 3 without kwarg: cfg.rounds == 2 → ReviewError
            try:
                stub.seed([(APPROVE_TEXT, "sid-r3")])
                discussion_run(cfg, SLUG, mill_dir, wiki_root, project_root)
                errors += 1
                print("FAIL max_rounds override: expected ReviewError for round 3 with cfg max=2", file=sys.stderr)
            except Exception as exc:
                if "exceeds max" in str(exc):
                    print("PASS max_rounds override: round 3 raises ReviewError without kwarg")
                else:
                    errors += 1
                    print(f"FAIL max_rounds override: unexpected exception: {exc}", file=sys.stderr)

            # Round 3 with max_rounds=5 kwarg: should succeed
            stub.seed([(APPROVE_TEXT, "sid-r3b")])
            r3 = discussion_run(cfg, SLUG, mill_dir, wiki_root, project_root, max_rounds=5)
            assert r3.round == 3, f"expected round 3, got {r3.round}"
            fname3 = Path(r3.reviews[0]["file"]).name
            assert "discussion-review-r3" in fname3, f"unexpected filename: {fname3}"
            print(f"PASS max_rounds override: round 3 succeeds with max_rounds=5 → {fname3}")

        except AssertionError as exc:
            errors += 1
            print(f"FAIL max_rounds override: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL max_rounds override (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)

    # ------------------------------------------------------------------
    # blocking_count populated from GAP headings
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        wiki_root = Path(tmpdir) / "wiki"
        project_root = Path(tmpdir) / "project"
        mill_dir = project_root / ".millhouse"

        _active.write(
            mill_dir,
            slug=SLUG,
            task_title="Test Task",
            branch="test-branch",
            spawned_at="2026-01-01T00:00:00Z",
        )

        discussion_dir = wiki_root / "active" / SLUG
        discussion_dir.mkdir(parents=True)
        (discussion_dir / "discussion.md").write_text(
            "# Discussion\n\nTest.\n", encoding="utf-8"
        )

        cfg = {
            "paths": {
                "discussion_file": f"active/{SLUG}/discussion.md",
                "plan_dir":        f"active/{SLUG}/plan/",
                "reviews_dir":     f"active/{SLUG}/reviews/",
            },
            "review": {
                "discussion": {"rounds": 5, "holistic": "test_stub"},
            },
        }

        try:
            # Two GAP headings → blocking_count == 2
            two_gaps = (
                "# Review\n\n"
                "### [GAP] missing rationale\n\n- bullet\n\n"
                "### [GAP] unclear scope\n\n- bullet\n\n"
                "```yaml\nverdict: GAPS_FOUND\n```\n"
            )
            stub.seed([(two_gaps, "sid-gaps")])
            r = discussion_run(cfg, SLUG, mill_dir, wiki_root, project_root)
            assert r.blocking_count == 2, f"expected blocking_count=2, got {r.blocking_count}"
            print("PASS blocking_count: two GAP headings → blocking_count == 2")

            # Zero GAPs → blocking_count == 0
            stub.seed([(APPROVE_TEXT, "sid-no-gaps")])
            r2 = discussion_run(cfg, SLUG, mill_dir, wiki_root, project_root)
            assert r2.blocking_count == 0, f"expected blocking_count=0, got {r2.blocking_count}"
            print("PASS blocking_count: no GAP headings → blocking_count == 0")

        except AssertionError as exc:
            errors += 1
            print(f"FAIL blocking_count: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL blocking_count (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All _review_discussion flow tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
