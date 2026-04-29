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

import _active  # noqa: E402
import _reviewer_test_stub as stub  # noqa: E402
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


def _make_batch_file(name: str, reads: list[str], creates: list[str]) -> str:
    """Return batch file text (single-line Reads:/Creates: form)."""
    reads_part = ", ".join(f"`{r}`" for r in reads) if reads else "none"
    creates_part = ", ".join(f"`{c}`" for c in creates) if creates else "none"
    return (
        f"# Batch: {name}\n\n"
        "```yaml\n"
        f"task: test\nbatch: {name}\ncards: 1\nverify: null\ndepends-on: []\n"
        "```\n\n"
        "## Cards\n\n### Card 1\n\n"
        f"- **Reads:** {reads_part}\n"
        "- **Modifies:** none\n"
        f"- **Creates:** {creates_part}\n"
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
    mill_dir = worktree / ".millhouse"
    wiki_root = tmp_path / "wiki"
    project_root = worktree

    _active.write(
        mill_dir,
        slug=SLUG,
        task_title="Test Task",
        branch="test-branch",
        spawned_at="2026-01-01T00:00:00Z",
    )

    plan_dir = worktree / "active" / SLUG / "plan"
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
            "discussion_file": f"active/{SLUG}/discussion.md",
            "plan_dir":        f"active/{SLUG}/plan/",
            "reviews_dir":     f"active/{SLUG}/reviews/",
        },
        "review": {
            "plan": {"rounds": 3, "batch": "test_stub", "holistic": "test_stub"},
        },
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
            print("PASS test1a: first run — all scopes r1")

            # Second run — each scope advances to r2 independently
            _seed_approve(4)
            r2 = plan_run(cfg, SLUG, mill_dir, wiki_root, project_root)
            assert r2.verdict == "APPROVE"
            assert len(r2.reviews) == 4
            per_batch2 = [rv for rv in r2.reviews if rv["scope"] != "holistic"]
            holistic2 = next(rv for rv in r2.reviews if rv["scope"] == "holistic")
            for rv in per_batch2:
                fname = Path(rv["file"]).name
                assert f"plan-review-{rv['scope']}-r2" in fname, (
                    f"expected r2 in filename, got {fname}"
                )
            assert "plan-review-r2" in Path(holistic2["file"]).name, (
                f"unexpected holistic r2 filename: {Path(holistic2['file']).name}"
            )
            print("PASS test1b: second run — all scopes r2 (per-scope #21/#62/#63)")
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
    # alpha must be r2; beta/gamma/holistic must each be r1.
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
            # Pre-create an alpha-r1 review file inside the worktree
            reviews_dir = project_root / "active" / SLUG / "reviews"
            reviews_dir.mkdir(parents=True)
            (reviews_dir / "20260418-000000-plan-review-01-alpha-r1.md").write_text(
                "# stub r1 review", encoding="utf-8"
            )

            _seed_approve(4)
            r = plan_run(cfg, SLUG, mill_dir, wiki_root, project_root)
            assert r.verdict == "APPROVE"
            # alpha should be r2; others r1
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
            assert "plan-review-r1" in Path(rv_hol["file"]).name, (
                f"holistic should be r1, got {Path(rv_hol['file']).name}"
            )
            print("PASS test2: partial re-invocation — alpha r2, others r1 (independent per-scope)")
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
            assert retry_kwargs == {"session_id": "sid-1", "resume": True}, (
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
            assert retry_kwargs == {"session_id": "sid-2", "resume": True}, (
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

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All _review_plan flow tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
