"""Unit-test flow harness for _review_discussion.run.

Uses _reviewer_test_stub as the reviewer backend.
All tests run in-process with no real LLM.
Covers the per-scope (holistic) round counter for discussion reviews (#21 regression pin).

Discussion review is exempt from the NEED_CONTEXT resume-fallback path (per discussion.md decision),
so no retry tests are included.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import yaml

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _reviewer_test_stub as stub  # noqa: E402
import _test_registry  # noqa: E402
import _test_helpers  # noqa: E402
from wiki import _client as wiki  # noqa: E402
from _llm_common import LLMError, ReviewerCallResult  # noqa: E402
from _review_common import ReviewError  # noqa: E402
import _review_discussion  # noqa: E402
from _review_discussion import prepare as discussion_prepare  # noqa: E402
from _review_discussion import run as discussion_run  # noqa: E402
from _test_helpers import seed_wiki_config, write_local_overlay  # noqa: E402

SLUG = "test-slug"

APPROVE_TEXT = "# Review: test\n\n```yaml\nverdict: APPROVE\n```\n"


def _make_fixture(tmp: Path) -> tuple[Path, Path, Path]:
    """Create a container/wts/<slug> worktree fixture.

    Returns (mill_dir, project_root, wiki_root).
    project_root is the worktree path;
    callers must os.chdir(project_root) before invoking discussion_run.
    """
    worktree = tmp / "container" / "wts" / SLUG
    worktree.mkdir(parents=True)
    subprocess.run(
        ["git", "-C", str(worktree), "init"], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(worktree), "checkout", "-b", f"hanf/{SLUG}"],
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(worktree), "config", "user.email", "test@example.com"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(worktree), "config", "user.name", "test"],
        check=True,
        capture_output=True,
    )
    (worktree / ".gitignore").write_text("\n", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(worktree), "add", ".gitignore"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(worktree), "commit", "-m", "seed"],
        check=True,
        capture_output=True,
    )
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
        f"paths:\n  wiki: '{wiki_root.as_posix()}'\nspawn:\n  branch_prefix: 'hanf/'\n",
        encoding="utf-8",
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
                "plan_dir": "plan/",
                "reviews_dir": "reviews/",
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
            print(
                f"PASS test-discussion round 1: {fname} scope=holistic session_id=sid-1"
            )

            # Round 2 — same reviews_dir, counter should increment
            stub.seed([(APPROVE_TEXT, "sid-2")])
            r2 = discussion_run(cfg, SLUG, mill_dir, project_root, wiki_root)
            assert r2.verdict == "APPROVE"
            assert r2.round == 2, f"expected round 2, got {r2.round}"
            fname2 = Path(r2.reviews[0]["file"]).name
            assert "discussion-review-r2" in fname2, f"unexpected r2 filename: {fname2}"
            assert r2.reviews[0]["scope"] == "holistic"
            print(
                f"PASS test-discussion round 2: {fname2} (per-scope counter increments)"
            )

        except AssertionError as exc:
            errors += 1
            print(f"FAIL test-discussion: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(
                f"FAIL test-discussion (unexpected {type(exc).__name__}): {exc}",
                file=sys.stderr,
            )
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
                "plan_dir": "plan/",
                "reviews_dir": "reviews/",
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
                print(
                    "FAIL max_rounds override: expected ReviewError for round 3 with cfg max=2",
                    file=sys.stderr,
                )
            except Exception as exc:
                if "exceeds max" in str(exc):
                    print(
                        "PASS max_rounds override: round 3 raises ReviewError without kwarg"
                    )
                else:
                    errors += 1
                    print(
                        f"FAIL max_rounds override: unexpected exception: {exc}",
                        file=sys.stderr,
                    )

            # Round 3 with max_rounds=5 kwarg: should succeed
            stub.seed([(APPROVE_TEXT, "sid-r3b")])
            r3 = discussion_run(
                cfg, SLUG, mill_dir, project_root, wiki_root, max_rounds=5
            )
            assert r3.round == 3, f"expected round 3, got {r3.round}"
            fname3 = Path(r3.reviews[0]["file"]).name
            assert "discussion-review-r3" in fname3, f"unexpected filename: {fname3}"
            print(
                f"PASS max_rounds override: round 3 succeeds with max_rounds=5 -> {fname3}"
            )

        except AssertionError as exc:
            errors += 1
            print(f"FAIL max_rounds override: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(
                f"FAIL max_rounds override (unexpected {type(exc).__name__}): {exc}",
                file=sys.stderr,
            )
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
                "plan_dir": "plan/",
                "reviews_dir": "reviews/",
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
            # Two BLOCKING:design headings -> blocking_count == 2 (design survives the
            # discussion stage's blocking_classes ceiling, so the count is unaffected by demotion).
            two_gaps = (
                "# Review\n\n"
                "### [BLOCKING:design] missing rationale\n\n- bullet\n\n"
                "### [BLOCKING:design] unclear scope\n\n- bullet\n\n"
                "```yaml\nverdict: REQUEST_CHANGES\n```\n"
            )
            stub.seed([(two_gaps, "sid-gaps")])
            r = discussion_run(cfg, SLUG, mill_dir, project_root, wiki_root)
            assert r.verdict == "REQUEST_CHANGES", (
                f"expected REQUEST_CHANGES, got {r.verdict}"
            )
            assert r.blocking_count == 2, (
                f"expected blocking_count=2, got {r.blocking_count}"
            )
            print("PASS blocking_count: two BLOCKING:design headings -> blocking_count == 2")

            # Zero BLOCKING headings -> blocking_count == 0
            stub.seed([(APPROVE_TEXT, "sid-no-gaps")])
            r2 = discussion_run(cfg, SLUG, mill_dir, project_root, wiki_root)
            assert r2.blocking_count == 0, (
                f"expected blocking_count=0, got {r2.blocking_count}"
            )
            print("PASS blocking_count: no BLOCKING headings -> blocking_count == 0")

        except AssertionError as exc:
            errors += 1
            print(f"FAIL blocking_count: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(
                f"FAIL blocking_count (unexpected {type(exc).__name__}): {exc}",
                file=sys.stderr,
            )
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # nit_count populated from NOTE headings
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        mill_dir, project_root, wiki_root = _make_fixture(tmpdir)
        (project_root / "discussion.md").write_text(
            "# Discussion\n\nTest.\n", encoding="utf-8"
        )

        cfg = {
            "paths": {
                "discussion_file": "discussion.md",
                "plan_dir": "plan/",
                "reviews_dir": "reviews/",
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
            # Two NIT:design headings and zero BLOCKING -> nit_count == 2, blocking_count == 0
            two_notes = (
                "# Review\n\n"
                "### [NIT:design] minor style issue\n\n- bullet\n\n"
                "### [NIT:design] consider this optimization\n\n- bullet\n\n"
                "```yaml\nverdict: APPROVE\n```\n"
            )
            stub.seed([(two_notes, "sid-notes")])
            r = discussion_run(cfg, SLUG, mill_dir, project_root, wiki_root)
            assert r.nit_count == 2, f"expected nit_count=2, got {r.nit_count}"
            assert r.blocking_count == 0, (
                f"expected blocking_count=0, got {r.blocking_count}"
            )
            print(
                "PASS nit_count: two NIT:design headings -> nit_count == 2, blocking_count == 0"
            )

        except AssertionError as exc:
            errors += 1
            print(f"FAIL nit_count: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(
                f"FAIL nit_count (unexpected {type(exc).__name__}): {exc}",
                file=sys.stderr,
            )
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # findings list length equals blocking_count + nit_count, at both the
    # top level and inside reviews[0]
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        mill_dir, project_root, wiki_root = _make_fixture(tmpdir)
        (project_root / "discussion.md").write_text(
            "# Discussion\n\nTest.\n", encoding="utf-8"
        )

        cfg = {
            "paths": {
                "discussion_file": "discussion.md",
                "plan_dir": "plan/",
                "reviews_dir": "reviews/",
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
            # Two BLOCKING:design and one NIT:design -> findings length == 3.
            mixed = (
                "# Review\n\n"
                "### [BLOCKING:design] missing rationale\n\n- bullet\n\n"
                "### [BLOCKING:design] unclear scope\n\n- bullet\n\n"
                "### [NIT:design] minor style issue\n\n- bullet\n\n"
                "```yaml\nverdict: REQUEST_CHANGES\n```\n"
            )
            stub.seed([(mixed, "sid-findings")])
            r = discussion_run(cfg, SLUG, mill_dir, project_root, wiki_root)
            expected_len = r.blocking_count + r.nit_count
            assert len(r.findings) == expected_len, (
                f"expected top-level findings length {expected_len}, got {len(r.findings)}"
            )
            assert len(r.reviews[0]["findings"]) == expected_len, (
                f"expected reviews[0] findings length {expected_len}, "
                f"got {len(r.reviews[0]['findings'])}"
            )
            print(
                "PASS findings length: top-level and reviews[0] findings both "
                "equal blocking_count + nit_count"
            )

        except AssertionError as exc:
            errors += 1
            print(f"FAIL findings length: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(
                f"FAIL findings length (unexpected {type(exc).__name__}): {exc}",
                file=sys.stderr,
            )
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # BLOCKING:scope findings are demoted at the discussion stage (scope is
    # outside discussion-review's default blocking_classes) -> APPROVE
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        mill_dir, project_root, wiki_root = _make_fixture(tmpdir)
        (project_root / "discussion.md").write_text(
            "# Discussion\n\nTest.\n", encoding="utf-8"
        )

        cfg = {
            "paths": {
                "discussion_file": "discussion.md",
                "plan_dir": "plan/",
                "reviews_dir": "reviews/",
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
            two_scope_findings = (
                "# Review\n\n"
                "### [BLOCKING:scope] incomplete inventory\n\n- bullet\n\n"
                "### [BLOCKING:scope] unreliable enumeration\n\n- bullet\n\n"
                "```yaml\nverdict: REQUEST_CHANGES\n```\n"
            )
            stub.seed([(two_scope_findings, "sid-scope-only")])
            r = discussion_run(cfg, SLUG, mill_dir, project_root, wiki_root)
            assert r.verdict == "APPROVE", (
                f"expected APPROVE (scope demoted to NIT), got {r.verdict}"
            )
            assert r.blocking_count == 0, (
                f"expected blocking_count=0, got {r.blocking_count}"
            )
            assert r.nit_count == len(r.findings), (
                f"expected nit_count == number of findings ({len(r.findings)}), "
                f"got {r.nit_count}"
            )
            assert all(f["demoted"] for f in r.findings), (
                f"expected every finding demoted, got {r.findings}"
            )
            print(
                "PASS BLOCKING:scope demotion: scope-only findings yield APPROVE "
                "with all findings demoted"
            )

        except AssertionError as exc:
            errors += 1
            print(f"FAIL BLOCKING:scope demotion: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(
                f"FAIL BLOCKING:scope demotion (unexpected {type(exc).__name__}): {exc}",
                file=sys.stderr,
            )
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
                "plan_dir": "plan/",
                "reviews_dir": "reviews/",
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
            stub.seed(
                [
                    (
                        "# Raw prose without yaml block\n\nDiscussion looks fine.",
                        "sid-unparseable",
                    ),
                ]
            )
            r = discussion_run(cfg, SLUG, mill_dir, project_root, wiki_root)
            assert r.verdict == "ERROR", f"expected ERROR, got {r.verdict}"
            assert len(r.reviews) >= 1, (
                f"expected at least 1 review, got {len(r.reviews)}"
            )
            assert r.reviews[0]["verdict"] == "ERROR", (
                f"expected ERROR verdict, got {r.reviews[0]['verdict']}"
            )
            assert "parse_verdict failed" in r.reviews[0].get("error", ""), (
                f"error message missing 'parse_verdict failed': {r.reviews[0].get('error')}"
            )
            assert r.reviews[0]["file"] is not None, (
                "ERROR entry should have a file path"
            )
            file_path = Path(r.reviews[0]["file"])
            assert file_path.exists(), f"review file should exist on disk: {file_path}"
            print(
                "PASS parse_verdict failure: discussion parse_verdict failure emits ERROR envelope (#315)"
            )

        except AssertionError as exc:
            errors += 1
            print(f"FAIL parse_verdict failure: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(
                f"FAIL parse_verdict failure (unexpected {type(exc).__name__}): {exc}",
                file=sys.stderr,
            )
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
                "plan_dir": "plan/",
                "reviews_dir": "reviews/",
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
            assert r.verdict == "APPROVE", (
                f"expected APPROVE for rounds=0, got {r.verdict}"
            )
            assert r.round == 0, f"expected round=0, got {r.round}"
            assert r.blocking_count == 0, (
                f"expected blocking_count=0, got {r.blocking_count}"
            )
            print(
                "PASS rounds=0: discussion rounds=0 -> APPROVE stub with round=0, blocking_count=0"
            )
        except AssertionError as exc:
            errors += 1
            print(f"FAIL rounds=0: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(
                f"FAIL rounds=0 (unexpected {type(exc).__name__}): {exc}",
                file=sys.stderr,
            )
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # prepare() reviewer_override -- resolves the named override, not config
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        mill_dir, project_root, wiki_root = _make_fixture(tmpdir)
        (project_root / "discussion.md").write_text(
            "# Discussion\n\nTest.\n", encoding="utf-8"
        )

        cfg = {
            "paths": {
                "discussion_file": "discussion.md",
                "plan_dir": "plan/",
                "reviews_dir": "reviews/",
            },
            "roles": {
                "discussion-review": {
                    "holistic": {
                        "rounds": 1,
                        "reviewer": "config-reviewer-should-not-be-used",
                    },
                },
            },
        }

        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            write_local_overlay(
                mill_dir,
                **{
                    "override-reviewer": {
                        "type": "single",
                        "provider": "claude",
                        "model": "claude-opus-4-1",
                        "effort": "max",
                        "tooluse": False,
                    }
                },
            )
            result = discussion_prepare(
                cfg, SLUG, mill_dir, project_root, wiki_root,
                reviewer_override="override-reviewer",
            )
            assert result["model"] == "claude-opus-4-1", (
                f"expected override model claude-opus-4-1, got {result['model']!r}"
            )
            assert result["effort"] == "max", (
                f"expected override effort max, got {result['effort']!r}"
            )
            print(
                "PASS prepare() reviewer_override: named override drives "
                "resolution, not config's reviewer"
            )
        except AssertionError as exc:
            errors += 1
            print(f"FAIL prepare() reviewer_override: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(
                f"FAIL prepare() reviewer_override (unexpected {type(exc).__name__}): {exc}",
                file=sys.stderr,
            )
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # prepare() reviewer_override -- unknown name raises ReviewError
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        mill_dir, project_root, wiki_root = _make_fixture(tmpdir)
        (project_root / "discussion.md").write_text(
            "# Discussion\n\nTest.\n", encoding="utf-8"
        )

        cfg = {
            "paths": {
                "discussion_file": "discussion.md",
                "plan_dir": "plan/",
                "reviews_dir": "reviews/",
            },
            "roles": {
                "discussion-review": {
                    "holistic": {
                        "rounds": 1,
                        "reviewer": "config-reviewer-should-not-be-used",
                    },
                },
            },
        }

        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            try:
                discussion_prepare(
                    cfg, SLUG, mill_dir, project_root, wiki_root,
                    reviewer_override="does-not-exist",
                )
                errors += 1
                print(
                    "FAIL prepare() reviewer_override unknown name: expected ReviewError",
                    file=sys.stderr,
                )
            except ReviewError as exc:
                assert "Unknown reviewer" in str(exc), (
                    f"expected 'Unknown reviewer' in error, got {exc!r}"
                )
                print(
                    "PASS prepare() reviewer_override unknown name: raises "
                    "ReviewError mentioning 'Unknown reviewer'"
                )
        except AssertionError as exc:
            errors += 1
            print(f"FAIL prepare() reviewer_override unknown name: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(
                f"FAIL prepare() reviewer_override unknown name (unexpected "
                f"{type(exc).__name__}): {exc}",
                file=sys.stderr,
            )
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # prepare() reviewer_override -- cluster override raises ReviewError
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        mill_dir, project_root, wiki_root = _make_fixture(tmpdir)
        (project_root / "discussion.md").write_text(
            "# Discussion\n\nTest.\n", encoding="utf-8"
        )

        cfg = {
            "paths": {
                "discussion_file": "discussion.md",
                "plan_dir": "plan/",
                "reviews_dir": "reviews/",
            },
            "roles": {
                "discussion-review": {
                    "holistic": {
                        "rounds": 1,
                        "reviewer": "config-reviewer-should-not-be-used",
                    },
                },
            },
        }

        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            write_local_overlay(
                mill_dir,
                **{
                    "worker_single": {
                        "type": "single",
                        "provider": "claude",
                        "model": "claude-sonnet-4-6",
                    },
                    "override-cluster": {
                        "type": "cluster",
                        "workers": {"use": "worker_single", "count": 3},
                        "handler": {"use": "worker_single"},
                    },
                },
            )
            try:
                discussion_prepare(
                    cfg, SLUG, mill_dir, project_root, wiki_root,
                    reviewer_override="override-cluster",
                )
                errors += 1
                print(
                    "FAIL prepare() reviewer_override cluster: expected ReviewError",
                    file=sys.stderr,
                )
            except ReviewError as exc:
                assert "cluster" in str(exc), (
                    f"expected 'cluster' in error, got {exc!r}"
                )
                print(
                    "PASS prepare() reviewer_override cluster: raises "
                    "ReviewError mentioning 'cluster'"
                )
        except AssertionError as exc:
            errors += 1
            print(f"FAIL prepare() reviewer_override cluster: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(
                f"FAIL prepare() reviewer_override cluster (unexpected "
                f"{type(exc).__name__}): {exc}",
                file=sys.stderr,
            )
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # prepare() reviewer_override -- skips the large-prompt auto-switch entirely
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        mill_dir, project_root, wiki_root = _make_fixture(tmpdir)
        (project_root / "discussion.md").write_text(
            "# Discussion\n\nTest.\n", encoding="utf-8"
        )

        cfg = {
            "paths": {
                "discussion_file": "discussion.md",
                "plan_dir": "plan/",
                "reviews_dir": "reviews/",
            },
            "roles": {
                "discussion-review": {
                    "holistic": {
                        "rounds": 1,
                        "reviewer": "config-reviewer-should-not-be-used",
                        "large_prompt": {
                            "threshold_ktok": 0,
                            "reviewer": "large-prompt-reviewer",
                        },
                    },
                },
            },
        }

        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            write_local_overlay(
                mill_dir,
                **{
                    "override-reviewer": {
                        "type": "single",
                        "provider": "claude",
                        "model": "claude-opus-4-1",
                        "effort": "max",
                        "tooluse": False,
                    },
                    "large-prompt-reviewer": {
                        "type": "single",
                        "provider": "claude",
                        "model": "claude-haiku-4-5-20251001",
                        "tooluse": False,
                    },
                },
            )
            result = discussion_prepare(
                cfg, SLUG, mill_dir, project_root, wiki_root,
                reviewer_override="override-reviewer",
            )
            assert result["model"] == "claude-opus-4-1", (
                f"expected override model claude-opus-4-1 (large-prompt-reviewer "
                f"never consulted), got {result['model']!r}"
            )
            print(
                "PASS prepare() reviewer_override large-prompt skip: override "
                "survives large_prompt auto-switch untouched"
            )
        except AssertionError as exc:
            errors += 1
            print(
                f"FAIL prepare() reviewer_override large-prompt skip: {exc}",
                file=sys.stderr,
            )
        except Exception as exc:
            errors += 1
            print(
                f"FAIL prepare() reviewer_override large-prompt skip (unexpected "
                f"{type(exc).__name__}): {exc}",
                file=sys.stderr,
            )
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # run() reviewer_override -- dispatches the named override, not config
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        mill_dir, project_root, wiki_root = _make_fixture(tmpdir)
        (project_root / "discussion.md").write_text(
            "# Discussion\n\nTest.\n", encoding="utf-8"
        )

        cfg = {
            "paths": {
                "discussion_file": "discussion.md",
                "plan_dir": "plan/",
                "reviews_dir": "reviews/",
            },
            "roles": {
                "discussion-review": {
                    "holistic": {
                        "rounds": 1,
                        "reviewer": "config-reviewer-should-not-be-used",
                    },
                },
            },
        }

        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            write_local_overlay(
                mill_dir,
                **{
                    "override-reviewer": {
                        "type": "single",
                        "provider": "test_stub",
                        "model": "unused-test-stub-model",
                        "tooluse": False,
                    }
                },
            )
            stub.seed([(APPROVE_TEXT, "sid-run-override")])
            r = discussion_run(
                cfg, SLUG, mill_dir, project_root, wiki_root,
                reviewer_override="override-reviewer",
            )
            assert r.verdict == "APPROVE", f"expected APPROVE, got {r.verdict}"
            assert Path(r.reviews[0]["file"]).exists(), (
                f"expected review file to exist, got {r.reviews[0]['file']!r}"
            )
            print(
                "PASS run() reviewer_override: named override dispatches, "
                "not config's reviewer"
            )
        except AssertionError as exc:
            errors += 1
            print(f"FAIL run() reviewer_override: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(
                f"FAIL run() reviewer_override (unexpected {type(exc).__name__}): {exc}",
                file=sys.stderr,
            )
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # run() reviewer_override -- unknown name raises ReviewError before dispatch
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        mill_dir, project_root, wiki_root = _make_fixture(tmpdir)
        (project_root / "discussion.md").write_text(
            "# Discussion\n\nTest.\n", encoding="utf-8"
        )

        cfg = {
            "paths": {
                "discussion_file": "discussion.md",
                "plan_dir": "plan/",
                "reviews_dir": "reviews/",
            },
            "roles": {
                "discussion-review": {
                    "holistic": {
                        "rounds": 1,
                        "reviewer": "config-reviewer-should-not-be-used",
                    },
                },
            },
        }

        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            try:
                discussion_run(
                    cfg, SLUG, mill_dir, project_root, wiki_root,
                    reviewer_override="does-not-exist",
                )
                errors += 1
                print(
                    "FAIL run() reviewer_override unknown name: expected ReviewError",
                    file=sys.stderr,
                )
            except ReviewError as exc:
                assert "Unknown reviewer" in str(exc), (
                    f"expected 'Unknown reviewer' in error, got {exc!r}"
                )
                print(
                    "PASS run() reviewer_override unknown name: raises "
                    "ReviewError mentioning 'Unknown reviewer' (fails before dispatch)"
                )
        except AssertionError as exc:
            errors += 1
            print(f"FAIL run() reviewer_override unknown name: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(
                f"FAIL run() reviewer_override unknown name (unexpected "
                f"{type(exc).__name__}): {exc}",
                file=sys.stderr,
            )
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # run() reviewer_override -- accepts a non-Claude alias (reject_non_claude=False)
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        mill_dir, project_root, wiki_root = _make_fixture(tmpdir)
        (project_root / "discussion.md").write_text(
            "# Discussion\n\nTest.\n", encoding="utf-8"
        )

        cfg = {
            "paths": {
                "discussion_file": "discussion.md",
                "plan_dir": "plan/",
                "reviews_dir": "reviews/",
            },
            "roles": {
                "discussion-review": {
                    "holistic": {
                        "rounds": 1,
                        "reviewer": "config-reviewer-should-not-be-used",
                    },
                },
            },
        }

        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            write_local_overlay(
                mill_dir,
                **{
                    "gemini-reviewer": {
                        "type": "single",
                        "provider": "gemini",
                        "model": "gemini-2.5-flash",
                        "tooluse": False,
                    }
                },
            )
            import _llm_gemini as llm_gemini

            original = llm_gemini.run_bulk
            llm_gemini.run_bulk = lambda prompt_text, **kw: ReviewerCallResult(
                text=APPROVE_TEXT, session_id="sid-gemini"
            )
            try:
                r = discussion_run(
                    cfg, SLUG, mill_dir, project_root, wiki_root,
                    reviewer_override="gemini-reviewer",
                )
            finally:
                llm_gemini.run_bulk = original
            assert r.verdict == "APPROVE", f"expected APPROVE, got {r.verdict}"
            print(
                "PASS run() reviewer_override: accepts non-Claude alias "
                "(reject_non_claude=False), unlike prepare()"
            )
        except AssertionError as exc:
            errors += 1
            print(f"FAIL run() reviewer_override gemini alias: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(
                f"FAIL run() reviewer_override gemini alias (unexpected "
                f"{type(exc).__name__}): {exc}",
                file=sys.stderr,
            )
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # run() reviewer_override -- skips the large-prompt auto-switch entirely
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        mill_dir, project_root, wiki_root = _make_fixture(tmpdir)
        (project_root / "discussion.md").write_text(
            "# Discussion\n\nTest.\n", encoding="utf-8"
        )

        cfg = {
            "paths": {
                "discussion_file": "discussion.md",
                "plan_dir": "plan/",
                "reviews_dir": "reviews/",
            },
            "roles": {
                "discussion-review": {
                    "holistic": {
                        "rounds": 1,
                        "reviewer": "config-reviewer-should-not-be-used",
                        "large_prompt": {
                            "threshold_ktok": 0,
                            "reviewer": "large-prompt-reviewer",
                        },
                    },
                },
            },
        }

        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            write_local_overlay(
                mill_dir,
                **{
                    "override-reviewer": {
                        "type": "single",
                        "provider": "test_stub",
                        "model": "unused-test-stub-model",
                        "tooluse": False,
                        "effort": "max",
                    },
                    "large-prompt-reviewer": {
                        "type": "single",
                        "provider": "test_stub",
                        "model": "unused-test-stub-model",
                        "tooluse": False,
                        "effort": "low",
                    },
                },
            )
            stub.seed([(APPROVE_TEXT, "sid-run-large-prompt")])
            r = discussion_run(
                cfg, SLUG, mill_dir, project_root, wiki_root,
                reviewer_override="override-reviewer",
            )
            assert r.verdict == "APPROVE", f"expected APPROVE, got {r.verdict}"
            dispatched_effort = stub.captured_prompts()[-1][1]["effort"]
            assert dispatched_effort == "max", (
                f"expected dispatched effort 'max' (override-reviewer's, not "
                f"large-prompt-reviewer's 'low'), got {dispatched_effort!r}"
            )
            print(
                "PASS run() reviewer_override large-prompt skip: dispatched "
                "spec is the override's, not the large-prompt fallback's"
            )
        except AssertionError as exc:
            errors += 1
            print(
                f"FAIL run() reviewer_override large-prompt skip: {exc}",
                file=sys.stderr,
            )
        except Exception as exc:
            errors += 1
            print(
                f"FAIL run() reviewer_override large-prompt skip (unexpected "
                f"{type(exc).__name__}): {exc}",
                file=sys.stderr,
            )
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # cost metadata: happy path -- duration_s/tool_calls/cost_usd surface
    # in reviews[0] and get written into the review file's yaml header
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        mill_dir, project_root, wiki_root = _make_fixture(tmpdir)
        (project_root / "discussion.md").write_text(
            "# Discussion\n\nTest.\n", encoding="utf-8"
        )

        cfg = {
            "paths": {
                "discussion_file": "discussion.md",
                "plan_dir": "plan/",
                "reviews_dir": "reviews/",
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
            stub.seed([(APPROVE_TEXT, "sid-cost-happy")])
            r = discussion_run(cfg, SLUG, mill_dir, project_root, wiki_root)
            assert r.verdict == "APPROVE", f"expected APPROVE, got {r.verdict}"
            entry = r.reviews[0]
            # The stub's ReviewerCallResult carries duration_s=0.0 (a real in-process call
            # that took no measurable time) and tool_calls/cost_usd=None (unsupported signals).
            assert entry["duration_s"] == 0.0, (
                f"expected duration_s=0.0, got {entry['duration_s']!r}"
            )
            assert entry["tool_calls"] is None, (
                f"expected tool_calls=None, got {entry['tool_calls']!r}"
            )
            assert entry["cost_usd"] is None, (
                f"expected cost_usd=None, got {entry['cost_usd']!r}"
            )
            file_text = Path(entry["file"]).read_text(encoding="utf-8")
            assert "duration_s:" in file_text, (
                f"expected 'duration_s:' line in written review file, got:\n{file_text}"
            )
            print(
                "PASS cost metadata happy path: reviews[0] carries duration_s/tool_calls/"
                "cost_usd and the written file's yaml header carries duration_s:"
            )
        except AssertionError as exc:
            errors += 1
            print(f"FAIL cost metadata happy path: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(
                f"FAIL cost metadata happy path (unexpected {type(exc).__name__}): {exc}",
                file=sys.stderr,
            )
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # cost metadata: call-failure ERROR -- LLMError's duration_s surfaces
    # on the synthetic ERROR entry; file stays None (call never returned)
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        mill_dir, project_root, wiki_root = _make_fixture(tmpdir)
        (project_root / "discussion.md").write_text(
            "# Discussion\n\nTest.\n", encoding="utf-8"
        )

        cfg = {
            "paths": {
                "discussion_file": "discussion.md",
                "plan_dir": "plan/",
                "reviews_dir": "reviews/",
            },
            "roles": {
                "discussion-review": {
                    "holistic": {"rounds": 5, "reviewer": "test_stub"},
                },
            },
        }

        orig_dir = os.getcwd()
        os.chdir(project_root)
        original_run = stub.run

        def _raise_with_duration(prompt_text, **kw):
            raise LLMError("seeded boom", duration_s=12.5)

        stub.run = _raise_with_duration
        stub.seed([])  # clear prompts log
        try:
            r = discussion_run(cfg, SLUG, mill_dir, project_root, wiki_root)
            assert r.verdict == "ERROR", f"expected ERROR, got {r.verdict}"
            entry = r.reviews[0]
            assert entry["duration_s"] == 12.5, (
                f"expected duration_s=12.5, got {entry['duration_s']!r}"
            )
            assert entry["tool_calls"] is None, (
                f"expected tool_calls=None, got {entry['tool_calls']!r}"
            )
            assert entry["cost_usd"] is None, (
                f"expected cost_usd=None, got {entry['cost_usd']!r}"
            )
            assert entry["file"] is None, f"expected file=None, got {entry['file']!r}"
            print(
                "PASS cost metadata call-failure ERROR: LLMError.duration_s surfaces on "
                "the synthetic ERROR entry with file=None"
            )
        except AssertionError as exc:
            errors += 1
            print(f"FAIL cost metadata call-failure ERROR: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(
                f"FAIL cost metadata call-failure ERROR (unexpected {type(exc).__name__}): {exc}",
                file=sys.stderr,
            )
        finally:
            stub.run = original_run
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # cost metadata: parse-failure ERROR -- a real ReviewerCallResult's
    # metrics survive into both the ERROR entry and the raw file's
    # yaml header, injected via apply_cost_metadata (no guard needed)
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        mill_dir, project_root, wiki_root = _make_fixture(tmpdir)
        (project_root / "discussion.md").write_text(
            "# Discussion\n\nTest.\n", encoding="utf-8"
        )

        cfg = {
            "paths": {
                "discussion_file": "discussion.md",
                "plan_dir": "plan/",
                "reviews_dir": "reviews/",
            },
            "roles": {
                "discussion-review": {
                    "holistic": {"rounds": 5, "reviewer": "test_stub"},
                },
            },
        }

        orig_dir = os.getcwd()
        os.chdir(project_root)
        original_run = stub.run
        unparseable_with_fence = (
            "# Review\n\n```yaml\nnot_a_verdict: true\n```\n"
        )

        def _return_unparseable(prompt_text, **kw):
            return ReviewerCallResult(
                text=unparseable_with_fence,
                session_id="sid-parse-fail",
                duration_s=7.25,
                tool_calls=3,
                cost_usd=0.0123,
            )

        stub.run = _return_unparseable
        stub.seed([])  # clear prompts log
        try:
            r = discussion_run(cfg, SLUG, mill_dir, project_root, wiki_root)
            assert r.verdict == "ERROR", f"expected ERROR, got {r.verdict}"
            entry = r.reviews[0]
            assert entry["duration_s"] == 7.25, (
                f"expected duration_s=7.25, got {entry['duration_s']!r}"
            )
            assert entry["tool_calls"] == 3, (
                f"expected tool_calls=3, got {entry['tool_calls']!r}"
            )
            assert entry["cost_usd"] == 0.0123, (
                f"expected cost_usd=0.0123, got {entry['cost_usd']!r}"
            )
            assert entry["file"] is not None, "expected a written raw file, got file=None"
            file_text = Path(entry["file"]).read_text(encoding="utf-8")
            assert "duration_s: 7.2" in file_text, (
                f"expected injected 'duration_s:' line in raw file, got:\n{file_text}"
            )
            print(
                "PASS cost metadata parse-failure ERROR: metrics survive into both the "
                "ERROR entry and the raw file's injected yaml header"
            )
        except AssertionError as exc:
            errors += 1
            print(f"FAIL cost metadata parse-failure ERROR: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(
                f"FAIL cost metadata parse-failure ERROR (unexpected {type(exc).__name__}): {exc}",
                file=sys.stderr,
            )
        finally:
            stub.run = original_run
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # cost metadata: parse-failure ERROR variant with no yaml fence at all
    # -- apply_cost_metadata's terminal fallback leaves the raw text
    # unchanged, and the run does not raise
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        mill_dir, project_root, wiki_root = _make_fixture(tmpdir)
        (project_root / "discussion.md").write_text(
            "# Discussion\n\nTest.\n", encoding="utf-8"
        )

        cfg = {
            "paths": {
                "discussion_file": "discussion.md",
                "plan_dir": "plan/",
                "reviews_dir": "reviews/",
            },
            "roles": {
                "discussion-review": {
                    "holistic": {"rounds": 5, "reviewer": "test_stub"},
                },
            },
        }

        orig_dir = os.getcwd()
        os.chdir(project_root)
        original_run = stub.run
        no_fence_text = "Raw prose with no yaml fence at all.\n"

        def _return_no_fence(prompt_text, **kw):
            return ReviewerCallResult(
                text=no_fence_text,
                session_id="sid-no-fence",
                duration_s=3.0,
                tool_calls=1,
                cost_usd=0.001,
            )

        stub.run = _return_no_fence
        stub.seed([])  # clear prompts log
        try:
            r = discussion_run(cfg, SLUG, mill_dir, project_root, wiki_root)
            assert r.verdict == "ERROR", f"expected ERROR, got {r.verdict}"
            entry = r.reviews[0]
            assert entry["file"] is not None, "expected a written raw file, got file=None"
            file_text = Path(entry["file"]).read_text(encoding="utf-8")
            assert file_text == no_fence_text, (
                f"expected the raw file to be written unchanged (no fence to anchor "
                f"on), got:\n{file_text!r}"
            )
            print(
                "PASS cost metadata parse-failure ERROR (no yaml fence): raw file is "
                "written unchanged and the run does not raise"
            )
        except AssertionError as exc:
            errors += 1
            print(
                f"FAIL cost metadata parse-failure ERROR (no yaml fence): {exc}",
                file=sys.stderr,
            )
        except Exception as exc:
            errors += 1
            print(
                f"FAIL cost metadata parse-failure ERROR (no yaml fence) (unexpected "
                f"{type(exc).__name__}): {exc}",
                file=sys.stderr,
            )
        finally:
            stub.run = original_run
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # brief-path nested-layout: prepare stage writes brief under hub_dir (#553)
    # ------------------------------------------------------------------
    errors += test_brief_path_nested_layout()

    # ------------------------------------------------------------------
    # project_root/hub_dir rebind: briefs_dir resolves under resolve_active_hub, not resolve_hub_path's decoy (#675)
    # ------------------------------------------------------------------
    errors += test_project_root_rebind_uses_resolve_active_hub_not_resolve_hub_path()

    # ------------------------------------------------------------------
    # finalize() direct call: parse_verdict failure tags error_kind: "reviewer"
    # (reviewer-kind-finalize-wrappers Shared Decision).
    # Calls finalize() directly (not via discussion_run/run()) so the assertion exercises
    # exactly the except ReviewError entry this batch's Card 9 changed.
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        reviews_dir = tmpdir / "reviews"
        try:
            r = _review_discussion.finalize(
                {},
                "test-slug",
                "# Raw prose without any yaml block\n\nNo verdict here.",
                round_n=1,
                reviews_dir=reviews_dir,
                mill_dir=reviews_dir.parent,
                project_root=reviews_dir.parent,
                wiki_root=reviews_dir.parent,
            )
            assert r.verdict == "ERROR", f"expected ERROR, got {r.verdict}"
            assert r.reviews[0]["error_kind"] == "reviewer", (
                f"expected error_kind 'reviewer', got {r.reviews[0].get('error_kind')!r}"
            )
            print("PASS finalize() parse_verdict failure tags error_kind: reviewer")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL finalize() error_kind: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL finalize() error_kind (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All _review_discussion flow tests passed.")
    return 0


def test_brief_path_nested_layout() -> int:
    """Verify that the prepare stage routes the brief under hub_dir, not git_root.

    Creates a nested layout where hub_dir is a subdirectory of git_root, then loads
    millpy-review-discussion via importlib and calls main().
    Inspects the recorded resolve_task_path calls to confirm the first argument is hub_dir.

    A reversion of the Card 3 fix (changing hub_dir back to git_root) causes the assertion to fail
    because resolve_task_path is called with git_root instead.

    Returns 0 on success, 1 on failure (matching the errors-accumulator convention used throughout
    this file).
    """
    import importlib.util
    import tempfile
    from pathlib import Path
    from unittest.mock import MagicMock, patch

    scripts_dir = HUB / "plugins" / "mill" / "scripts"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        # Nested layout: hub_dir is a subdirectory of git_root.
        git_root = tmp / "repo"
        hub_dir = git_root / "src" / "proj"
        hub_dir.mkdir(parents=True)

        # Build minimal config dict with the keys that the prepare branch reads.
        minimal_cfg = {
            "paths": {
                "discussion_file": "discussion.md",
                "reviews_dir": "_mill/reviews/",
            },
            "roles": {
                "discussion-review": {
                    "holistic": {"rounds": 1},
                },
            },
        }

        # Build all mock objects that main() imports inside its body.
        mock_paths = MagicMock()
        mock_paths.resolve_hub_path.return_value = hub_dir
        mock_paths.resolve_git_root.return_value = git_root
        mock_paths.resolve_wiki_path.return_value = git_root / "wiki"
        # The project_root/hub_dir rebind (Card 15) calls resolve_container_path and resolve_active_hub after slug resolution, superseding hub_dir for every subsequent use -- mock them to the same hub_dir this test already exercises so the pre-existing assertions below (which compare against the local hub_dir variable) keep passing after the rebind.
        mock_paths.resolve_container_path.return_value = git_root.parent
        mock_paths.resolve_active_hub.return_value = hub_dir
        # side_effect records calls and returns a real Path so downstream code can str() it.
        mock_paths.resolve_task_path.side_effect = lambda root, path: (
            Path(str(root)) / path.lstrip("/")
        )

        mock_review_common = MagicMock()
        mock_review_common.load_config.return_value = minimal_cfg
        mock_review_common.discover_round.return_value = 1
        mock_review_common.find_active_slug.return_value = "test-slug"
        mock_review_common.ReviewError = Exception

        mock_review_discussion = MagicMock()
        mock_review_discussion.prepare.return_value = {
            "scope": "holistic",
            "round": 1,
            "prompt_text": "prompt",
            "model": "default",
        }

        mock_agent_dispatch = MagicMock()
        mock_agent_dispatch.write_brief.return_value = hub_dir / "_mill/briefs/brief.md"
        mock_agent_dispatch.SUBAGENT_REVIEWER = "reviewer"
        mock_agent_dispatch.model_to_tier.return_value = "default"

        mock_reviewers = MagicMock()
        mock_reviewers.ReviewerError = Exception

        mock_review_cli = MagicMock()

        injected_modules = {
            "_paths": mock_paths,
            "_review_common": mock_review_common,
            "_review_discussion": mock_review_discussion,
            "_agent_dispatch": mock_agent_dispatch,
            "_reviewers": mock_reviewers,
            "_review_cli": mock_review_cli,
        }

        # Insert mocks before loading the module so that the import-inside-main() pattern picks up the mocks from sys.modules rather than loading real modules.
        with patch.dict(sys.modules, injected_modules):
            spec = importlib.util.spec_from_file_location(
                "millpy_review_discussion",
                scripts_dir / "millpy-review-discussion.py",
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            # Redirect sys.argv so main() enters the prepare branch.
            with patch("sys.argv", ["prog", "--stage", "prepare"]):
                try:
                    mod.main()
                except (TypeError, SystemExit, Exception):
                    # The prepare branch calls json.dumps(envelope);
                    # a bare MagicMock return from write_brief causes TypeError at that point.
                    # The resolve_task_path call is already recorded before the crash.
                    pass

        # Inspect recorded calls: find the one whose path arg starts with "_mill/briefs/".
        call_args_list = mock_paths.resolve_task_path.call_args_list
        briefs_call = None
        for call in call_args_list:
            positional = call[0]
            if len(positional) >= 2 and str(positional[1]).startswith("_mill/briefs/"):
                briefs_call = positional
                break

        if briefs_call is None:
            print(
                "FAIL: test_brief_path_nested_layout: resolve_task_path was never called"
                " with a '_mill/briefs/' path argument",
                file=sys.stderr,
            )
            return 1

        actual_root = briefs_call[0]
        if actual_root != hub_dir:
            print(
                f"FAIL: test_brief_path_nested_layout: expected resolve_task_path first arg"
                f" to be hub_dir ({hub_dir}), got {actual_root}",
                file=sys.stderr,
            )
            return 1

        if actual_root == git_root:
            print(
                "FAIL: test_brief_path_nested_layout: first arg equals git_root"
                " (assertion is vacuous — hub_dir and git_root are the same object)",
                file=sys.stderr,
            )
            return 1

        print(
            "PASS: discussion-review brief path is under hub_dir not git_root in nested layout"
        )
        return 0


def test_project_root_rebind_uses_resolve_active_hub_not_resolve_hub_path() -> int:
    """hub_dir rebinds to resolve_active_hub's value, not resolve_hub_path's escaped one.

    Modeled on test_brief_path_nested_layout,
    but instead of hub_dir vs. git_root, this test distinguishes resolve_hub_path's (decoy) return
    value from resolve_active_hub's (corrected active task worktree) return value -- the two values
    the Card 15 rebind is meant to keep distinct.
    resolve_hub_path returns a decoy directory standing in for the pre-rebind escape (e.g.
    the main worktree resolve_hub_path() falls back to);
    resolve_active_hub returns a separate, real task-worktree directory.
    briefs_dir must resolve under the resolve_active_hub value, proving hub_dir/project_root was
    rebound after slug resolution and not left at resolve_hub_path's original value.

    A reversion of the Card 15 fix (never calling resolve_active_hub) causes the assertion to fail
    because resolve_task_path is called with the decoy directory instead.

    Returns 0 on success, 1 on failure (matching the errors-accumulator convention used throughout
    this file).
    """
    import importlib.util
    import tempfile
    from pathlib import Path
    from unittest.mock import MagicMock, patch

    scripts_dir = HUB / "plugins" / "mill" / "scripts"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        decoy_dir = tmp / "decoy-hub-path"
        decoy_dir.mkdir(parents=True)
        corrected_dir = tmp / "corrected-active-worktree"
        corrected_dir.mkdir(parents=True)

        minimal_cfg = {
            "paths": {
                "discussion_file": "discussion.md",
                "reviews_dir": "_mill/reviews/",
            },
            "roles": {
                "discussion-review": {
                    "holistic": {"rounds": 1},
                },
            },
        }

        mock_paths = MagicMock()
        mock_paths.resolve_hub_path.return_value = decoy_dir
        mock_paths.resolve_git_root.return_value = decoy_dir
        mock_paths.resolve_wiki_path.return_value = decoy_dir / "wiki"
        mock_paths.resolve_container_path.return_value = tmp
        mock_paths.resolve_active_hub.return_value = corrected_dir
        mock_paths.resolve_task_path.side_effect = lambda root, path: (
            Path(str(root)) / path.lstrip("/")
        )

        mock_review_common = MagicMock()
        mock_review_common.load_config.return_value = minimal_cfg
        mock_review_common.discover_round.return_value = 1
        mock_review_common.find_active_slug.return_value = "test-slug"
        mock_review_common.ReviewError = Exception

        mock_review_discussion = MagicMock()
        mock_review_discussion.prepare.return_value = {
            "scope": "holistic",
            "round": 1,
            "prompt_text": "prompt",
            "model": "default",
        }

        mock_agent_dispatch = MagicMock()
        mock_agent_dispatch.write_brief.return_value = corrected_dir / "_mill/briefs/brief.md"
        mock_agent_dispatch.SUBAGENT_REVIEWER = "reviewer"
        mock_agent_dispatch.model_to_tier.return_value = "default"

        mock_reviewers = MagicMock()
        mock_reviewers.ReviewerError = Exception

        mock_review_cli = MagicMock()

        injected_modules = {
            "_paths": mock_paths,
            "_review_common": mock_review_common,
            "_review_discussion": mock_review_discussion,
            "_agent_dispatch": mock_agent_dispatch,
            "_reviewers": mock_reviewers,
            "_review_cli": mock_review_cli,
        }

        with patch.dict(sys.modules, injected_modules):
            spec = importlib.util.spec_from_file_location(
                "millpy_review_discussion",
                scripts_dir / "millpy-review-discussion.py",
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            with patch("sys.argv", ["prog", "--stage", "prepare"]):
                try:
                    mod.main()
                except (TypeError, SystemExit, Exception):
                    # json.dumps(envelope) may raise TypeError on a bare MagicMock field;
                    # the resolve_active_hub/resolve_task_path calls are already recorded before any such crash.
                    pass

        # Confirm resolve_active_hub was actually invoked (the rebind's call).
        if not mock_paths.resolve_active_hub.called:
            print(
                "FAIL: test_project_root_rebind_uses_resolve_active_hub_not_resolve_hub_path:"
                " _paths.resolve_active_hub was never called",
                file=sys.stderr,
            )
            return 1

        call_args_list = mock_paths.resolve_task_path.call_args_list
        briefs_call = None
        for call in call_args_list:
            positional = call[0]
            if len(positional) >= 2 and str(positional[1]).startswith("_mill/briefs/"):
                briefs_call = positional
                break

        if briefs_call is None:
            print(
                "FAIL: test_project_root_rebind_uses_resolve_active_hub_not_resolve_hub_path:"
                " resolve_task_path was never called with a '_mill/briefs/' path argument",
                file=sys.stderr,
            )
            return 1

        actual_root = briefs_call[0]
        if actual_root != corrected_dir:
            print(
                f"FAIL: test_project_root_rebind_uses_resolve_active_hub_not_resolve_hub_path:"
                f" expected resolve_task_path first arg to be resolve_active_hub's return"
                f" value ({corrected_dir}), got {actual_root}",
                file=sys.stderr,
            )
            return 1

        if actual_root == decoy_dir:
            print(
                "FAIL: test_project_root_rebind_uses_resolve_active_hub_not_resolve_hub_path:"
                " first arg equals resolve_hub_path's decoy value (rebind did not supersede it)",
                file=sys.stderr,
            )
            return 1

        print(
            "PASS: discussion-review briefs_dir resolves under resolve_active_hub's value,"
            " not resolve_hub_path's decoy"
        )
        return 0


if __name__ == "__main__":
    sys.exit(main())
