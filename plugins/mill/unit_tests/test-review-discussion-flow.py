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
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _reviewer_test_stub as stub  # noqa: E402
import _test_registry  # noqa: E402
import _test_helpers  # noqa: E402
from wiki import _client as wiki  # noqa: E402
from _review_discussion import run as discussion_run  # noqa: E402
from _test_helpers import seed_wiki_config  # noqa: E402

SLUG = "test-slug"

APPROVE_TEXT = "# Review: test\n\n```yaml\nverdict: APPROVE\n```\n"


def _make_fixture(tmp: Path) -> tuple[Path, Path, Path]:
    """Create a container/wts/<slug> worktree fixture.

    Returns (mill_dir, project_root, wiki_root). project_root is the worktree path;
    callers must os.chdir(project_root) before invoking discussion_run.
    """
    worktree = tmp / "container" / "wts" / SLUG
    worktree.mkdir(parents=True)
    subprocess.run(["git", "-C", str(worktree), "init"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(worktree), "checkout", "-b", f"hanf/{SLUG}"], capture_output=True)
    subprocess.run(["git", "-C", str(worktree), "config", "user.email", "test@example.com"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(worktree), "config", "user.name", "test"], check=True, capture_output=True)
    (worktree / ".gitignore").write_text("\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(worktree), "add", ".gitignore"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(worktree), "commit", "-m", "seed"], check=True, capture_output=True)
    mill_dir = worktree / ".millhouse"
    mill_dir.mkdir(parents=True, exist_ok=True)
    wiki_root = tmp / "wiki"
    _test_helpers.init_wiki_repo(wiki_root)
    seed_wiki_config(wiki_root)
    (wiki_root / "Home.md").write_text(
        f"## Test Task\n[{SLUG}] [active]\n\n_body_\n", encoding="utf-8"
    )
    wiki.upsert_task(wiki_root, SLUG, title="Test Task", status="active")
    (mill_dir / "config.local.yaml").write_text(
        f"paths:\n  wiki: '{wiki_root.as_posix()}'\n", encoding="utf-8"
    )
    _test_registry.write_to(wiki_root)
    return mill_dir, worktree, wiki_root


def main() -> int:
    errors = 0

    # ------------------------------------------------------------------
    # Single test — per-scope round counter for holistic discussion review
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        mill_dir, project_root, wiki_root = _make_fixture(tmpdir)

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
            "spawn": {
                "branch_prefix": "hanf/",
            },
            "roles": {
                "discussion-review": {
                    "holistic": {"rounds": 2, "reviewer": "test_stub"},
                },
            },
        }

        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            # Round 1
            stub.seed([(APPROVE_TEXT, "sid-1")])
            r = discussion_run(cfg, SLUG, mill_dir, project_root, wiki_root)
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
            assert str(project_root / "reviews") in r.reviews[0]["file"], (
                f"review file must be under worktree/reviews/, got {r.reviews[0]['file']!r}"
            )
            print(f"PASS test-discussion round 1: {fname} scope=holistic session_id=sid-1")

            # Round 2 — same reviews_dir, counter should increment
            stub.seed([(APPROVE_TEXT, "sid-2")])
            r2 = discussion_run(cfg, SLUG, mill_dir, project_root, wiki_root)
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

    # ------------------------------------------------------------------
    # max_rounds override
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        mill_dir, project_root, wiki_root = _make_fixture(tmpdir)
        (project_root / "discussion.md").write_text(
            "# Discussion\n\nTest.\n", encoding="utf-8"
        )

        cfg = {
            "paths": {
                "discussion_file": "discussion.md",
                "plan_dir":        "plan/",
                "reviews_dir":     "reviews/",
            },
            "roles": {
                "discussion-review": {
                    "holistic": {"rounds": 2, "reviewer": "test_stub"},
                },
            },
        }

        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            # Pre-populate 2 review files by running rounds 1 and 2
            stub.seed([(APPROVE_TEXT, "sid-r1"), (APPROVE_TEXT, "sid-r2")])
            discussion_run(cfg, SLUG, mill_dir, project_root, wiki_root)
            discussion_run(cfg, SLUG, mill_dir, project_root, wiki_root)

            # Round 3 without kwarg: cfg.rounds == 2 -> ReviewError
            try:
                stub.seed([(APPROVE_TEXT, "sid-r3")])
                discussion_run(cfg, SLUG, mill_dir, project_root, wiki_root)
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
            r3 = discussion_run(cfg, SLUG, mill_dir, project_root, wiki_root, max_rounds=5)
            assert r3.round == 3, f"expected round 3, got {r3.round}"
            fname3 = Path(r3.reviews[0]["file"]).name
            assert "discussion-review-r3" in fname3, f"unexpected filename: {fname3}"
            print(f"PASS max_rounds override: round 3 succeeds with max_rounds=5 -> {fname3}")

        except AssertionError as exc:
            errors += 1
            print(f"FAIL max_rounds override: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL max_rounds override (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # blocking_count populated from GAP headings
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        mill_dir, project_root, wiki_root = _make_fixture(tmpdir)
        (project_root / "discussion.md").write_text(
            "# Discussion\n\nTest.\n", encoding="utf-8"
        )

        cfg = {
            "paths": {
                "discussion_file": "discussion.md",
                "plan_dir":        "plan/",
                "reviews_dir":     "reviews/",
            },
            "roles": {
                "discussion-review": {
                    "holistic": {"rounds": 5, "reviewer": "test_stub"},
                },
            },
        }

        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            # Two GAP headings -> blocking_count == 2
            two_gaps = (
                "# Review\n\n"
                "### [GAP] missing rationale\n\n- bullet\n\n"
                "### [GAP] unclear scope\n\n- bullet\n\n"
                "```yaml\nverdict: GAPS_FOUND\n```\n"
            )
            stub.seed([(two_gaps, "sid-gaps")])
            r = discussion_run(cfg, SLUG, mill_dir, project_root, wiki_root)
            assert r.blocking_count == 2, f"expected blocking_count=2, got {r.blocking_count}"
            print("PASS blocking_count: two GAP headings -> blocking_count == 2")

            # Zero GAPs -> blocking_count == 0
            stub.seed([(APPROVE_TEXT, "sid-no-gaps")])
            r2 = discussion_run(cfg, SLUG, mill_dir, project_root, wiki_root)
            assert r2.blocking_count == 0, f"expected blocking_count=0, got {r2.blocking_count}"
            print("PASS blocking_count: no GAP headings -> blocking_count == 0")

        except AssertionError as exc:
            errors += 1
            print(f"FAIL blocking_count: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL blocking_count (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test parse_verdict failure — returns ERROR envelope (#315)
    # Unparseable output -> ERROR verdict, ERROR entry with file path.
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        mill_dir, project_root, wiki_root = _make_fixture(tmpdir)

        # Create discussion file
        (project_root / "discussion.md").write_text(
            "# Discussion\n\nThis is a test discussion.\n", encoding="utf-8"
        )

        cfg = {
            "paths": {
                "discussion_file": "discussion.md",
                "plan_dir":        "plan/",
                "reviews_dir":     "reviews/",
            },
            "roles": {
                "discussion-review": {
                    "holistic": {"rounds": 5, "reviewer": "test_stub"},
                },
            },
        }

        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            stub.seed([
                ("# Raw prose without yaml block\n\nDiscussion looks fine.", "sid-unparseable"),
            ])
            r = discussion_run(cfg, SLUG, mill_dir, project_root, wiki_root)
            assert r.verdict == "ERROR", (
                f"expected ERROR, got {r.verdict}"
            )
            assert len(r.reviews) >= 1, f"expected at least 1 review, got {len(r.reviews)}"
            assert r.reviews[0]["verdict"] == "ERROR", (
                f"expected ERROR verdict, got {r.reviews[0]['verdict']}"
            )
            assert "parse_verdict failed" in r.reviews[0].get("error", ""), (
                f"error message missing 'parse_verdict failed': {r.reviews[0].get('error')}"
            )
            assert r.reviews[0]["file"] is not None, "ERROR entry should have a file path"
            file_path = Path(r.reviews[0]["file"])
            assert file_path.exists(), f"review file should exist on disk: {file_path}"
            print("PASS parse_verdict failure: discussion parse_verdict failure emits ERROR envelope (#315)")

        except AssertionError as exc:
            errors += 1
            print(f"FAIL parse_verdict failure: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL parse_verdict failure (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # rounds=0 early return (APPROVE stub)
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        mill_dir, project_root, wiki_root = _make_fixture(tmpdir)
        (project_root / "discussion.md").write_text(
            "# Discussion\n\nTest discussion.\n", encoding="utf-8"
        )

        cfg = {
            "paths": {
                "discussion_file": "discussion.md",
                "plan_dir":        "plan/",
                "reviews_dir":     "reviews/",
            },
            "roles": {
                "discussion-review": {
                    "holistic": {"rounds": 0, "reviewer": "test_stub"},
                },
            },
        }

        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            r = discussion_run(cfg, SLUG, mill_dir, project_root, wiki_root)
            assert r.verdict == "APPROVE", f"expected APPROVE for rounds=0, got {r.verdict}"
            assert r.round == 0, f"expected round=0, got {r.round}"
            assert r.blocking_count == 0, f"expected blocking_count=0, got {r.blocking_count}"
            print("PASS rounds=0: discussion rounds=0 -> APPROVE stub with round=0, blocking_count=0")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL rounds=0: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL rounds=0 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All _review_discussion flow tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
