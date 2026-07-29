"""Unit-test flow harness for _review_plan.run.

Uses _reviewer_test_stub as the reviewer backend. All tests run in-process
with no real LLM, no network calls. Covers:
  - Per-scope round counter (#21/#62/#63)
  - creates_union suppression in parallel per-batch section (#60)
  - Hard-fail surfaces as ERROR per-batch entry / ReviewError in holistic (#41)
  - NEED_CONTEXT resume fallback in per-batch and holistic (#5/#7)
"""
from __future__ import annotations

import json
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
from _llm_claude import LLMError  # noqa: E402
from _review_plan import run as plan_run  # noqa: E402
from _review_plan import prepare as plan_prepare  # noqa: E402
from _review_common import ReviewError  # noqa: E402
from _test_helpers import seed_wiki_config, write_local_overlay  # noqa: E402

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
    repo = _test_helpers.init_minimal_git_repo(worktree, branch="main")
    _test_helpers.checkout_new_branch(repo, f"hanf/{SLUG}")
    (worktree / ".gitignore").write_text("\n", encoding="utf-8")
    mill_dir = worktree / ".millhouse"
    mill_dir.mkdir(parents=True, exist_ok=True)
    wiki_root = tmp_path / "wiki"
    _test_helpers.init_wiki_repo(wiki_root)
    seed_wiki_config(wiki_root)
    (wiki_root / "Home.md").write_text(
        f"## Test Task\n[{SLUG}] [active]\n\n_body_\n", encoding="utf-8"
    )
    wiki.upsert_task(wiki_root, SLUG, title="Test Task", status="active")
    (mill_dir / "config.local.yaml").write_text(
        f"paths:\n  wiki: '{wiki_root.as_posix()}'\n"
        f"spawn:\n  branch_prefix: 'hanf/'\n", encoding="utf-8"
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

    _test_registry.write_to(wiki_root)

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
            "plan-review": {
                "batch":   {"rounds": 3, "reviewer": "test_stub"},
                "holistic": {"rounds": 3, "reviewer": "test_stub"},
            },
        },
        "llm": {"bulk_timeout": None, "holistic_timeout": None},
    }
    return mill_dir, wiki_root, project_root, cfg


def _seed_approve(n: int) -> None:
    """Seed n approve responses on the stub."""
    stub.seed([(APPROVE_TEXT, f"sid-{i + 1}") for i in range(n)])


