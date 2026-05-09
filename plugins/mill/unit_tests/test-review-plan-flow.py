"""Unit-test flow harness for _review_plan.run.

Uses _reviewer_test_stub as the reviewer backend. All tests run in-process
with no real LLM, no network calls. Covers:
  - Per-scope round counter (#21/#62/#63)
  - creates_union suppression in parallel per-batch section (#60)
  - Hard-fail surfaces as ERROR per-batch entry / ReviewError in holistic (#41)
  - NEED_CONTEXT resume fallback in per-batch and holistic (#5/#7)
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _reviewer_test_stub as stub  # noqa: E402
from _llm_claude import LLMError  # noqa: E402
from _review_plan import run as plan_run  # noqa: E402
from _review_common import ReviewError  # noqa: E402

SLUG = "test-slug"

APPROVE_TEXT = "# Review: test\n\n```yaml\nverdict: APPROVE\n```\n"

# References src/a.py which the fixtures create on disk — used by NEED_CONTEXT tests.
NEED_CONTEXT_TEXT = (
    "# Review: test\n\n"
    "```yaml\nverdict: NEED_CONTEXT\n```\n\n"
    "## Missing context\n\n"
    "- `src/a.py` — need this file\n"
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _make_overview(batches: list[tuple[str, str]]) -> str:
    """Return 00-overview.md text with the given (name, file) batch entries."""
    entries = []
    for name, file_ in batches:
        entries.append(
            f"  - name: {name}\n    file: {file_}\n    depends-on: []\n    verify: null"
        )
    batch_list = "\n".join(entries)
    return (
        "# Overview: test-slug\n\n"
        "```yaml\n"
        f"task: test\nslug: {SLUG}\nroot: \"\"\n"
        "```\n\n"
        "## Batch Index\n\n"
        "```yaml\n"
        f"batches:\n{batch_list}\n"
        "```\n"
    )


def _make_batch_file(
    name: str,
    reads: list[str],
    creates: list[str],
    *,
    deletes: list[str] | None = None,
) -> str:
    """Return batch file text (single-line Context:/Edits:/Creates:/Deletes: form)."""
    reads_part = ", ".join(f"`{r}`" for r in reads) if reads else "none"
    creates_part = ", ".join(f"`{c}`" for c in creates) if creates else "none"
    deletes_part = ", ".join(f"`{d}`" for d in deletes) if deletes else "none"
    return (
        f"# Batch: {name}\n\n"
        "```yaml\n"
        f"task: test\nbatch: {name}\ncards: 1\nverify: null\ndepends-on: []\n"
        "```\n\n"
        "## Cards\n\n### Card 1\n\n"
        f"- **Context:** {reads_part}\n"
        "- **Edits:** none\n"
        f"- **Creates:** {creates_part}\n"
        f"- **Deletes:** {deletes_part}\n"
    )


def _make_plan_fixture(
    tmp_path: Path,
    batch_specs: list[tuple[str, str, list[str], list[str]]],
    *,
    skip_create: set[str] | None = None,
) -> tuple[Path, Path, Path, dict]:
    """Build a plan-review fixture under tmp_path.

    batch_specs = [(name, file, reads, creates)].
    Reads paths are created on disk unless listed in skip_create (for
    tests that deliberately need missing refs).
    Returns (mill_dir, wiki_root, project_root, cfg with holistic enabled).
    project_root is the worktree path; callers must os.chdir(project_root).
    """
    skip_create = skip_create or set()
    worktree = tmp_path / "container" / "wts" / SLUG
    worktree.mkdir(parents=True)
    subprocess.run(["git", "-C", str(worktree), "init"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(worktree), "checkout", "-b", f"hanf/{SLUG}"], capture_output=True)
    mill_dir = worktree / ".millhouse"
    mill_dir.mkdir(parents=True, exist_ok=True)
    wiki_root = tmp_path / "wiki"
    wiki_root.mkdir(parents=True, exist_ok=True)
    (wiki_root / "config.yaml").write_text(
        "paths:\n  discussion_file: discussion.md\n  plan_dir: plan/\n  reviews_dir: reviews/\n"
        "spawn:\n  branch_prefix: \"hanf/\"\n",
        encoding="utf-8",
    )
    (wiki_root / "Home.md").write_text(
        f"## Test Task\n[[{SLUG}]] [active]\n\n_body_\n", encoding="utf-8"
    )
    (mill_dir / "config.local.yaml").write_text(
        f"paths:\n  wiki: '{wiki_root.as_posix()}'\n", encoding="utf-8"
    )
    project_root = worktree

    plan_dir = worktree / "plan"
    plan_dir.mkdir(parents=True)

    (plan_dir / "00-overview.md").write_text(
        _make_overview([(n, f) for n, f, _, _ in batch_specs]),
        encoding="utf-8",
    )
    for name, file_, reads, creates in batch_specs:
        (plan_dir / file_).write_text(
            _make_batch_file(name, reads, creates), encoding="utf-8"
        )
        for rf in reads:
            if rf not in skip_create:
                p = project_root / rf
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("# placeholder", encoding="utf-8")

    cfg = {
        "paths": {
            "discussion_file": "discussion.md",
            "plan_dir":        "plan/",
            "reviews_dir":     "reviews/",
        },
        "review": {
            "plan": {"rounds": 3, "batch": "test_stub", "holistic": "test_stub"},
        },
        "llm": {"bulk_timeout": None, "holistic_timeout": None},
    }
    return mill_dir, wiki_root, project_root, cfg


def _seed_approve(n: int) -> None:
    """Seed n approve responses on the stub."""
    stub.seed([(APPROVE_TEXT, f"sid-{i + 1}") for i in range(n)])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def main() -> int:
    errors = 0

    # ------------------------------------------------------------------
    # Test 1 — per-scope round counter on re-invocation
    # 3 per-batch + 1 holistic = 4 responses per run.
    # After re-invocation all scopes advance to r2 independently.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        batch_specs = [
            ("alpha", "01-alpha.md", ["src/a.py"], []),
            ("beta",  "02-beta.md",  ["src/b.py"], []),
            ("gamma", "03-gamma.md", ["src/c.py"], []),
        ]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(Path(tmpdir), batch_specs)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            # First run — each scope gets r1
            _seed_approve(4)
            r = plan_run(cfg, SLUG, mill_dir, wiki_root, project_root)
            assert r.verdict == "APPROVE", f"expected APPROVE, got {r.verdict}"
            assert len(r.reviews) == 4, f"expected 4 reviews, got {len(r.reviews)}"
            per_batch = [rv for rv in r.reviews if rv["scope"] != "holistic"]
            holistic = next(rv for rv in r.reviews if rv["scope"] == "holistic")
            for rv in per_batch:
                fname = Path(rv["file"]).name
                assert f"plan-review-{rv['scope']}-r1" in fname, (
                    f"expected r1 in filename, got {fname}"
                )
            assert "plan-review-r1" in Path(holistic["file"]).name, (
                f"unexpected holistic filename: {Path(holistic['file']).name}"
            )
            assert str(project_root / "reviews") in holistic["file"], (
                f"review file must be under worktree/reviews/, got {holistic['file']!r}"
            )
            print("PASS test1a: first run — all scopes r1")

            # Second run — per-batch batches all APPROVE → carryforward (r1 files);
            # only holistic fires fresh (r2). Skip-approved scan active.
            _seed_approve(1)  # only holistic needs a response
            r2 = plan_run(cfg, SLUG, mill_dir, wiki_root, project_root)
            assert r2.verdict == "APPROVE"
            assert len(r2.reviews) == 4, f"expected 4 reviews, got {len(r2.reviews)}"
            per_batch2 = [rv for rv in r2.reviews if rv["scope"] != "holistic"]
            holistic2 = next(rv for rv in r2.reviews if rv["scope"] == "holistic")
            # Per-batch entries are carryforwards: r1 files, session_id None
            for rv in per_batch2:
                fname = Path(rv["file"]).name
                assert f"plan-review-{rv['scope']}-r1" in fname, (
                    f"expected r1 carryforward in filename, got {fname}"
                )
                assert rv["session_id"] is None, (
                    f"carryforward entry should have session_id=None, got {rv['session_id']!r}"
                )
            # Holistic is fresh: r2 file, non-None session_id
            assert "plan-review-r2" in Path(holistic2["file"]).name, (
                f"unexpected holistic r2 filename: {Path(holistic2['file']).name}"
            )
            assert holistic2["session_id"] is not None, "holistic should have non-None session_id"
            print("PASS test1b: second run — per-batch carryforward (r1), holistic fresh (r2)")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test1: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test1 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 2 — partial re-invocation (only alpha-r1 file pre-exists)
    # alpha must be r2; beta/gamma must be r1; holistic must be r2.
    # A holistic-r1 file is also pre-created so detect_resume_round
    # returns None (completed round, not interrupted mid-round).
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        batch_specs = [
            ("alpha", "01-alpha.md", ["src/a.py"], []),
            ("beta",  "02-beta.md",  ["src/b.py"], []),
            ("gamma", "03-gamma.md", ["src/c.py"], []),
        ]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(Path(tmpdir), batch_specs)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            # Pre-create alpha-r1 (malformed) and holistic-r1 to simulate a
            # completed round where alpha's result was written but was garbled.
            reviews_dir = project_root / "reviews"
            reviews_dir.mkdir(parents=True)
            (reviews_dir / "20260418-000000-plan-review-01-alpha-r1.md").write_text(
                "# stub r1 review", encoding="utf-8"
            )
            (reviews_dir / "20260418-000001-plan-review-r1.md").write_text(
                APPROVE_TEXT, encoding="utf-8"
            )

            _seed_approve(4)
            r = plan_run(cfg, SLUG, mill_dir, wiki_root, project_root)
            assert r.verdict == "APPROVE"
            # alpha should be r2; beta/gamma r1; holistic r2 (prior holistic was r1)
            rv_alpha = next(rv for rv in r.reviews if rv["scope"] == "01-alpha")
            rv_beta  = next(rv for rv in r.reviews if rv["scope"] == "02-beta")
            rv_gamma = next(rv for rv in r.reviews if rv["scope"] == "03-gamma")
            rv_hol   = next(rv for rv in r.reviews if rv["scope"] == "holistic")
            assert "plan-review-01-alpha-r2" in Path(rv_alpha["file"]).name, (
                f"alpha should be r2, got {Path(rv_alpha['file']).name}"
            )
            assert "plan-review-02-beta-r1" in Path(rv_beta["file"]).name, (
                f"beta should be r1, got {Path(rv_beta['file']).name}"
            )
            assert "plan-review-03-gamma-r1" in Path(rv_gamma["file"]).name, (
                f"gamma should be r1, got {Path(rv_gamma['file']).name}"
            )
            assert "plan-review-r2" in Path(rv_hol["file"]).name, (
                f"holistic should be r2, got {Path(rv_hol['file']).name}"
            )
            print("PASS test2: partial re-invocation — alpha r2, beta/gamma r1, holistic r2 (independent per-scope)")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test2: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test2 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 3 — creates_union suppression in per-batch parallel section (#60)
    # beta Reads a file alpha Creates; file not on disk. No ReviewError expected.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        batch_specs = [
            ("alpha", "01-alpha.md", ["src/a.py"], ["generated/by_alpha.py"]),
            ("beta",  "02-beta.md",  ["generated/by_alpha.py"], []),
            ("gamma", "03-gamma.md", ["src/c.py"], []),
        ]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(
            Path(tmpdir), batch_specs, skip_create={"generated/by_alpha.py"}
        )
        orig_dir = os.getcwd()
        os.chdir(project_root)
        _seed_approve(4)
        try:
            r = plan_run(cfg, SLUG, mill_dir, wiki_root, project_root)
            assert r.verdict == "APPROVE", f"expected APPROVE, got {r.verdict}"
            for rv in r.reviews:
                assert rv["verdict"] == "APPROVE", (
                    f"scope {rv['scope']} verdict {rv['verdict']} != APPROVE"
                )
            print("PASS test3: creates_union suppresses missing cross-batch ref in parallel plan review (#60)")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test3: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test3 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 4 — hard-fail surfaces as ERROR per-batch entry, not full-run failure
    # alpha (clean) succeeds; beta (bad ref) → ERROR entry; holistic disabled.
    # Aggregate must be REQUEST_CHANGES (not ReviewError), since not all ERROR.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        batch_specs = [
            ("alpha", "01-alpha.md", ["src/a.py"], []),
            ("beta",  "02-beta.md",  ["nonexistent/path.py"], []),
        ]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(
            Path(tmpdir), batch_specs, skip_create={"nonexistent/path.py"}
        )
        cfg4 = dict(cfg)
        cfg4["review"] = dict(cfg["review"])
        cfg4["review"]["plan"] = dict(cfg["review"]["plan"])
        cfg4["review"]["plan"]["holistic"] = None  # disable holistic for isolation

        orig_dir = os.getcwd()
        os.chdir(project_root)
        # 1 approve for alpha; beta fails before calling reviewer
        _seed_approve(1)
        try:
            r = plan_run(cfg4, SLUG, mill_dir, wiki_root, project_root)
            assert r.verdict == "REQUEST_CHANGES", (
                f"expected REQUEST_CHANGES, got {r.verdict}"
            )
            rv_beta = next((rv for rv in r.reviews if rv["scope"] == "02-beta"), None)
            assert rv_beta is not None, "no beta entry in reviews"
            assert rv_beta["verdict"] == "ERROR", (
                f"beta entry verdict should be ERROR, got {rv_beta['verdict']}"
            )
            assert "referenced path not found" in rv_beta.get("error", ""), (
                f"error message missing 'referenced path not found': {rv_beta.get('error')}"
            )
            assert "nonexistent/path.py" in rv_beta.get("error", ""), (
                f"path not in error message: {rv_beta.get('error')}"
            )
            print("PASS test4: per-batch ReviewError → ERROR entry, aggregate REQUEST_CHANGES (#41)")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test4: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test4 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 5 — hard-fail in holistic block surfaces as ReviewError
    # alpha + gamma succeed; beta has bad ref → ERROR entry (no reviewer call).
    # Holistic resolver encounters beta's bad ref → ReviewError propagates.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        batch_specs = [
            ("alpha", "01-alpha.md", ["src/a.py"], []),
            ("beta",  "02-beta.md",  ["nonexistent/path.py"], []),
            ("gamma", "03-gamma.md", ["src/c.py"], []),
        ]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(
            Path(tmpdir), batch_specs, skip_create={"nonexistent/path.py"}
        )
        orig_dir = os.getcwd()
        os.chdir(project_root)
        # alpha + gamma consume one each; holistic resolver fails before reviewer runs.
        # The third seeded response is never consumed.
        _seed_approve(3)
        try:
            plan_run(cfg, SLUG, mill_dir, wiki_root, project_root)
            errors += 1
            print("FAIL test5: expected ReviewError from holistic, none raised", file=sys.stderr)
        except ReviewError as exc:
            msg = str(exc)
            try:
                assert "referenced path not found" in msg, (
                    f"error missing 'referenced path not found': {msg}"
                )
                assert "nonexistent/path.py" in msg, f"path not in error: {msg}"
                prompts = stub.captured_prompts()
                assert len(prompts) == 2, (
                    f"expected 2 prompts (alpha + gamma), got {len(prompts)}"
                )
                print("PASS test5: holistic resolve_ref_paths raises ReviewError, reviewer never called (#41)")
            except AssertionError as ae:
                errors += 1
                print(f"FAIL test5 (wrong assertion): {ae}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test5 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 6 — NEED_CONTEXT resume fallback in per-batch (#5/#7)
    # Single batch (alpha) + holistic. Alpha retries once → APPROVE.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        batch_specs = [("alpha", "01-alpha.md", ["src/a.py"], [])]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(
            Path(tmpdir), batch_specs
        )
        orig_dir = os.getcwd()
        os.chdir(project_root)
        # alpha: NEED_CONTEXT → retry APPROVE; holistic: APPROVE
        stub.seed([
            (NEED_CONTEXT_TEXT, "sid-1"),  # alpha first call
            (APPROVE_TEXT,      "sid-2"),  # alpha retry
            (APPROVE_TEXT,      "sid-3"),  # holistic
        ])
        try:
            r = plan_run(cfg, SLUG, mill_dir, wiki_root, project_root)
            assert r.verdict == "APPROVE", f"expected APPROVE, got {r.verdict}"
            rv_alpha = next(rv for rv in r.reviews if rv["scope"] == "01-alpha")
            assert rv_alpha["verdict"] == "APPROVE", (
                f"alpha verdict should be APPROVE after retry, got {rv_alpha['verdict']}"
            )
            prompts = stub.captured_prompts()
            # alpha first call + alpha retry + holistic = 3
            assert len(prompts) == 3, f"expected 3 captured prompts, got {len(prompts)}"
            # The retry prompt is captured at index 1 (alpha retry)
            retry_text, retry_kwargs = prompts[1]
            assert retry_text.startswith("## Re-attached files"), (
                f"retry prompt must start with '## Re-attached files': {retry_text[:80]!r}"
            )
            assert retry_kwargs == {"session_id": "sid-1", "resume": True, "timeout": None, "effort": None}, (
                f"retry kwargs wrong: {retry_kwargs}"
            )
            print("PASS test6: per-batch NEED_CONTEXT retry → APPROVE, holistic unaffected")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test6: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test6 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 7 — NEED_CONTEXT resume fallback in holistic block (#5/#7)
    # Single batch (alpha) succeeds; holistic NEED_CONTEXT → retry APPROVE.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        batch_specs = [("alpha", "01-alpha.md", ["src/a.py"], [])]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(
            Path(tmpdir), batch_specs
        )
        orig_dir = os.getcwd()
        os.chdir(project_root)
        # alpha: APPROVE; holistic: NEED_CONTEXT → retry APPROVE
        stub.seed([
            (APPROVE_TEXT,      "sid-1"),  # alpha
            (NEED_CONTEXT_TEXT, "sid-2"),  # holistic first call
            (APPROVE_TEXT,      "sid-3"),  # holistic retry
        ])
        try:
            r = plan_run(cfg, SLUG, mill_dir, wiki_root, project_root)
            assert r.verdict == "APPROVE", f"expected APPROVE, got {r.verdict}"
            rv_hol = next(rv for rv in r.reviews if rv["scope"] == "holistic")
            assert rv_hol["verdict"] == "APPROVE", (
                f"holistic verdict should be APPROVE after retry, got {rv_hol['verdict']}"
            )
            prompts = stub.captured_prompts()
            # alpha + holistic first + holistic retry = 3
            assert len(prompts) == 3, f"expected 3 captured prompts, got {len(prompts)}"
            # holistic retry is at index 2
            retry_text, retry_kwargs = prompts[2]
            assert retry_text.startswith("## Re-attached files"), (
                f"holistic retry prompt must start with '## Re-attached files': {retry_text[:80]!r}"
            )
            assert retry_kwargs == {"session_id": "sid-2", "resume": True, "timeout": None, "effort": None}, (
                f"holistic retry kwargs wrong: {retry_kwargs}"
            )
            print("PASS test7: holistic NEED_CONTEXT retry → APPROVE")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test7: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test7 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    REQUEST_CHANGES_TEXT = "# Review: test\n\n```yaml\nverdict: REQUEST_CHANGES\n```\n"

    # ------------------------------------------------------------------
    # Test 8 — skip-approved happy path
    # Three batches; 01-a and 03-c are approved in r1; 02-b is not.
    # Stub should fire exactly twice: once for 02-b, once for holistic.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        batch_specs = [
            ("a", "01-a.md", ["src/a.py"], []),
            ("b", "02-b.md", ["src/b.py"], []),
            ("c", "03-c.md", ["src/c.py"], []),
        ]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(Path(tmpdir), batch_specs)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            reviews_dir = project_root / "reviews"
            reviews_dir.mkdir(parents=True, exist_ok=True)
            # 01-a approved in r1
            (reviews_dir / "20260429-000001-plan-review-01-a-r1.md").write_text(
                APPROVE_TEXT, encoding="utf-8"
            )
            # 02-b NOT approved (REQUEST_CHANGES)
            (reviews_dir / "20260429-000002-plan-review-02-b-r1.md").write_text(
                REQUEST_CHANGES_TEXT, encoding="utf-8"
            )
            # 03-c approved in r1
            (reviews_dir / "20260429-000003-plan-review-03-c-r1.md").write_text(
                APPROVE_TEXT, encoding="utf-8"
            )
            # holistic-r1: marks round 1 as complete so detect_resume_round returns None
            (reviews_dir / "20260429-000004-plan-review-r1.md").write_text(
                APPROVE_TEXT, encoding="utf-8"
            )

            # Stub: 1 for 02-b + 1 for holistic = 2 responses
            stub.seed([(APPROVE_TEXT, "sid-fresh-b"), (APPROVE_TEXT, "sid-fresh-hol")])
            r = plan_run(cfg, SLUG, mill_dir, wiki_root, project_root)

            prompts = stub.captured_prompts()
            assert len(prompts) == 2, (
                f"stub should fire exactly twice (02-b + holistic), got {len(prompts)}"
            )
            assert r.verdict == "APPROVE"
            assert len(r.reviews) == 4, f"expected 4 reviews, got {len(r.reviews)}"

            rv_a   = next((rv for rv in r.reviews if rv["scope"] == "01-a"), None)
            rv_b   = next((rv for rv in r.reviews if rv["scope"] == "02-b"), None)
            rv_c   = next((rv for rv in r.reviews if rv["scope"] == "03-c"), None)
            rv_hol = next((rv for rv in r.reviews if rv["scope"] == "holistic"), None)

            assert rv_a is not None, "01-a entry missing"
            assert rv_b is not None, "02-b entry missing"
            assert rv_c is not None, "03-c entry missing"
            assert rv_hol is not None, "holistic entry missing"

            # Carryforward entries
            assert rv_a["session_id"] is None, f"01-a should be carryforward (session_id=None), got {rv_a['session_id']!r}"
            assert rv_a["verdict"] == "APPROVE"
            assert "01-a-r1" in Path(rv_a["file"]).name, f"01-a should point to r1 file, got {Path(rv_a['file']).name}"
            assert rv_c["session_id"] is None, f"03-c should be carryforward, got {rv_c['session_id']!r}"
            assert "03-c-r1" in Path(rv_c["file"]).name

            # Fresh entries
            assert rv_b["session_id"] == "sid-fresh-b", f"02-b should be fresh, got {rv_b['session_id']!r}"
            assert rv_hol["session_id"] == "sid-fresh-hol", f"holistic should be fresh, got {rv_hol['session_id']!r}"

            print("PASS test8: skip-approved happy path — 01-a/03-c carryforward, 02-b/holistic fresh")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test8: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test8 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 9 — all batches approved + holistic re-runs
    # All three batches approved in r1 → stub fires exactly once (holistic).
    # reviews has 1 entry (holistic only, resume path, bug C fix #184).
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        batch_specs = [
            ("a", "01-a.md", ["src/a.py"], []),
            ("b", "02-b.md", ["src/b.py"], []),
            ("c", "03-c.md", ["src/c.py"], []),
        ]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(Path(tmpdir), batch_specs)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            reviews_dir = project_root / "reviews"
            reviews_dir.mkdir(parents=True, exist_ok=True)
            for stem in ("01-a", "02-b", "03-c"):
                (reviews_dir / f"20260429-000001-plan-review-{stem}-r1.md").write_text(
                    APPROVE_TEXT, encoding="utf-8"
                )

            # Only holistic fires
            stub.seed([(APPROVE_TEXT, "sid-hol")])
            r = plan_run(cfg, SLUG, mill_dir, wiki_root, project_root)

            prompts = stub.captured_prompts()
            assert len(prompts) == 1, (
                f"stub should fire exactly once (holistic), got {len(prompts)}"
            )
            assert len(r.reviews) == 1, f"expected 1 review (holistic only after bug C fix), got {len(r.reviews)}"
            fresh_entries = [rv for rv in r.reviews if rv["session_id"] is not None]
            assert len(fresh_entries) == 1, f"expected 1 fresh entry, got {len(fresh_entries)}"
            assert fresh_entries[0]["scope"] == "holistic"
            print("PASS test9: all approved — stub fires once (holistic only), holistic-only result (bug C fix #184)")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test9: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test9 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 10 — malformed prior review file
    # 01-a r1 file has unparseable content → treated as not-approved.
    # Stub fires for 01-a, 02-b, 03-c, and holistic (4 calls).
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        batch_specs = [
            ("a", "01-a.md", ["src/a.py"], []),
            ("b", "02-b.md", ["src/b.py"], []),
            ("c", "03-c.md", ["src/c.py"], []),
        ]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(Path(tmpdir), batch_specs)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            reviews_dir = project_root / "reviews"
            reviews_dir.mkdir(parents=True, exist_ok=True)
            # 01-a has malformed content — no yaml block
            (reviews_dir / "20260429-000001-plan-review-01-a-r1.md").write_text(
                "not a yaml block at all", encoding="utf-8"
            )
            # holistic-r1: marks round 1 as complete so detect_resume_round returns None
            (reviews_dir / "20260429-000002-plan-review-r1.md").write_text(
                APPROVE_TEXT, encoding="utf-8"
            )

            # All four scopes fire: 01-a, 02-b, 03-c, holistic
            _seed_approve(4)
            r = plan_run(cfg, SLUG, mill_dir, wiki_root, project_root)

            prompts = stub.captured_prompts()
            assert len(prompts) == 4, (
                f"malformed file should cause 01-a to re-review; expected 4 prompts, got {len(prompts)}"
            )
            assert r.verdict == "APPROVE"
            print("PASS test10: malformed prior review → 01-a treated as not-approved, all 4 scopes fire")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test10: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test10 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 11 — holistic_only=True: only holistic fires
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        batch_specs = [
            ("alpha", "01-alpha.md", ["src/a.py"], []),
            ("beta",  "02-beta.md",  ["src/b.py"], []),
        ]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(Path(tmpdir), batch_specs)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            stub.seed([(APPROVE_TEXT, "sid-hol-only")])
            r = plan_run(cfg, SLUG, mill_dir, wiki_root, project_root, holistic_only=True)
            prompts = stub.captured_prompts()
            assert len(prompts) == 1, (
                f"holistic_only: expected exactly 1 prompt (holistic), got {len(prompts)}"
            )
            assert len(r.reviews) == 1, f"expected 1 review entry, got {len(r.reviews)}"
            assert r.reviews[0]["scope"] == "holistic"
            print("PASS test11: holistic_only=True — stub fires once (holistic only)")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test11: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test11 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 12 — no_holistic=True: only per-batch fires
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        batch_specs = [
            ("alpha", "01-alpha.md", ["src/a.py"], []),
            ("beta",  "02-beta.md",  ["src/b.py"], []),
        ]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(Path(tmpdir), batch_specs)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            _seed_approve(2)
            r = plan_run(cfg, SLUG, mill_dir, wiki_root, project_root, no_holistic=True)
            prompts = stub.captured_prompts()
            assert len(prompts) == 2, (
                f"no_holistic: expected 2 prompts (per-batch only), got {len(prompts)}"
            )
            assert len(r.reviews) == 2, f"expected 2 review entries, got {len(r.reviews)}"
            scopes = {rv["scope"] for rv in r.reviews}
            assert "holistic" not in scopes, f"holistic should not appear in reviews: {scopes}"
            print("PASS test12: no_holistic=True — stub fires twice (per-batch only)")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test12: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test12 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 13 — mutual exclusion: holistic_only + no_holistic raises ReviewError
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        batch_specs = [("alpha", "01-alpha.md", ["src/a.py"], [])]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(Path(tmpdir), batch_specs)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            try:
                plan_run(cfg, SLUG, mill_dir, wiki_root, project_root,
                         holistic_only=True, no_holistic=True)
                errors += 1
                print("FAIL test13: expected ReviewError for mutually exclusive flags", file=sys.stderr)
            except Exception as exc:
                if "mutually exclusive" in str(exc):
                    print("PASS test13: holistic_only+no_holistic raises ReviewError (mutually exclusive)")
                else:
                    errors += 1
                    print(f"FAIL test13: unexpected exception: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test13 (unexpected outer {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 14 — aggregate blocking_count
    # batch a: 2 BLOCKINGs, batch b: 1 BLOCKING, holistic: 0 BLOCKINGs
    # aggregate = 3
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        batch_specs = [
            ("alpha", "01-alpha.md", ["src/a.py"], []),
            ("beta",  "02-beta.md",  ["src/b.py"], []),
        ]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(Path(tmpdir), batch_specs)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            two_blockings = (
                "# Review\n\n"
                "### [BLOCKING] issue one\n\n- b\n\n"
                "### [BLOCKING] issue two\n\n- b\n\n"
                "```yaml\nverdict: REQUEST_CHANGES\n```\n"
            )
            one_blocking = (
                "# Review\n\n"
                "### [BLOCKING] issue three\n\n- b\n\n"
                "```yaml\nverdict: REQUEST_CHANGES\n```\n"
            )
            stub.seed([
                (two_blockings, "sid-a"),
                (one_blocking,  "sid-b"),
                (APPROVE_TEXT,  "sid-hol"),
            ])
            r = plan_run(cfg, SLUG, mill_dir, wiki_root, project_root)
            assert r.blocking_count == 3, f"expected aggregate blocking_count=3, got {r.blocking_count}"
            print("PASS test14: aggregate blocking_count == 3 (2 + 1 + 0)")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test14: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test14 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 15 — max_rounds kwarg override for plan review
    # Pre-populate 3 per-batch review files and 3 holistic files.
    # Without kwarg (cfg max=3): raises ReviewError (round 4 would exceed max).
    # With max_rounds=5: holistic r4 succeeds (per-batch all approved → carryforward).
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        batch_specs = [("alpha", "01-alpha.md", ["src/a.py"], [])]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(Path(tmpdir), batch_specs)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            reviews_dir = project_root / "reviews"
            reviews_dir.mkdir(parents=True, exist_ok=True)

            # Pre-populate 3 holistic review files (rounds 1-3)
            for i in (1, 2, 3):
                (reviews_dir / f"2026042{i}-000001-plan-review-r{i}.md").write_text(
                    APPROVE_TEXT, encoding="utf-8"
                )
            # Pre-populate 3 alpha batch review files (rounds 1-3, all APPROVE)
            for i in (1, 2, 3):
                (reviews_dir / f"2026042{i}-000002-plan-review-01-alpha-r{i}.md").write_text(
                    APPROVE_TEXT, encoding="utf-8"
                )

            # Without kwarg: round 4 exceeds cfg max=3 → ReviewError
            try:
                stub.seed([(APPROVE_TEXT, "sid-x")])
                plan_run(cfg, SLUG, mill_dir, wiki_root, project_root)
                errors += 1
                print("FAIL test15a: expected ReviewError for round 4 with cfg max=3", file=sys.stderr)
            except Exception as exc:
                if "exceeds max" in str(exc):
                    print("PASS test15a: round 4 raises ReviewError without max_rounds kwarg")
                else:
                    errors += 1
                    print(f"FAIL test15a: unexpected exception: {exc}", file=sys.stderr)

            # With max_rounds=5: succeeds (alpha carryforward, holistic fresh r4)
            stub.seed([(APPROVE_TEXT, "sid-hol4")])
            r = plan_run(cfg, SLUG, mill_dir, wiki_root, project_root, max_rounds=5)
            rv_hol = next((rv for rv in r.reviews if rv["scope"] == "holistic"), None)
            assert rv_hol is not None, "holistic entry missing"
            fname = Path(rv_hol["file"]).name
            assert "plan-review-r4" in fname, f"expected holistic r4, got {fname}"
            print(f"PASS test15b: max_rounds=5 → holistic r4 succeeds → {fname}")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test15: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test15 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 16 — all-ERROR run returns ReviewResult, not ReviewError (#84)
    # Monkey-patch stub.run to raise LLMError for every call.
    # After Card 17, the total-fail check is removed, so plan_run falls
    # through to aggregate_verdict and returns REQUEST_CHANGES.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        batch_specs = [("alpha", "01-alpha.md", ["src/a.py"], [])]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(Path(tmpdir), batch_specs)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        original_run = stub.run

        def _raises_llmerror(*a, **kw):
            raise LLMError("seeded boom")

        stub.run = _raises_llmerror
        try:
            r = plan_run(cfg, SLUG, mill_dir, wiki_root, project_root)
            assert r.verdict == "REQUEST_CHANGES", (
                f"expected REQUEST_CHANGES for all-ERROR run, got {r.verdict}"
            )
            assert len(r.reviews) >= 1, "expected at least 1 review entry"
            for rv in r.reviews:
                assert rv["verdict"] == "ERROR", (
                    f"expected ERROR entry, got {rv['verdict']}"
                )
            print("PASS test16: all-ERROR run returns ReviewResult(REQUEST_CHANGES) rather than raising (#84)")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test16: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test16 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            stub.run = original_run
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 17 — mid-round resume: holistic missing, per-batch on disk (#87)
    # Pre-populate two per-batch r1 files (no holistic); stub fires once
    # (holistic only); reviews has 1 entry (holistic only, bug C fix #184).
    # ------------------------------------------------------------------
    REQUEST_CHANGES_TEXT2 = "# Review: test\n\n```yaml\nverdict: REQUEST_CHANGES\n```\n"
    with tempfile.TemporaryDirectory() as tmpdir:
        batch_specs = [
            ("alpha", "01-alpha.md", ["src/a.py"], []),
            ("beta",  "02-beta.md",  ["src/b.py"], []),
        ]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(Path(tmpdir), batch_specs)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            reviews_dir = project_root / "reviews"
            reviews_dir.mkdir(parents=True, exist_ok=True)
            (reviews_dir / "20260501-000001-plan-review-01-alpha-r1.md").write_text(
                APPROVE_TEXT, encoding="utf-8"
            )
            (reviews_dir / "20260501-000002-plan-review-02-beta-r1.md").write_text(
                REQUEST_CHANGES_TEXT2, encoding="utf-8"
            )

            stub.seed([(APPROVE_TEXT, "sid-hol-resume")])
            r = plan_run(cfg, SLUG, mill_dir, wiki_root, project_root)

            prompts = stub.captured_prompts()
            assert len(prompts) == 1, (
                f"mid-round resume: expected 1 prompt (holistic only), got {len(prompts)}"
            )
            assert len(r.reviews) == 1, (
                f"expected 1 review (holistic only after bug C fix), got {len(r.reviews)}"
            )
            rv_hol = next((rv for rv in r.reviews if rv["scope"] == "holistic"), None)
            assert rv_hol is not None, "holistic missing from resume reviews"
            assert rv_hol["session_id"] == "sid-hol-resume", (
                f"holistic should be fresh, got {rv_hol['session_id']!r}"
            )
            print("PASS test17: mid-round resume — stub fires once (holistic only), holistic-only result (bug C fix #184)")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test17: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test17 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 18 — deletes surface: batch declares Deletes token
    # The per-batch prompt must contain ## Intentionally deleted + the token.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        batch_specs = [("alpha", "01-alpha.md", ["src/a.py"], [])]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(Path(tmpdir), batch_specs)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            # Overwrite batch file to declare a delete
            plan_dir = project_root / "plan"
            (plan_dir / "01-alpha.md").write_text(
                _make_batch_file("alpha", ["src/a.py"], [], deletes=["old/file.py"]),
                encoding="utf-8",
            )

            _seed_approve(2)  # per-batch + holistic
            plan_run(cfg, SLUG, mill_dir, wiki_root, project_root)

            prompts = stub.captured_prompts()
            per_batch_prompt = prompts[0][0]
            assert "## Intentionally deleted" in per_batch_prompt, (
                "per-batch prompt missing '## Intentionally deleted' section"
            )
            assert "old/file.py" in per_batch_prompt, (
                "'old/file.py' not found in per-batch prompt"
            )
            print("PASS test18: deletes surface — '## Intentionally deleted' in per-batch prompt")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test18: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test18 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 19 — timeout plumbing: bulk_timeout → per-batch, holistic_timeout → holistic
    # Single-batch fixture so captured_prompts() ordering is deterministic.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        batch_specs = [("alpha", "01-alpha.md", ["src/a.py"], [])]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(Path(tmpdir), batch_specs)
        cfg["llm"]["bulk_timeout"] = 900
        cfg["llm"]["holistic_timeout"] = 1800
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            _seed_approve(2)  # per-batch + holistic
            plan_run(cfg, SLUG, mill_dir, wiki_root, project_root)

            prompts = stub.captured_prompts()
            assert len(prompts) == 2, f"expected 2 prompts, got {len(prompts)}"
            _, batch_kwargs = prompts[0]
            _, hol_kwargs   = prompts[1]
            assert batch_kwargs["timeout"] == 900, (
                f"per-batch timeout should be 900, got {batch_kwargs['timeout']!r}"
            )
            assert hol_kwargs["timeout"] == 1800, (
                f"holistic timeout should be 1800, got {hol_kwargs['timeout']!r}"
            )
            print("PASS test19: timeout plumbing — bulk_timeout=900 → per-batch, holistic_timeout=1800 → holistic")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test19: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test19 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 20 — holistic parse_verdict failure → ERROR entry (#185)
    # One-batch plan; holistic returns raw prose without yaml block →
    # parse_verdict raises ReviewError → ERROR entry, no raise.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        batch_specs = [("alpha", "01-alpha.md", ["src/a.py"], [])]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(Path(tmpdir), batch_specs)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            stub.seed([
                (APPROVE_TEXT, "sid-batch"),
                ("# Raw prose without any yaml block\n\nThe plan looks fine.", "sid-hol"),
            ])
            r = plan_run(cfg, SLUG, mill_dir, wiki_root, project_root)
            assert r.verdict == "REQUEST_CHANGES", (
                f"expected REQUEST_CHANGES (APPROVE + ERROR), got {r.verdict}"
            )
            assert len(r.reviews) == 2, f"expected 2 reviews, got {len(r.reviews)}"
            rv_hol = next((rv for rv in r.reviews if rv["scope"] == "holistic"), None)
            assert rv_hol is not None, "holistic entry missing"
            assert rv_hol["verdict"] == "ERROR", (
                f"holistic verdict should be ERROR, got {rv_hol['verdict']}"
            )
            assert rv_hol["file"] is not None, "holistic ERROR entry should have a file path"
            assert "parse_verdict failed" in rv_hol.get("error", ""), (
                f"error message missing 'parse_verdict failed': {rv_hol.get('error')}"
            )
            print("PASS test20: holistic parse_verdict failure → ERROR entry, no ReviewError raised (#185)")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test20: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test20 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 6a — batch=null: holistic fires, per-batch skipped
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        batch_specs = [("core", "01-core.md", ["src/a.py"], [])]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(Path(tmpdir), batch_specs)
        cfg["review"]["plan"]["batch"] = None  # keep holistic: "test_stub"
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            stub.seed([(APPROVE_TEXT, "sid-null-1")])
            r = plan_run(cfg, SLUG, mill_dir, wiki_root, project_root)
            assert r.verdict == "APPROVE", f"expected APPROVE, got {r.verdict}"
            assert len(r.reviews) == 1, f"expected 1 review, got {len(r.reviews)}"
            assert r.reviews[0]["scope"] == "holistic", (
                f"expected holistic scope, got {r.reviews[0]['scope']!r}"
            )
            fname = Path(r.reviews[0]["file"]).name
            assert "plan-review-r1" in fname, f"expected holistic filename pattern, got {fname}"
            print("PASS test6a: batch=null — holistic fires, per-batch skipped")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test6a: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test6a (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 6b — batch=null + holistic=null raises ReviewError
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        batch_specs = [("core", "01-core.md", ["src/a.py"], [])]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(Path(tmpdir), batch_specs)
        cfg["review"]["plan"]["batch"] = None
        cfg["review"]["plan"]["holistic"] = None
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            try:
                plan_run(cfg, SLUG, mill_dir, wiki_root, project_root)
                errors += 1
                print("FAIL test6b: expected ReviewError", file=sys.stderr)
            except ReviewError as exc:
                assert "at least one must be set" in str(exc), (
                    f"ReviewError message missing 'at least one must be set': {exc}"
                )
                print("PASS test6b: batch=null + holistic=null raises ReviewError")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test6b: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test6b (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All _review_plan flow tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