def _make_nested_plan_fixture(
    tmp_path: Path,
    batch_specs: list[tuple[str, str, list[str], list[str]]],
) -> tuple[Path, Path, Path, Path]:
    """Build a nested-hub-layout plan-review fixture under tmp_path.

    Unlike _make_plan_fixture, the git root and the mill hub_root are
    different directories: hub_root lives one level under git_root
    (git_root/hub), mirroring a repo where .millhouse/ sits in a
    subdirectory of the git toplevel rather than at its root.

    batch_specs = [(name, file, reads, creates)]. The plan is written
    directly under hub_root/_mill/plan/ (the CLI's default plan_dir),
    so no --stage prepare copy step is needed.

    Returns (mill_dir, wiki_root, hub_root, git_root). Callers must
    os.chdir(hub_root) before invoking the CLI so _paths.resolve_hub_path()
    walks up from hub_root and finds .millhouse/config.local.yaml there,
    while _paths.resolve_git_root() still resolves to git_root.

    wiki_root deliberately uses the container-form sibling default
    (<container>/wiki, resolved via _sibling.resolve_path) rather than a
    paths.wiki override in hub_root's config.local.yaml: resolve_wiki_path
    is called both with hub_root (CLI's own lookup) and with git_root
    (inside _paths.resolve_active_worktree's marker check), and only
    git_root's own .millhouse/ (absent here) or the sibling default is
    consulted for the latter -- a hub_root-only override would make the
    two calls disagree on the wiki location.
    """
    git_root = tmp_path / "container" / "wts" / SLUG
    git_root.mkdir(parents=True)
    repo = _test_helpers.init_minimal_git_repo(git_root, branch="main")
    _test_helpers.checkout_new_branch(repo, f"hanf/{SLUG}")
    (git_root / ".gitignore").write_text("\n", encoding="utf-8")

    # hub_root nested one level under git_root -- the layout under test.
    hub_root = git_root / "hub"
    mill_dir = hub_root / ".millhouse"
    mill_dir.mkdir(parents=True, exist_ok=True)
    wiki_root = tmp_path / "container" / "wiki"
    _test_helpers.init_wiki_repo(wiki_root)
    seed_wiki_config(wiki_root)
    (wiki_root / "Home.md").write_text(
        f"## Test Task\n[{SLUG}] [active]\n\n_body_\n", encoding="utf-8"
    )
    wiki.upsert_task(wiki_root, SLUG, title="Test Task", status="active")
    (mill_dir / "config.local.yaml").write_text(
        # hub_relative_path declares hub_root's own offset from git_root --
        # the real mill-claim convention for M2+sub (nested-hub) layouts,
        # consumed by _paths.resolve_active_hub to rebase onto hub_root.
        "hub_relative_path: hub\n"
        "spawn:\n  branch_prefix: 'hanf/'\n", encoding="utf-8"
    )

    plan_dir = hub_root / "_mill" / "plan"
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
            p = hub_root / rf
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("# placeholder", encoding="utf-8")

    _test_registry.write_to(wiki_root)
    return mill_dir, wiki_root, hub_root, git_root


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
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch_specs = [
            ("alpha", "01-alpha.md", ["src/a.py"], []),
            ("beta",  "02-beta.md",  ["src/b.py"], []),
            ("gamma", "03-gamma.md", ["src/c.py"], []),
        ]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(tmpdir, batch_specs)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            # First run — each scope gets r1
            _seed_approve(4)
            r = plan_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root)
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

            # Second run — per-batch batches all APPROVE -> carryforward (r1 files);
            # only holistic fires fresh (r2). Skip-approved scan active.
            _seed_approve(1)  # only holistic needs a response
            r2 = plan_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root)
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
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch_specs = [
            ("alpha", "01-alpha.md", ["src/a.py"], []),
            ("beta",  "02-beta.md",  ["src/b.py"], []),
            ("gamma", "03-gamma.md", ["src/c.py"], []),
        ]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(tmpdir, batch_specs)
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
            r = plan_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root)
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
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch_specs = [
            ("alpha", "01-alpha.md", ["src/a.py"], ["generated/by_alpha.py"]),
            ("beta",  "02-beta.md",  ["generated/by_alpha.py"], []),
            ("gamma", "03-gamma.md", ["src/c.py"], []),
        ]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(
            tmpdir, batch_specs, skip_create={"generated/by_alpha.py"}
        )
        orig_dir = os.getcwd()
        os.chdir(project_root)
        _seed_approve(4)
        try:
            r = plan_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root)
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
    # alpha (clean) succeeds; beta (bad ref) -> ERROR entry; holistic disabled.
    # Aggregate must be REQUEST_CHANGES (not ReviewError), since not all ERROR.
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch_specs = [
            ("alpha", "01-alpha.md", ["src/a.py"], []),
            ("beta",  "02-beta.md",  ["nonexistent/path.py"], []),
        ]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(
            tmpdir, batch_specs, skip_create={"nonexistent/path.py"}
        )
        cfg4 = dict(cfg)
        cfg4["roles"] = dict(cfg["roles"])
        cfg4["roles"]["plan-review"] = dict(cfg["roles"]["plan-review"])
        cfg4["roles"]["plan-review"]["holistic"] = dict(cfg["roles"]["plan-review"]["holistic"])
        cfg4["roles"]["plan-review"]["holistic"]["reviewer"] = None  # disable holistic for isolation

        orig_dir = os.getcwd()
        os.chdir(project_root)
        # 1 approve for alpha; beta fails before calling reviewer
        _seed_approve(1)
        try:
            r = plan_run(cfg4, SLUG, mill_dir, wiki_root, project_root, git_root=project_root)
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
            print("PASS test4: per-batch ReviewError -> ERROR entry, aggregate REQUEST_CHANGES (#41)")
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
    # alpha + gamma succeed; beta has bad ref -> ERROR entry (no reviewer call).
    # Holistic resolver encounters beta's bad ref -> ReviewError propagates.
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch_specs = [
            ("alpha", "01-alpha.md", ["src/a.py"], []),
            ("beta",  "02-beta.md",  ["nonexistent/path.py"], []),
            ("gamma", "03-gamma.md", ["src/c.py"], []),
        ]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(
            tmpdir, batch_specs, skip_create={"nonexistent/path.py"}
        )
        orig_dir = os.getcwd()
        os.chdir(project_root)
        # alpha + gamma consume one each; holistic resolver fails before reviewer runs.
        # The third seeded response is never consumed.
        _seed_approve(3)
        try:
            plan_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root)
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
    # Single batch (alpha) + holistic. Alpha retries once -> APPROVE.
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch_specs = [("alpha", "01-alpha.md", ["src/a.py"], [])]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(
            tmpdir, batch_specs
        )
        orig_dir = os.getcwd()
        os.chdir(project_root)
        # alpha: NEED_CONTEXT -> retry APPROVE; holistic: APPROVE
        stub.seed([
            (NEED_CONTEXT_TEXT, "sid-1"),  # alpha first call
            (APPROVE_TEXT,      "sid-2"),  # alpha retry
            (APPROVE_TEXT,      "sid-3"),  # holistic
        ])
        try:
            r = plan_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root)
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
            print("PASS test6: per-batch NEED_CONTEXT retry -> APPROVE, holistic unaffected")
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
    # Single batch (alpha) succeeds; holistic NEED_CONTEXT -> retry APPROVE.
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch_specs = [("alpha", "01-alpha.md", ["src/a.py"], [])]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(
            tmpdir, batch_specs
        )
        orig_dir = os.getcwd()
        os.chdir(project_root)
        # alpha: APPROVE; holistic: NEED_CONTEXT -> retry APPROVE-with-a-real-[NIT]
        RETRY_APPROVE_WITH_NIT_TEXT = (
            "# Review: test\n\n### [NIT] cleanup note\n\n- b\n\n"
            "```yaml\nverdict: APPROVE\n```\n"
        )
        stub.seed([
            (APPROVE_TEXT,      "sid-1"),  # alpha
            (NEED_CONTEXT_TEXT, "sid-2"),  # holistic first call
            (RETRY_APPROVE_WITH_NIT_TEXT, "sid-3"),  # holistic retry
        ])
        try:
            r = plan_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root)
            assert r.verdict == "APPROVE", f"expected APPROVE, got {r.verdict}"
            rv_hol = next(rv for rv in r.reviews if rv["scope"] == "holistic")
            assert rv_hol["verdict"] == "APPROVE", (
                f"holistic verdict should be APPROVE after retry, got {rv_hol['verdict']}"
            )
            assert rv_hol["blocking_count"] == 0, (
                f"expected holistic blocking_count=0, got {rv_hol['blocking_count']}"
            )
            assert rv_hol["nit_count"] == 1, (
                f"expected holistic nit_count=1, got {rv_hol['nit_count']}"
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
            print("PASS test7: holistic NEED_CONTEXT retry -> APPROVE")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test7: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test7 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 7b — holistic NEED_CONTEXT no-resolve branch
    # Sibling to Test 7 (this file's tests are not renumbered when a new one
    # is inserted between existing numbers -- see Test 9's own "bug C fix
    # #184" comment for precedent). Single batch (alpha) succeeds; holistic
    # returns NEED_CONTEXT referencing a path that resolve_existing_paths
    # cannot resolve on disk, so the no-retry / no-resolve branch fires and
    # the holistic entry is finalized directly from the first response.
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch_specs = [("alpha", "01-alpha.md", ["src/a.py"], [])]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(
            tmpdir, batch_specs
        )
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            # `nonexistent/missing.py` is never created on disk and is not a
            # Creates:/Deletes: token in any batch file, so
            # resolve_existing_paths returns an empty list and no retry fires.
            NEED_CONTEXT_UNRESOLVABLE_WITH_NIT_TEXT = (
                "# Review: test\n\n### [NIT] pending cleanup\n\n- b\n\n"
                "```yaml\nverdict: NEED_CONTEXT\n```\n\n"
                "## Missing context\n\n"
                "- `nonexistent/missing.py` — need this file\n"
            )
            stub.seed([
                (APPROVE_TEXT, "sid-1"),  # alpha
                (NEED_CONTEXT_UNRESOLVABLE_WITH_NIT_TEXT, "sid-2"),  # holistic first call, unresolvable
            ])
            r = plan_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root)
            prompts = stub.captured_prompts()
            assert len(prompts) == 2, (
                f"expected 2 prompts (alpha + holistic first call, no retry), got {len(prompts)}"
            )
            rv_hol = next(rv for rv in r.reviews if rv["scope"] == "holistic")
            assert rv_hol["verdict"] == "NEED_CONTEXT", (
                f"expected holistic verdict NEED_CONTEXT, got {rv_hol['verdict']}"
            )
            assert rv_hol["blocking_count"] == 0, (
                f"expected holistic blocking_count=0, got {rv_hol['blocking_count']}"
            )
            assert rv_hol["nit_count"] == 1, (
                f"expected holistic nit_count=1, got {rv_hol['nit_count']}"
            )
            print("PASS test7b: holistic NEED_CONTEXT no-resolve branch — no retry, counters finalized from first response")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test7b: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test7b (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    REQUEST_CHANGES_TEXT = "# Review: test\n\n```yaml\nverdict: REQUEST_CHANGES\n```\n"

    # ------------------------------------------------------------------
    # Test 8 — skip-approved happy path
    # Three batches; 01-a and 03-c are approved in r1; 02-b is not.
    # Stub should fire exactly twice: once for 02-b, once for holistic.
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch_specs = [
            ("a", "01-a.md", ["src/a.py"], []),
            ("b", "02-b.md", ["src/b.py"], []),
            ("c", "03-c.md", ["src/c.py"], []),
        ]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(tmpdir, batch_specs)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            reviews_dir = project_root / "reviews"
            reviews_dir.mkdir(parents=True, exist_ok=True)
            # 01-a approved in r1, with a real [NIT] finding to prove the
            # carryforward path computes a genuine nit_count, not just 0.
            APPROVE_WITH_NIT_TEXT = (
                "# Review: test\n\n### [NIT] cosmetic\n\n- b\n\n"
                "```yaml\nverdict: APPROVE\n```\n"
            )
            (reviews_dir / "20260429-000001-plan-review-01-a-r1.md").write_text(
                APPROVE_WITH_NIT_TEXT, encoding="utf-8"
            )
            # 02-b NOT approved (REQUEST_CHANGES)
            (reviews_dir / "20260429-000002-plan-review-02-b-r1.md").write_text(
                REQUEST_CHANGES_TEXT, encoding="utf-8"
            )
            # 03-c approved in r1, with an off-vocabulary [MAJOR] heading
            # alongside verdict: APPROVE -- _scan_approved_batches carries this
            # forward because parse_verdict still reads APPROVE, exercising
            # the round-3 finding that verdict is never cross-validated
            # against the review's actual finding counts.
            APPROVE_WITH_UNRECOGNIZED_SEVERITY_TEXT = (
                "# Review: test\n\n### [MAJOR] mislabeled issue\n\n- b\n\n"
                "```yaml\nverdict: APPROVE\n```\n"
            )
            (reviews_dir / "20260429-000003-plan-review-03-c-r1.md").write_text(
                APPROVE_WITH_UNRECOGNIZED_SEVERITY_TEXT, encoding="utf-8"
            )
            # holistic-r1: marks round 1 as complete so detect_resume_round returns None
            (reviews_dir / "20260429-000004-plan-review-r1.md").write_text(
                APPROVE_TEXT, encoding="utf-8"
            )

            # Stub: 1 for 02-b + 1 for holistic = 2 responses
            stub.seed([(APPROVE_TEXT, "sid-fresh-b"), (APPROVE_TEXT, "sid-fresh-hol")])
            r = plan_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root)

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

            # Carryforward counts: 01-a's real [NIT] heading and 03-c's
            # off-vocabulary [MAJOR] heading (folds into blocking_count).
            assert rv_a["blocking_count"] == 0, f"expected 01-a blocking_count=0, got {rv_a['blocking_count']}"
            assert rv_a["nit_count"] == 1, f"expected 01-a nit_count=1, got {rv_a['nit_count']}"
            assert rv_c["blocking_count"] == 1, f"expected 03-c blocking_count=1, got {rv_c['blocking_count']}"
            assert rv_c["nit_count"] == 0, f"expected 03-c nit_count=0, got {rv_c['nit_count']}"

            # Aggregate: the fresh 02-b/holistic dispatches return zero-finding
            # APPROVE_TEXT/REQUEST_CHANGES_TEXT, so only the two carryforward
            # entries above contribute to the run-level aggregate.
            assert r.blocking_count == 1, f"expected aggregate blocking_count=1, got {r.blocking_count}"
            assert r.nit_count == 1, f"expected aggregate nit_count=1, got {r.nit_count}"

            print("PASS test8: skip-approved happy path — 01-a/03-c carryforward, 02-b/holistic fresh, blocking/nit counts correct")
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
    # All three batches approved in r1 -> stub fires exactly once (holistic).
    # reviews has 1 entry (holistic only, resume path, bug C fix #184).
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch_specs = [
            ("a", "01-a.md", ["src/a.py"], []),
            ("b", "02-b.md", ["src/b.py"], []),
            ("c", "03-c.md", ["src/c.py"], []),
        ]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(tmpdir, batch_specs)
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
            r = plan_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root)

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
    # 01-a r1 file has unparseable content -> treated as not-approved.
    # Stub fires for 01-a, 02-b, 03-c, and holistic (4 calls).
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch_specs = [
            ("a", "01-a.md", ["src/a.py"], []),
            ("b", "02-b.md", ["src/b.py"], []),
            ("c", "03-c.md", ["src/c.py"], []),
        ]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(tmpdir, batch_specs)
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
            r = plan_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root)

            prompts = stub.captured_prompts()
            assert len(prompts) == 4, (
                f"malformed file should cause 01-a to re-review; expected 4 prompts, got {len(prompts)}"
            )
            assert r.verdict == "APPROVE"
            print("PASS test10: malformed prior review -> 01-a treated as not-approved, all 4 scopes fire")
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
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch_specs = [
            ("alpha", "01-alpha.md", ["src/a.py"], []),
            ("beta",  "02-beta.md",  ["src/b.py"], []),
        ]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(tmpdir, batch_specs)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            stub.seed([(APPROVE_TEXT, "sid-hol-only")])
            r = plan_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, holistic_only=True)
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
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch_specs = [
            ("alpha", "01-alpha.md", ["src/a.py"], []),
            ("beta",  "02-beta.md",  ["src/b.py"], []),
        ]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(tmpdir, batch_specs)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            _seed_approve(2)
            r = plan_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, no_holistic=True)
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
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch_specs = [("alpha", "01-alpha.md", ["src/a.py"], [])]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(tmpdir, batch_specs)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            try:
                plan_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root,
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
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch_specs = [
            ("alpha", "01-alpha.md", ["src/a.py"], []),
            ("beta",  "02-beta.md",  ["src/b.py"], []),
        ]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(tmpdir, batch_specs)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            two_blockings = (
                "# Review\n\n"
                "### [BLOCKING] issue one\n\n- b\n\n"
                "### [BLOCKING] issue two\n\n- b\n\n"
                "### [NIT] issue four\n\n- b\n\n"
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
            r = plan_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root)
            assert r.blocking_count == 3, f"expected aggregate blocking_count=3, got {r.blocking_count}"
            assert r.nit_count == 1, f"expected aggregate nit_count=1, got {r.nit_count}"
            print("PASS test14: aggregate blocking_count == 3 (2 + 1 + 0), nit_count == 1")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test14: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test14 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 14b — holistic-normal site's own blocking_count/nit_count
    # Sibling to Test 14 (inserted without renumbering later tests, same
    # precedent as Test 7b). Test 14's holistic leg stays APPROVE_TEXT, so
    # this is the only test that exercises the "holistic normal" finalize_scope
    # call site's own counts directly rather than only the run-level aggregate.
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch_specs = [("alpha", "01-alpha.md", ["src/a.py"], [])]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(tmpdir, batch_specs)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            holistic_blocking_and_nit = (
                "# Review\n\n"
                "### [BLOCKING] missing edge case\n\n- b\n\n"
                "### [NIT] naming nit\n\n- b\n\n"
                "```yaml\nverdict: REQUEST_CHANGES\n```\n"
            )
            stub.seed([(APPROVE_TEXT, "sid-a"), (holistic_blocking_and_nit, "sid-hol")])
            r = plan_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root)
            rv_hol = next(rv for rv in r.reviews if rv["scope"] == "holistic")
            assert rv_hol["blocking_count"] == 1, (
                f"expected holistic blocking_count=1, got {rv_hol['blocking_count']}"
            )
            assert rv_hol["nit_count"] == 1, (
                f"expected holistic nit_count=1, got {rv_hol['nit_count']}"
            )
            print("PASS test14b: holistic-normal site's own blocking_count/nit_count == 1/1")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test14b: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test14b (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 15 — max_rounds kwarg override for plan review
    # Pre-populate 3 per-batch review files and 3 holistic files.
    # Without kwarg (cfg max=3): raises ReviewError (round 4 would exceed max).
    # With max_rounds=5: holistic r4 succeeds (per-batch all approved -> carryforward).
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch_specs = [("alpha", "01-alpha.md", ["src/a.py"], [])]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(tmpdir, batch_specs)
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

            # Without kwarg: round 4 exceeds cfg max=3 -> ReviewError
            try:
                stub.seed([(APPROVE_TEXT, "sid-x")])
                plan_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root)
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
            r = plan_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, max_rounds=5)
            rv_hol = next((rv for rv in r.reviews if rv["scope"] == "holistic"), None)
            assert rv_hol is not None, "holistic entry missing"
            fname = Path(rv_hol["file"]).name
            assert "plan-review-r4" in fname, f"expected holistic r4, got {fname}"
            print(f"PASS test15b: max_rounds=5 -> holistic r4 succeeds -> {fname}")
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
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch_specs = [("alpha", "01-alpha.md", ["src/a.py"], [])]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(tmpdir, batch_specs)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        original_run = stub.run

        def _raises_llmerror(*a, **kw):
            raise LLMError("seeded boom")

        stub.run = _raises_llmerror
        try:
            r = plan_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root)
            assert r.verdict == "ERROR", (
                f"expected ERROR for all-ERROR run, got {r.verdict}"
            )
            assert len(r.reviews) >= 1, "expected at least 1 review entry"
            for rv in r.reviews:
                assert rv["verdict"] == "ERROR", (
                    f"expected ERROR entry, got {rv['verdict']}"
                )
            assert all(rv["verdict"] == "ERROR" for rv in r.reviews), f"expected all sub-reviews ERROR, got {[rv['verdict'] for rv in r.reviews]}"
            print("PASS test16: all-ERROR run returns ReviewResult(ERROR) rather than raising (#84, #228)")
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
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch_specs = [
            ("alpha", "01-alpha.md", ["src/a.py"], []),
            ("beta",  "02-beta.md",  ["src/b.py"], []),
        ]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(tmpdir, batch_specs)
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
            r = plan_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root)

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
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch_specs = [("alpha", "01-alpha.md", ["src/a.py"], [])]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(tmpdir, batch_specs)
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
            plan_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root)

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
    # Test 19 — timeout plumbing: bulk_timeout -> per-batch, holistic_timeout -> holistic
    # Single-batch fixture so captured_prompts() ordering is deterministic.
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch_specs = [("alpha", "01-alpha.md", ["src/a.py"], [])]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(tmpdir, batch_specs)
        cfg["llm"]["bulk_timeout"] = 900
        cfg["llm"]["holistic_timeout"] = 1800
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            _seed_approve(2)  # per-batch + holistic
            plan_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root)

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
            print("PASS test19: timeout plumbing — bulk_timeout=900 -> per-batch, holistic_timeout=1800 -> holistic")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test19: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test19 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 20 — holistic parse_verdict failure -> ERROR entry (#185)
    # One-batch plan; holistic returns raw prose without yaml block ->
    # parse_verdict raises ReviewError -> ERROR entry, no raise.
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch_specs = [("alpha", "01-alpha.md", ["src/a.py"], [])]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(tmpdir, batch_specs)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            stub.seed([
                (APPROVE_TEXT, "sid-batch"),
                ("# Raw prose without any yaml block\n\nThe plan looks fine.", "sid-hol"),
            ])
            r = plan_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root)
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
            print("PASS test20: holistic parse_verdict failure -> ERROR entry, no ReviewError raised (#185)")
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
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch_specs = [("core", "01-core.md", ["src/a.py"], [])]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(tmpdir, batch_specs)
        cfg["roles"]["plan-review"]["batch"]["reviewer"] = None  # keep holistic: "test_stub"
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            stub.seed([(APPROVE_TEXT, "sid-null-1")])
            r = plan_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root)
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
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch_specs = [("core", "01-core.md", ["src/a.py"], [])]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(tmpdir, batch_specs)
        cfg["roles"]["plan-review"]["batch"]["reviewer"] = None
        cfg["roles"]["plan-review"]["holistic"]["reviewer"] = None
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            try:
                plan_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root)
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

    # ------------------------------------------------------------------
    # Test 21 — holistic parse_verdict failure (holistic-only) returns ERROR envelope (#315)
    # No per-batch reviews; holistic-only mode. Unparseable output -> ERROR entry
    # with file path. Aggregate verdict is ERROR (all reviews are ERROR).
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch_specs = [("alpha", "01-alpha.md", ["src/a.py"], [])]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(tmpdir, batch_specs)
        cfg["roles"]["plan-review"]["batch"]["reviewer"] = None  # holistic only
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            stub.seed([
                ("# Raw prose without yaml block\n\nPlan looks good.", "sid-hol"),
            ])
            r = plan_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root)
            assert r.verdict == "ERROR", (
                f"expected ERROR for all-ERROR run, got {r.verdict}"
            )
            assert len(r.reviews) >= 1, f"expected at least 1 review, got {len(r.reviews)}"
            assert r.reviews[0]["verdict"] == "ERROR", (
                f"expected first review ERROR, got {r.reviews[0]['verdict']}"
            )
            assert "parse_verdict failed" in r.reviews[0].get("error", ""), (
                f"error message missing 'parse_verdict failed': {r.reviews[0].get('error')}"
            )
            assert r.reviews[0]["file"] is not None, "ERROR entry should have a file path"
            file_path = Path(r.reviews[0]["file"])
            assert file_path.exists(), f"review file should exist on disk: {file_path}"
            print("PASS test21: holistic parse_verdict failure emits ERROR envelope (#315)")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test21: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test21 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 22 — rounds=0 holistic via kwarg, batch reviewer null -> both
    # scopes are now correctly disabled, so ReviewError fires (post-Card-4:
    # the disablement gate reads holistic_max_rounds, so a max_rounds=0
    # override makes holistic_spec None the same as an explicit
    # reviewer=None would -- it no longer coincidentally slips through
    # the round-cap stub-return at holistic dispatch time, so with the
    # batch reviewer also null there is genuinely nothing to review)
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch_specs = [("core", "01-core.md", ["src/a.py"], [])]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(tmpdir, batch_specs)
        cfg["roles"]["plan-review"]["holistic"]["reviewer"] = "test_stub"
        cfg["roles"]["plan-review"]["holistic"]["rounds"] = 3
        cfg["roles"]["plan-review"]["batch"]["reviewer"] = None
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            try:
                plan_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, max_rounds=0)
                errors += 1
                print("FAIL test22: expected ReviewError", file=sys.stderr)
            except ReviewError as exc:
                assert "at least one must be set" in str(exc), (
                    f"ReviewError message missing 'at least one must be set': {exc}"
                )
                print("PASS test22: max_rounds=0 kwarg disables holistic + batch=null -> ReviewError")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test22: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test22 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 23 — large_prompt.timeout override wires to holistic run call
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch_specs = [("core", "01-core.md", ["src/a.py"], [])]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(tmpdir, batch_specs)
        cfg["roles"]["plan-review"]["holistic"]["reviewer"] = "test_stub"
        cfg["roles"]["plan-review"]["holistic"]["rounds"] = 1
        cfg["roles"]["plan-review"]["batch"]["reviewer"] = None
        cfg["llm"]["holistic_timeout"] = 1800  # default
        # Add large_prompt timeout override
        cfg["roles"]["plan-review"]["holistic"]["large_prompt"] = {
            "threshold_ktok": 1,  # low threshold to trigger override with normal prompt
            "timeout": 7200,
        }
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            from unittest.mock import patch, MagicMock
            # Capture the timeout kwarg passed to _reviewer_single.run
            captured_timeout = None
            def mock_run(spec, prompt_text, timeout=None, session_id=None, resume=False):
                nonlocal captured_timeout
                captured_timeout = timeout
                # Return APPROVE_TEXT and a session_id like the test stub does
                return (APPROVE_TEXT, "test-session-id")

            _seed_approve(1)  # seed the test_stub just in case
            with patch("_review_plan._reviewer_single.run", side_effect=mock_run):
                r = plan_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root)

            # The captured_timeout should be the override (7200) because the prompt is over threshold
            assert captured_timeout == 7200, (
                f"Expected resolved timeout=7200 (override), got {captured_timeout}"
            )
            print("PASS test23: large_prompt.timeout override wires to holistic run call")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test23: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test23 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 24 — prepare-stage validator gate with errors (non-existent-path ref)
    # Error plan has a Context: ref to nonexistent file; validator should reject
    # it with exit 1, JSON errors envelope, and no brief file written.
    # Tests the CLI entry point main(["--stage", "prepare", "--holistic-only"]),
    # NOT the validator function directly (see test-plan-validate.py for
    # negative case: omitting git_root from validator).
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch_specs = [
            ("alpha", "01-alpha.md", ["nonexistent/path.py"], []),
        ]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(
            tmpdir, batch_specs, skip_create={"nonexistent/path.py"}
        )
        # The CLI expects the plan in _mill/plan/ (default config has plan_dir: _mill/plan/)
        # Copy from plan/ to _mill/plan/
        mill_plan_dir = project_root / "_mill" / "plan"
        mill_plan_dir.mkdir(parents=True, exist_ok=True)
        for f in (project_root / "plan").glob("*.md"):
            (mill_plan_dir / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")

        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            # Invoke the CLI entry point via subprocess through uv
            result = subprocess.run(
                [
                    "uv", "run",
                    "--project", str(HUB / "plugins" / "mill"),
                    "python", str(HUB / "plugins" / "mill" / "scripts" / "millpy-review-plan.py"),
                    "--stage", "prepare",
                    "--holistic-only",
                ],
                capture_output=True,
                text=True,
                cwd=str(project_root),
            )

            # Should exit with code 1 (validator found errors)
            assert result.returncode == 1, (
                f"expected exit code 1 for validator errors, got {result.returncode}; "
                f"stdout={result.stdout!r}, stderr={result.stderr!r}"
            )

            # Check that stdout contains JSON with errors and summary keys
            json_output = json.loads(result.stdout)
            assert "errors" in json_output, f"expected 'errors' key in JSON output: {json_output}"
            assert "summary" in json_output, f"expected 'summary' key in JSON output: {json_output}"
            validate_errors = json_output["errors"]
            assert len(validate_errors) > 0, f"expected non-empty errors list, got {validate_errors}"
            assert any(e["check"] == "non-existent-path" for e in validate_errors), (
                f"expected non-existent-path check error, got checks: {[e['check'] for e in validate_errors]}"
            )

            # Brief file should NOT exist (validator rejected the plan)
            briefs_dir = project_root / "_mill" / "briefs"
            brief_files = list(briefs_dir.glob("*.md")) if briefs_dir.exists() else []
            assert len(brief_files) == 0, (
                f"expected no brief files written on validator errors, got {len(brief_files)}: {brief_files}"
            )

            print("PASS test24: prepare CLI entry point rejects plan with validator errors, no brief written")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test24: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test24 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 25 — prepare-stage validator gate with clean plan
    # Clean plan should pass validation, write brief file, and return
    # prepare envelope with stage: "prepare" and brief_path.
    # Tests the CLI entry point main(["--stage", "prepare", "--holistic-only"]).
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch_specs = [
            ("alpha", "01-alpha.md", ["src/a.py"], []),
        ]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(tmpdir, batch_specs)
        # The CLI expects the plan in _mill/plan/ (default config has plan_dir: _mill/plan/)
        # Copy from plan/ to _mill/plan/
        mill_plan_dir = project_root / "_mill" / "plan"
        mill_plan_dir.mkdir(parents=True, exist_ok=True)
        for f in (project_root / "plan").glob("*.md"):
            (mill_plan_dir / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")

        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            # Create briefs directory so write_brief doesn't fail
            briefs_dir = project_root / "_mill" / "briefs"
            briefs_dir.mkdir(parents=True, exist_ok=True)

            # Invoke the CLI entry point via subprocess through uv
            result = subprocess.run(
                [
                    "uv", "run",
                    "--project", str(HUB / "plugins" / "mill"),
                    "python", str(HUB / "plugins" / "mill" / "scripts" / "millpy-review-plan.py"),
                    "--stage", "prepare",
                    "--holistic-only",
                ],
                capture_output=True,
                text=True,
                cwd=str(project_root),
            )

            # Should exit with code 0 (clean plan, validator passed)
            assert result.returncode == 0, (
                f"expected exit code 0 for clean plan, got {result.returncode}; "
                f"stdout={result.stdout!r}, stderr={result.stderr!r}"
            )

            # Check that stdout contains JSON with prepare stage envelope
            json_output = json.loads(result.stdout)
            assert json_output.get("stage") == "prepare", (
                f"expected stage='prepare' in JSON output, got {json_output}"
            )
            assert "brief_path" in json_output, (
                f"expected 'brief_path' key in JSON output, got {json_output}"
            )
            assert "errors" not in json_output, (
                f"expected no 'errors' key in successful prepare envelope, got {json_output}"
            )

            # Brief file should exist
            brief_path = Path(json_output["brief_path"])
            assert brief_path.exists(), (
                f"expected brief file to exist at {brief_path}, but it does not"
            )

            print("PASS test25: prepare CLI entry point accepts clean plan, writes brief file")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test25: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test25 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 26 — Move sources included in plan review bulk (Card 18)
    # A batch declares a Moves: entry; the source file exists on disk.
    # Both the per-batch prompt and the holistic prompt must contain the
    # source file's path/content so the reviewer can inspect the relocation.
    # ------------------------------------------------------------------
    def _make_batch_file_with_moves(
        name: str,
        reads: list[str],
        creates: list[str],
        *,
        moves: list[tuple[str, str]],
        deletes: list[str] | None = None,
    ) -> str:
        """Return batch file text including a multi-line Moves: field."""
        reads_part = ", ".join(f"`{r}`" for r in reads) if reads else "none"
        creates_part = ", ".join(f"`{c}`" for c in creates) if creates else "none"
        deletes_part = ", ".join(f"`{d}`" for d in deletes) if deletes else "none"
        if moves:
            moves_lines = "\n".join(f"  - `{s}` -> `{d}`" for s, d in moves)
            moves_part = f"\n{moves_lines}"
        else:
            moves_part = " none"
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
            f"- **Moves:**{moves_part}\n"
        )

    with _test_helpers.safe_temp_dir() as tmpdir:
        batch_specs = [
            ("alpha", "01-alpha.md", ["src/a.py"], []),
        ]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(tmpdir, batch_specs)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            plan_dir = project_root / "plan"
            # Overwrite batch file to declare a move: old/module.py -> new/module.py
            (plan_dir / "01-alpha.md").write_text(
                _make_batch_file_with_moves(
                    "alpha",
                    ["src/a.py"],
                    [],
                    moves=[("old/module.py", "new/module.py")],
                ),
                encoding="utf-8",
            )
            # Create the move source on disk (it exists pre-implementation)
            (project_root / "old").mkdir(parents=True)
            (project_root / "old" / "module.py").write_text(
                "# original module content\n", encoding="utf-8"
            )

            # per-batch + holistic = 2 responses
            _seed_approve(2)
            plan_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root)

            prompts = stub.captured_prompts()
            assert len(prompts) == 2, f"expected 2 prompts, got {len(prompts)}"

            # Per-batch prompt (index 0) must reference the move source
            per_batch_prompt = prompts[0][0]
            assert "old/module.py" in per_batch_prompt, (
                "move source 'old/module.py' not found in per-batch plan-review prompt"
            )

            # Holistic prompt (index 1) must also reference the move source
            holistic_prompt = prompts[1][0]
            assert "old/module.py" in holistic_prompt, (
                "move source 'old/module.py' not found in holistic plan-review prompt"
            )

            print("PASS test26: Moves: source appears in both per-batch and holistic plan-review prompts")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test26: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test26 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 27 — Move targets suppressed in plan-review path checks (Card 18 /
    # move-endpoint-accounting Shared Decision).
    # alpha declares Moves: old/module.py -> new/module.py; beta's Context
    # references the move target new/module.py, which does NOT exist on disk
    # at plan-review time (it is created as part of the rename). Without
    # move-target suppression, resolve_ref_paths raises ReviewError -> beta
    # ERROR entry in the per-batch section and ReviewError in the holistic
    # resolver, so the run aggregates away from APPROVE. The fix merges move
    # targets into the creates suppression set, so plan review must APPROVE
    # both scopes. Mirrors test3 (creates_union) for the move-endpoint case.
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch_specs = [
            ("alpha", "01-alpha.md", ["src/a.py"], []),
            ("beta",  "02-beta.md",  ["new/module.py"], []),
        ]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(
            tmpdir, batch_specs, skip_create={"new/module.py"}
        )
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            plan_dir = project_root / "plan"
            # alpha declares the rename old/module.py -> new/module.py.
            (plan_dir / "01-alpha.md").write_text(
                _make_batch_file_with_moves(
                    "alpha",
                    ["src/a.py"],
                    [],
                    moves=[("old/module.py", "new/module.py")],
                ),
                encoding="utf-8",
            )
            # Move source exists pre-implementation; move target does not.
            (project_root / "old").mkdir(parents=True)
            (project_root / "old" / "module.py").write_text(
                "# original module content\n", encoding="utf-8"
            )

            # per-batch (alpha + beta) + holistic = 3 responses
            _seed_approve(3)
            r = plan_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root)
            assert r.verdict == "APPROVE", f"expected APPROVE, got {r.verdict}"
            for rv in r.reviews:
                assert rv["verdict"] == "APPROVE", (
                    f"scope {rv['scope']} verdict {rv['verdict']} != APPROVE "
                    f"(move target not suppressed: {rv.get('error')})"
                )
            print("PASS test27: move targets suppressed in per-batch and holistic plan-review path checks")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test27: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test27 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 28 — nested-hub-layout: prepare-stage brief_path resolves under
    # the nested hub_root's _mill/briefs/, not under git_root's (#601).
    # Regression test for the bug fixed by Card 6: millpy-review-plan.py
    # used to write briefs under git_root instead of hub_root/project_root.
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch_specs = [("alpha", "01-alpha.md", ["src/a.py"], [])]
        mill_dir, wiki_root, hub_root, git_root = _make_nested_plan_fixture(tmpdir, batch_specs)
        orig_dir = os.getcwd()
        os.chdir(hub_root)
        try:
            result = subprocess.run(
                [
                    "uv", "run",
                    "--project", str(HUB / "plugins" / "mill"),
                    "python", str(HUB / "plugins" / "mill" / "scripts" / "millpy-review-plan.py"),
                    "--stage", "prepare",
                    "--holistic-only",
                ],
                capture_output=True,
                text=True,
                cwd=str(hub_root),
            )
            assert result.returncode == 0, (
                f"expected exit code 0 for clean nested-layout plan, got {result.returncode}; "
                f"stdout={result.stdout!r}, stderr={result.stderr!r}"
            )
            json_output = json.loads(result.stdout)
            assert json_output.get("stage") == "prepare", (
                f"expected stage='prepare' in JSON output, got {json_output}"
            )
            assert "brief_path" in json_output, (
                f"expected 'brief_path' key in JSON output, got {json_output}"
            )
            brief_path = Path(json_output["brief_path"])
            expected_briefs_dir = hub_root / "_mill" / "briefs"
            wrong_briefs_dir = git_root / "_mill" / "briefs"
            assert str(brief_path).startswith(str(expected_briefs_dir)), (
                f"brief_path must resolve under nested hub_root's _mill/briefs/, "
                f"got {brief_path} (expected under {expected_briefs_dir})"
            )
            assert not str(brief_path).startswith(str(wrong_briefs_dir)), (
                f"brief_path must NOT resolve under git_root's _mill/briefs/, "
                f"got {brief_path} (git_root briefs dir: {wrong_briefs_dir})"
            )
            assert brief_path.exists(), f"expected brief file to exist at {brief_path}"
            print("PASS test28: nested-hub-layout prepare-stage brief_path resolves under hub_root, not git_root (#601)")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test28: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test28 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # project_root rebind: briefs_dir resolves under resolve_active_hub,
    # not resolve_hub_path's decoy (#675)
    # ------------------------------------------------------------------
    errors += test_project_root_rebind_uses_resolve_active_hub_not_resolve_hub_path()

    # ------------------------------------------------------------------
    # Test 29 — fail-loud unrecognized severity in synchronous per-batch
    # dispatch (line 284 call site). A per-batch reviewer response with
    # ONLY a "### [MAJOR]" heading (no "### [BLOCKING]" heading at all)
    # must still surface as blocking_count == 1, proving the synchronous
    # subprocess dispatch path -- the path most divergent from batch 1's
    # finalize_scope() fix -- is fail-loud rather than silently dropping
    # the unrecognized severity from both counters.
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch_specs = [("alpha", "01-alpha.md", ["src/a.py"], [])]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(tmpdir, batch_specs)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            major_only = (
                "# Review\n\n"
                "### [MAJOR] compile break\n\n- b\n\n"
                "### [NIT] minor note\n\n- b\n\n"
                "```yaml\nverdict: REQUEST_CHANGES\n```\n"
            )
            stub.seed([
                (major_only,   "sid-major"),
                (APPROVE_TEXT, "sid-hol"),
            ])
            r = plan_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root)
            assert r.blocking_count == 1, f"expected blocking_count=1, got {r.blocking_count}"
            assert r.nit_count == 1, f"expected nit_count=1, got {r.nit_count}"
            print("PASS test29: unrecognized [MAJOR] severity fail-loud in synchronous per-batch dispatch, nit_count == 1")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test29: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test29 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 30 — #720 holistic-path [MEDIUM]-only regression
    # A holistic response with ONLY a "### [MEDIUM]" heading (no recognized
    # [BLOCKING]/[NIT] heading at all) must fold into blocking_count on the
    # holistic dispatch path, not just the per-batch path Test 29 covers.
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch_specs = [("alpha", "01-alpha.md", ["src/a.py"], [])]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(tmpdir, batch_specs)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            medium_only_holistic = (
                "# Review\n\n"
                "### [MEDIUM] borderline concern\n\n- b\n\n"
                "```yaml\nverdict: REQUEST_CHANGES\n```\n"
            )
            stub.seed([(APPROVE_TEXT, "sid-a"), (medium_only_holistic, "sid-hol")])
            r = plan_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root)
            assert r.blocking_count == 1, f"expected blocking_count=1, got {r.blocking_count}"
            assert r.nit_count == 0, f"expected nit_count=0, got {r.nit_count}"
            print("PASS test30: #720 MEDIUM-fold-in on the holistic dispatch path")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test30: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test30 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 31a — prepare() holistic reviewer_override drives resolution,
    # not config's holistic reviewer (Card 16, check 1)
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch_specs = [("01-setup", "01-setup.md", [], [])]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(tmpdir, batch_specs)
        cfg["roles"]["plan-review"]["holistic"]["reviewer"] = "config-reviewer-should-not-be-used"
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
            result = plan_prepare(
                cfg, SLUG, scope=None, mill_dir=mill_dir, project_root=project_root,
                wiki_root=wiki_root, git_root=project_root, reviewer_override="override-reviewer",
            )
            assert result["model"] == "claude-opus-4-1", (
                f"expected override model claude-opus-4-1, got {result['model']!r}"
            )
            assert result["effort"] == "max", f"expected override effort max, got {result['effort']!r}"
            print("PASS test31a: prepare() holistic reviewer_override drives resolution, not config's reviewer")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test31a: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test31a (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 31b — prepare() holistic reviewer_override: unknown name raises
    # ReviewError mentioning "Unknown reviewer" (Card 16, check 2)
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch_specs = [("01-setup", "01-setup.md", [], [])]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(tmpdir, batch_specs)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            try:
                plan_prepare(
                    cfg, SLUG, scope=None, mill_dir=mill_dir, project_root=project_root,
                    wiki_root=wiki_root, git_root=project_root, reviewer_override="does-not-exist",
                )
                errors += 1
                print("FAIL test31b: expected ReviewError for unknown reviewer_override", file=sys.stderr)
            except ReviewError as exc:
                assert "Unknown reviewer" in str(exc), f"expected 'Unknown reviewer' in error, got {exc!r}"
                print("PASS test31b: prepare() holistic reviewer_override unknown name raises ReviewError")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test31b: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test31b (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 31c — prepare() holistic reviewer_override: cluster override
    # raises ReviewError mentioning "cluster" (Card 16, check 3)
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch_specs = [("01-setup", "01-setup.md", [], [])]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(tmpdir, batch_specs)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            write_local_overlay(
                mill_dir,
                worker_single={
                    "type": "single",
                    "provider": "claude",
                    "model": "claude-sonnet-4-6",
                },
                my_cluster={
                    "type": "cluster",
                    "workers": {"use": "worker_single", "count": 3},
                    "handler": {"use": "worker_single"},
                },
            )
            try:
                plan_prepare(
                    cfg, SLUG, scope=None, mill_dir=mill_dir, project_root=project_root,
                    wiki_root=wiki_root, git_root=project_root, reviewer_override="my_cluster",
                )
                errors += 1
                print("FAIL test31c: expected ReviewError for cluster reviewer_override", file=sys.stderr)
            except ReviewError as exc:
                assert "cluster" in str(exc), f"expected 'cluster' in error, got {exc!r}"
                print("PASS test31c: prepare() holistic reviewer_override cluster raises ReviewError")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test31c: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test31c (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 31d — prepare() holistic reviewer_override skips the
    # large-prompt auto-switch entirely (Card 16, check 4)
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch_specs = [("01-setup", "01-setup.md", [], [])]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(tmpdir, batch_specs)
        cfg["roles"]["plan-review"]["holistic"]["large_prompt"] = {
            "threshold_ktok": 0,
            "reviewer": "large-prompt-reviewer",
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
            result = plan_prepare(
                cfg, SLUG, scope=None, mill_dir=mill_dir, project_root=project_root,
                wiki_root=wiki_root, git_root=project_root, reviewer_override="override-reviewer",
            )
            assert result["model"] == "claude-opus-4-1", (
                f"expected override model claude-opus-4-1 (large-prompt-reviewer never "
                f"consulted), got {result['model']!r}"
            )
            print("PASS test31d: prepare() holistic reviewer_override survives large_prompt auto-switch untouched")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test31d: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test31d (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 31e — prepare() reviewer_override is a documented no-op when
    # scope is not None (batch scope), per the holistic-only Decision
    # (Card 16, check 5)
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch_specs = [("01-setup", "01-setup.md", [], [])]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(tmpdir, batch_specs)
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
            result = plan_prepare(
                cfg, SLUG, scope="01-setup", mill_dir=mill_dir, project_root=project_root,
                wiki_root=wiki_root, git_root=project_root, reviewer_override="override-reviewer",
            )
            assert result["model"] is None, (
                f"expected batch-scope model=None (test_stub has no model key), got {result['model']!r}"
            )
            assert result["scope"] == "01-setup", f"expected scope='01-setup', got {result['scope']!r}"
            print("PASS test31e: prepare() reviewer_override is a no-op outside holistic scope")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test31e: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test31e (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 32a — run() holistic_only=True reviewer_override dispatches the
    # named override, not config's holistic reviewer (Card 17, check 1)
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch_specs = [("alpha", "01-alpha.md", ["src/a.py"], [])]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(tmpdir, batch_specs)
        cfg["roles"]["plan-review"]["holistic"]["reviewer"] = "config-reviewer-should-not-be-used"
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
            stub.seed([(APPROVE_TEXT, "sid-run-plan-override")])
            r = plan_run(
                cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root,
                holistic_only=True, reviewer_override="override-reviewer",
            )
            assert r.verdict == "APPROVE", f"expected APPROVE, got {r.verdict}"
            print("PASS test32a: run() holistic_only reviewer_override dispatches named override")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test32a: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test32a (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 32b — run() holistic_only=True reviewer_override: unknown name
    # raises ReviewError mentioning "Unknown reviewer" (Card 17, check 2)
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch_specs = [("alpha", "01-alpha.md", ["src/a.py"], [])]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(tmpdir, batch_specs)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            try:
                plan_run(
                    cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root,
                    holistic_only=True, reviewer_override="does-not-exist",
                )
                errors += 1
                print("FAIL test32b: expected ReviewError for unknown reviewer_override", file=sys.stderr)
            except ReviewError as exc:
                assert "Unknown reviewer" in str(exc), f"expected 'Unknown reviewer' in error, got {exc!r}"
                print("PASS test32b: run() holistic_only reviewer_override unknown name raises ReviewError")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test32b: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test32b (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 32c — run() holistic_only=True reviewer_override dispatches a
    # non-Claude (Gemini) reviewer, since direct-dispatch call sites pass
    # reject_non_claude=False (Card 17, check 3)
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch_specs = [("alpha", "01-alpha.md", ["src/a.py"], [])]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(tmpdir, batch_specs)
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
            llm_gemini.run_bulk = lambda prompt_text, **kw: (APPROVE_TEXT, "sid-gemini")
            try:
                r = plan_run(
                    cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root,
                    holistic_only=True, reviewer_override="gemini-reviewer",
                )
            finally:
                llm_gemini.run_bulk = original
            assert r.verdict == "APPROVE", f"expected APPROVE, got {r.verdict}"
            print("PASS test32c: run() holistic_only reviewer_override dispatches non-Claude (Gemini) reviewer")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test32c: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test32c (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 32d — run() holistic_only=True reviewer_override skips the
    # large-prompt auto-switch entirely; effort is forwarded to the
    # test_stub provider branch (Card 17, check 4; depends on batch
    # reviewer-override-helper's Card 2 fix)
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch_specs = [("alpha", "01-alpha.md", ["src/a.py"], [])]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(tmpdir, batch_specs)
        cfg["roles"]["plan-review"]["holistic"]["large_prompt"] = {
            "threshold_ktok": 0,
            "reviewer": "large-prompt-reviewer",
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
                        "effort": "max",
                        "tooluse": False,
                    },
                    "large-prompt-reviewer": {
                        "type": "single",
                        "provider": "test_stub",
                        "model": "unused-test-stub-model",
                        "effort": "low",
                        "tooluse": False,
                    },
                },
            )
            stub.seed([(APPROVE_TEXT, "sid-run-plan-large-prompt")])
            r = plan_run(
                cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root,
                holistic_only=True, reviewer_override="override-reviewer",
            )
            assert r.verdict == "APPROVE", f"expected APPROVE, got {r.verdict}"
            assert stub.captured_prompts()[-1][1]["effort"] == "max", (
                f"expected effort='max' forwarded from override-reviewer spec, "
                f"got {stub.captured_prompts()[-1][1]['effort']!r}"
            )
            print("PASS test32d: run() holistic_only reviewer_override skips large-prompt auto-switch, effort forwarded")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test32d: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test32d (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 33 — --max-rounds override forces holistic dispatch despite
    # holistic.rounds:0 (issue #740 regression: the elif gate used to read
    # the raw config value instead of the max_rounds-aware override)
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch_specs = [("alpha", "01-alpha.md", ["src/a.py"], [])]
        mill_dir, wiki_root, project_root, cfg = _make_plan_fixture(tmpdir, batch_specs)
        cfg["roles"]["plan-review"]["holistic"]["rounds"] = 0
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            stub.seed([(APPROVE_TEXT, "sid-max-rounds-override")])
            r = plan_run(
                cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root,
                max_rounds=1, holistic_only=True,
            )
            prompts = stub.captured_prompts()
            assert len(prompts) == 1, (
                f"--max-rounds=1 should force holistic dispatch despite holistic.rounds:0 "
                f"(issue #740 regression: before the fix, the buggy gate read the raw "
                f"config rounds value and skipped holistic entirely, giving 0 prompts "
                f"since holistic_only=True already skips per-batch review), got {len(prompts)}"
            )
            assert len(r.reviews) == 1, f"expected 1 review entry, got {len(r.reviews)}"
            assert r.reviews[0]["scope"] == "holistic"
            assert r.verdict == "APPROVE", f"expected APPROVE, got {r.verdict}"
            print("PASS test33: --max-rounds override forces holistic dispatch despite rounds:0")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test33: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test33 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All _review_plan flow tests passed.")
    return 0


def test_project_root_rebind_uses_resolve_active_hub_not_resolve_hub_path() -> int:
    """project_root rebinds to resolve_active_hub's value, not resolve_hub_path's decoy.

    millpy-review-plan.py's main() imports every module it needs (_agent_dispatch,
    _parent_branch, _paths, _reviewers, _review_cli, _review_common, _review_plan)
    inline, so this test loads the CLI script via importlib.util.spec_from_file_location
    and injects MagicMock stand-ins for each of those names into sys.modules before
    exec_module, exactly as test-review-discussion-flow.py's test_brief_path_nested_layout
    and test-review-code-flow.py's counterpart do. --skip-validate is passed so the
    real (unmocked) _plan_validate module is never imported by the prepare branch.

    resolve_hub_path returns a decoy directory standing in for a stale/escaped
    resolve_hub_path() fallback; resolve_active_hub -- called after slug
    resolution, per the Card 14 rebind -- returns a distinct directory standing
    in for the corrected active task worktree. briefs_dir must resolve under the
    resolve_active_hub value (checked via the recorded resolve_task_path and
    write_brief call args), proving project_root was rebound and not left at
    resolve_hub_path's original value.

    A reversion of the Card 14 fix (never calling resolve_active_hub) causes the
    assertion to fail because resolve_task_path is called with the decoy
    directory instead.

    Returns 0 on success, 1 on failure (matching the errors-accumulator
    convention used throughout this file).
    """
    import importlib.util
    import tempfile
    from unittest.mock import MagicMock, patch

    scripts_dir = HUB / "plugins" / "mill" / "scripts"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        decoy_dir = tmp / "decoy-hub-path"
        decoy_dir.mkdir(parents=True)
        corrected_dir = tmp / "corrected-active-worktree"
        corrected_dir.mkdir(parents=True)

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
        mock_review_common.load_config.return_value = {"paths": {}}
        mock_review_common.find_active_slug.return_value = "test-slug"
        mock_review_common.ReviewError = Exception

        mock_review_plan = MagicMock()
        mock_review_plan.prepare.return_value = {
            "scope": "holistic",
            "round": 1,
            "prompt_text": "prompt",
            "model": "default",
        }

        mock_agent_dispatch = MagicMock()
        mock_agent_dispatch.write_brief.return_value = corrected_dir / "_mill/briefs/brief.md"
        mock_agent_dispatch.output_path_for.return_value = corrected_dir / "_mill/briefs/brief.out.md"
        mock_agent_dispatch.SUBAGENT_REVIEWER = "reviewer"
        mock_agent_dispatch.model_to_tier.return_value = "default"

        mock_reviewers = MagicMock()
        mock_reviewers.ReviewerError = Exception

        mock_review_cli = MagicMock()
        mock_parent_branch = MagicMock()

        injected_modules = {
            "_paths": mock_paths,
            "_review_common": mock_review_common,
            "_review_plan": mock_review_plan,
            "_agent_dispatch": mock_agent_dispatch,
            "_reviewers": mock_reviewers,
            "_review_cli": mock_review_cli,
            "_parent_branch": mock_parent_branch,
        }

        with patch.dict(sys.modules, injected_modules):
            spec = importlib.util.spec_from_file_location(
                "millpy_review_plan",
                scripts_dir / "millpy-review-plan.py",
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            # --skip-validate bypasses the real (unmocked) _plan_validate import
            # this test does not inject; --stage prepare enters the branch
            # where the rebind's project_root value drives briefs_dir.
            with patch("sys.argv", ["prog", "--stage", "prepare", "--skip-validate"]):
                try:
                    mod.main()
                except (TypeError, SystemExit, Exception):
                    # The resolve_active_hub/resolve_task_path calls are
                    # already recorded before any crash on a bare MagicMock
                    # field reaching json.dumps(envelope).
                    pass

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

        write_brief_call = mock_agent_dispatch.write_brief.call_args
        if write_brief_call is None or not write_brief_call[0]:
            print(
                "FAIL: test_project_root_rebind_uses_resolve_active_hub_not_resolve_hub_path:"
                " _agent_dispatch.write_brief was never called",
                file=sys.stderr,
            )
            return 1
        write_brief_briefs_dir = write_brief_call[0][0]
        if write_brief_briefs_dir != corrected_dir / "_mill/briefs":
            print(
                f"FAIL: test_project_root_rebind_uses_resolve_active_hub_not_resolve_hub_path:"
                f" write_brief's briefs_dir arg expected {corrected_dir / '_mill/briefs'},"
                f" got {write_brief_briefs_dir}",
                file=sys.stderr,
            )
            return 1

        print(
            "PASS: plan-review briefs_dir resolves under resolve_active_hub's value,"
            " not resolve_hub_path's decoy"
        )
        return 0


if __name__ == "__main__":
    sys.exit(main())
