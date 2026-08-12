"""Unit-test flow harness for _review_code.run.

Uses _reviewer_test_stub as the reviewer backend.
    All tests run in-process
with no real LLM, no network calls. Covers the bugs fixed in batches 01-05:
- Per-scope round counter (#21/#62/#63)
- Manifest presence in prompts (#5/#7 prevention)
- creates_union suppression (#60)
- Hard-fail on missing refs (#41/#43)
- NEED_CONTEXT resume fallback (#5/#7 recovery)
- moves_sources_union suppression of stale cross-batch Context: refs (#686)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import unittest.mock

import _reviewer_test_stub as stub  # noqa: E402
import _test_registry  # noqa: E402
import _test_helpers  # noqa: E402
from wiki import _client as wiki  # noqa: E402
from _llm_claude import LLMError  # noqa: E402
from _llm_common import ReviewerCallResult  # noqa: E402
from _review_code import run as code_run, finalize as code_finalize, prepare  # noqa: E402
from _review_common import ReviewError  # noqa: E402
from _test_helpers import seed_wiki_config  # noqa: E402

SLUG = "test-slug"

APPROVE_TEXT = "# Review: test\n\n```yaml\nverdict: APPROVE\n```\n"

# References src/a.py which _make_fixture creates on disk — used by tests 5 & 6.
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
    """Return batch file text (single-line Context:/Creates:/Deletes: form)."""
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


def _make_fixture(tmp_path: Path) -> tuple[Path, Path, Path, dict]:
    """Build a standard 3-batch (alpha, beta, gamma) fixture under tmp_path.

    Returns (mill_dir, wiki_root, project_root, cfg).
    project_root is the worktree path;
    callers must os.chdir(project_root).
    alpha Reads src/a.py;
    beta Reads src/b.py;
    gamma Reads src/c.py.
    All three source files are created on disk.
    """
    worktree = tmp_path / "container" / "wts" / SLUG
    worktree.mkdir(parents=True)
    _repo = _test_helpers.init_minimal_git_repo(worktree, branch="main")
    _test_helpers.checkout_new_branch(_repo, f"hanf/{SLUG}")
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

    batch_specs = [
        ("alpha", "01-alpha.md", ["src/a.py"], []),
        ("beta",  "02-beta.md",  ["src/b.py"], []),
        ("gamma", "03-gamma.md", ["src/c.py"], []),
    ]

    (plan_dir / "00-overview.md").write_text(
        _make_overview([(n, f) for n, f, _, _ in batch_specs]), encoding="utf-8"
    )
    for name, file_, reads, creates in batch_specs:
        (plan_dir / file_).write_text(
            _make_batch_file(name, reads, creates), encoding="utf-8"
        )
        for rf in reads:
            p = project_root / rf
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("# placeholder", encoding="utf-8")

    _test_registry.write_to(wiki_root)

    cfg = {
        "paths": {
            "discussion_file": "discussion.md",
            "plan_dir":        "plan/",
            "reviews_dir":     "reviews/",
            "status_md":       "_mill/status.md",
        },
        "spawn": {
            "branch_prefix": "hanf/",
        },
        "llm": {
            "bulk_timeout":     None,
            "holistic_timeout": None,
        },
        "roles": {
            "code-review": {
                "batch":   {"rounds": 3, "reviewer": "test_stub"},
                "holistic": {"rounds": 3, "reviewer": "test_stub"},
            },
        },
    }
    return mill_dir, wiki_root, project_root, cfg


def _seed_approve(n: int) -> None:
    """Seed n approve responses on the stub."""
    stub.seed([(APPROVE_TEXT, f"sid-{i + 1}") for i in range(n)])


def _make_nested_code_fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    """Build a nested-hub-layout code-review fixture under tmp_path.

    Unlike _make_fixture, the git root and the mill hub_root are different directories: hub_root
    lives one level under git_root (git_root/hub), mirroring a repo where .millhouse/ sits in a
    subdirectory of the git toplevel rather than at its root (M2+sub layout).

    A single batch "alpha" reads src/a.py;
    the plan is written directly under hub_root/_mill/plan/ (the CLI's default plan_dir).

    Returns (mill_dir, wiki_root, hub_root, git_root).
    Callers must os.chdir(hub_root) before invoking the CLI so _paths.resolve_hub_path() walks up
    from hub_root and finds .millhouse/config.local.yaml there, while _paths.resolve_git_root()
    still resolves to git_root.

    wiki_root deliberately uses the container-form sibling default (<container>/wiki, resolved via
    _sibling.resolve_path) rather than a paths.wiki override in hub_root's config.local.yaml -- see
    _make_nested_plan_fixture in test-review-plan-flow.py for the full rationale (resolve_wiki_path
    is called with both hub_root and git_root, and only the sibling default agrees across both call
    sites).
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
        # hub_relative_path declares hub_root's own offset from git_root -- the real mill-claim convention for M2+sub (nested-hub) layouts, consumed by _paths.resolve_active_hub to rebase onto hub_root.
        "hub_relative_path: hub\n"
        "spawn:\n  branch_prefix: 'hanf/'\n", encoding="utf-8"
    )

    plan_dir = hub_root / "_mill" / "plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "00-overview.md").write_text(
        _make_overview([("alpha", "01-alpha.md")]), encoding="utf-8"
    )
    (plan_dir / "01-alpha.md").write_text(
        _make_batch_file("alpha", ["src/a.py"], []), encoding="utf-8"
    )
    (hub_root / "src").mkdir(parents=True)
    (hub_root / "src" / "a.py").write_text("# placeholder", encoding="utf-8")

    _test_registry.write_to(wiki_root)
    return mill_dir, wiki_root, hub_root, git_root


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def main() -> int:
    errors = 0

    # ------------------------------------------------------------------
    # Test 1 — per-scope round counter on sequential per-batch calls Regression pin for #21/#62/#63: holistic must start at r1 even after multiple per-batch rounds have been recorded.
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        mill_dir, wiki_root, project_root, cfg = _make_fixture(tmpdir)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            # alpha round 1
            _seed_approve(1)
            r = code_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, batch_name="alpha")
            assert r.round == 1, f"expected round 1, got {r.round}"
            assert r.verdict == "APPROVE"
            fname = Path(r.reviews[0]["file"]).name
            assert "code-review-alpha-r1" in fname, f"unexpected filename: {fname}"
            assert str(project_root / "reviews") in r.reviews[0]["file"], (
                f"review file must be under worktree/reviews/, got {r.reviews[0]['file']!r}"
            )
            print(f"PASS test1a: alpha r1 -> {fname}")

            # alpha round 2 (counter increments per-scope)
            _seed_approve(1)
            r = code_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, batch_name="alpha")
            assert r.round == 2, f"expected round 2, got {r.round}"
            fname = Path(r.reviews[0]["file"]).name
            assert "code-review-alpha-r2" in fname, f"unexpected filename: {fname}"
            print(f"PASS test1b: alpha r2 -> {fname}")

            # beta round 1 (fresh per-scope counter, not r3)
            _seed_approve(1)
            r = code_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, batch_name="beta")
            assert r.round == 1, f"expected round 1 for beta, got {r.round}"
            fname = Path(r.reviews[0]["file"]).name
            assert "code-review-beta-r1" in fname, f"unexpected filename: {fname}"
            print(f"PASS test1c: beta r1 (independent of alpha counter) -> {fname}")

            # holistic round 1 (independent of both per-batch counters)
            _seed_approve(1)
            r = code_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, batch_name=None)
            assert r.round == 1, f"expected holistic round 1, got {r.round}"
            fname = Path(r.reviews[0]["file"]).name
            assert "code-review-r1" in fname, f"unexpected holistic filename: {fname}"
            assert "alpha" not in fname and "beta" not in fname, (
                f"batch name leaked into holistic filename: {fname}"
            )
            print(f"PASS test1d: holistic r1 (per-scope regression #21/#62/#63) -> {fname}")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test1: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test1 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 2 — manifest present in prompt
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        mill_dir, wiki_root, project_root, cfg = _make_fixture(tmpdir)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            _seed_approve(1)
            code_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, batch_name=None)
            prompts = stub.captured_prompts()
            assert prompts, "expected at least one captured prompt"
            first_prompt = prompts[0][0]
            assert "## Files included (N=" in first_prompt, (
                "manifest heading '## Files included (N=' absent from prompt"
            )
            assert "00-overview.md" in first_prompt, (
                "00-overview.md path not listed in prompt manifest"
            )
            print("PASS test2: '## Files included' manifest present in holistic prompt")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test2: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test2 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 3 — creates_union suppression A batch's Reads: path that is in another batch's Creates: must not raise ReviewError even when the file doesn't exist on disk (#60).
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        worktree = tmpdir / "container" / "wts" / SLUG
        worktree.mkdir(parents=True)
        _repo = _test_helpers.init_minimal_git_repo(worktree, branch="main")
        _test_helpers.checkout_new_branch(_repo, f"hanf/{SLUG}")
        (worktree / ".gitignore").write_text("\n", encoding="utf-8")
        mill_dir = worktree / ".millhouse"
        mill_dir.mkdir(parents=True, exist_ok=True)
        wiki_root = tmpdir / "wiki"
        wiki_root.mkdir(parents=True, exist_ok=True)
        seed_wiki_config(wiki_root)
        (wiki_root / "Home.md").write_text(f"## Test Task\n[[{SLUG}]] [active]\n\n_body_\n", encoding="utf-8")
        (mill_dir / "config.local.yaml").write_text(
            f"paths:\n  wiki: '{wiki_root.as_posix()}'\n"
            f"spawn:\n  branch_prefix: 'hanf/'\n", encoding="utf-8"
        )
        project_root = worktree
        plan_dir = worktree / "plan"
        plan_dir.mkdir(parents=True)
        (plan_dir / "00-overview.md").write_text(
            _make_overview([("alpha", "01-alpha.md"), ("beta", "02-beta.md")]),
            encoding="utf-8",
        )
        (plan_dir / "01-alpha.md").write_text(
            _make_batch_file("alpha", ["src/a.py"], ["generated/by_alpha.py"]),
            encoding="utf-8",
        )
        (plan_dir / "02-beta.md").write_text(
            _make_batch_file("beta", ["generated/by_alpha.py"], []),
            encoding="utf-8",
        )
        (project_root / "src").mkdir(parents=True)
        (project_root / "src" / "a.py").write_text("x", encoding="utf-8")
        # generated/by_alpha.py is NOT created on disk
        cfg3 = {
            "paths": {
                "discussion_file": "discussion.md",
                "plan_dir":        "plan/",
                "reviews_dir":     "reviews/",
            },
            "llm": {"bulk_timeout": None, "holistic_timeout": None},
            "roles": {
                "code-review": {
                    "batch":   {"rounds": 3, "reviewer": "test_stub"},
                    "holistic": {"rounds": 3, "reviewer": "test_stub"},
                },
            },
        }
        _test_registry.write_to(wiki_root)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        _seed_approve(1)
        try:
            r = code_run(cfg3, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, batch_name="beta")
            assert r.verdict == "APPROVE", f"expected APPROVE, got {r.verdict}"
            print("PASS test3: creates_union suppresses missing cross-batch Reads ref (#60)")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test3: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test3 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 4 — hard-fail on missing ref not in creates_union (#41/#43)
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        worktree = tmpdir / "container" / "wts" / SLUG
        worktree.mkdir(parents=True)
        _repo = _test_helpers.init_minimal_git_repo(worktree, branch="main")
        _test_helpers.checkout_new_branch(_repo, f"hanf/{SLUG}")
        (worktree / ".gitignore").write_text("\n", encoding="utf-8")
        mill_dir = worktree / ".millhouse"
        mill_dir.mkdir(parents=True, exist_ok=True)
        wiki_root = tmpdir / "wiki"
        wiki_root.mkdir(parents=True, exist_ok=True)
        seed_wiki_config(wiki_root)
        (wiki_root / "Home.md").write_text(f"## Test Task\n[[{SLUG}]] [active]\n\n_body_\n", encoding="utf-8")
        (mill_dir / "config.local.yaml").write_text(
            f"paths:\n  wiki: '{wiki_root.as_posix()}'\n"
            f"spawn:\n  branch_prefix: 'hanf/'\n", encoding="utf-8"
        )
        project_root = worktree
        plan_dir = worktree / "plan"
        plan_dir.mkdir(parents=True)
        (plan_dir / "00-overview.md").write_text(
            _make_overview([("alpha", "01-alpha.md")]), encoding="utf-8"
        )
        (plan_dir / "01-alpha.md").write_text(
            _make_batch_file("alpha", ["nonexistent/path.py"], []),
            encoding="utf-8",
        )
        cfg4 = {
            "paths": {
                "discussion_file": "discussion.md",
                "plan_dir":        "plan/",
                "reviews_dir":     "reviews/",
            },
            "llm": {"bulk_timeout": None, "holistic_timeout": None},
            "roles": {
                "code-review": {
                    "batch":   {"rounds": 3, "reviewer": "test_stub"},
                    "holistic": {"rounds": 3, "reviewer": "test_stub"},
                },
            },
        }
        _test_registry.write_to(wiki_root)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        _seed_approve(1)
        try:
            code_run(cfg4, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, batch_name="alpha")
            errors += 1
            print("FAIL test4: expected ReviewError for missing ref, none raised", file=sys.stderr)
        except ReviewError as exc:
            msg = str(exc)
            try:
                assert "referenced path not found" in msg, (
                    f"error message missing 'referenced path not found': {msg}"
                )
                assert "nonexistent/path.py" in msg, f"path not in error message: {msg}"
                print("PASS test4: hard-fail on missing ref not in creates_union (#41/#43)")
            except AssertionError as ae:
                errors += 1
                print(f"FAIL test4 (wrong error message): {ae}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test4 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 5 — NEED_CONTEXT resume fallback: 1 retry -> APPROVE (#5/#7)
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        mill_dir, wiki_root, project_root, cfg = _make_fixture(tmpdir)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        # src/a.py exists on disk (created by _make_fixture);
        # NEED_CONTEXT_TEXT claims it is missing so resolve_existing_paths returns it -> retry fires.
        stub.seed([
            (NEED_CONTEXT_TEXT, "sid-1"),
            (APPROVE_TEXT,      "sid-2"),
        ])
        try:
            r = code_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, batch_name="alpha")
            assert r.verdict == "APPROVE", f"expected APPROVE after retry, got {r.verdict}"
            prompts = stub.captured_prompts()
            assert len(prompts) == 2, f"expected 2 captured prompts, got {len(prompts)}"
            _, retry_kwargs = prompts[1]
            assert retry_kwargs == {"session_id": "sid-1", "resume": True, "timeout": None, "effort": None}, (
                f"retry kwargs wrong: {retry_kwargs}"
            )
            retry_text = prompts[1][0]
            assert retry_text.startswith("## Re-attached files"), (
                f"retry prompt must start with '## Re-attached files', got: {retry_text[:80]!r}"
            )
            assert r.reviews[0]["session_id"] == "sid-2", (
                f"expected session_id 'sid-2', got {r.reviews[0]['session_id']!r}"
            )
            print("PASS test5: NEED_CONTEXT retry -> APPROVE, session_id from retry captured")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test5: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test5 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 6 — NEED_CONTEXT propagated when retry also returns NEED_CONTEXT
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        mill_dir, wiki_root, project_root, cfg = _make_fixture(tmpdir)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        stub.seed([
            (NEED_CONTEXT_TEXT, "sid-1"),
            (NEED_CONTEXT_TEXT, "sid-2"),
        ])
        try:
            r = code_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, batch_name="alpha")
            assert r.verdict == "NEED_CONTEXT", (
                f"expected NEED_CONTEXT propagation, got {r.verdict}"
            )
            prompts = stub.captured_prompts()
            assert len(prompts) == 2, (
                f"expected exactly 2 prompts (no 3rd retry), got {len(prompts)}"
            )
            print("PASS test6: second NEED_CONTEXT propagated to caller without further retry")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test6: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test6 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 7 — max_rounds kwarg override
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        project_root = tmpdir / "container" / "wts" / SLUG
        project_root.mkdir(parents=True)
        _repo = _test_helpers.init_minimal_git_repo(project_root, branch="main")
        _test_helpers.checkout_new_branch(_repo, f"hanf/{SLUG}")
        (project_root / ".gitignore").write_text("\n", encoding="utf-8")
        wiki_root = tmpdir / "wiki"
        wiki_root.mkdir(parents=True, exist_ok=True)
        seed_wiki_config(wiki_root)
        (wiki_root / "Home.md").write_text(f"## Test Task\n[[{SLUG}]] [active]\n\n_body_\n", encoding="utf-8")
        mill_dir = project_root / ".millhouse"
        mill_dir.mkdir(parents=True, exist_ok=True)
        (mill_dir / "config.local.yaml").write_text(
            f"paths:\n  wiki: '{wiki_root.as_posix()}'\n"
            f"spawn:\n  branch_prefix: 'hanf/'\n", encoding="utf-8"
        )
        plan_dir = project_root / "plan"
        plan_dir.mkdir(parents=True)
        (plan_dir / "00-overview.md").write_text(
            _make_overview([("foo", "01-foo.md")]), encoding="utf-8"
        )
        (plan_dir / "01-foo.md").write_text(
            _make_batch_file("foo", ["src/f.py"], []), encoding="utf-8"
        )
        (project_root / "src").mkdir(parents=True)
        (project_root / "src" / "f.py").write_text("x", encoding="utf-8")

        cfg7 = {
            "paths": {
                "discussion_file": "discussion.md",
                "plan_dir":        "plan/",
                "reviews_dir":     "reviews/",
            },
            "llm": {"bulk_timeout": None, "holistic_timeout": None},
            "roles": {
                "code-review": {
                    "batch":   {"rounds": 3, "reviewer": "test_stub"},
                    "holistic": {"rounds": 3, "reviewer": "test_stub"},
                },
            },
        }
        _test_registry.write_to(wiki_root)

        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            # Pre-populate 3 review files for batch "foo"
            _seed_approve(3)
            code_run(cfg7, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, batch_name="foo")
            code_run(cfg7, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, batch_name="foo")
            code_run(cfg7, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, batch_name="foo")

            # Round 4 without kwarg: cfg.rounds == 3 -> ReviewError
            try:
                _seed_approve(1)
                code_run(cfg7, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, batch_name="foo")
                errors += 1
                print("FAIL test7: expected ReviewError for round 4 with cfg max=3", file=sys.stderr)
            except Exception as exc:
                if "exceeds max" in str(exc):
                    print("PASS test7a: round 4 raises ReviewError without max_rounds kwarg")
                else:
                    errors += 1
                    print(f"FAIL test7a: unexpected exception: {exc}", file=sys.stderr)

            # Round 4 with max_rounds=5 kwarg: should succeed
            _seed_approve(1)
            r4 = code_run(cfg7, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, batch_name="foo", max_rounds=5)
            assert r4.round == 4, f"expected round 4, got {r4.round}"
            fname4 = Path(r4.reviews[0]["file"]).name
            assert "code-review-foo-r4" in fname4, f"unexpected filename: {fname4}"
            print(f"PASS test7b: round 4 succeeds with max_rounds=5 -> {fname4}")

        except AssertionError as exc:
            errors += 1
            print(f"FAIL test7: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test7 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 8 — blocking_count populated from BLOCKING headings
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        mill_dir, wiki_root, project_root, cfg = _make_fixture(tmpdir)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            three_blockings = (
                "# Review: test\n\n"
                "### [BLOCKING] issue one\n\n- bullet\n\n"
                "### [BLOCKING] issue two\n\n- bullet\n\n"
                "### [BLOCKING] issue three\n\n- bullet\n\n"
                "```yaml\nverdict: REQUEST_CHANGES\n```\n"
            )
            stub.seed([(three_blockings, "sid-b1")])
            r = code_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, batch_name="alpha")
            assert r.blocking_count == 3, f"expected blocking_count=3, got {r.blocking_count}"
            print("PASS test8a: three BLOCKING headings -> blocking_count == 3")

            stub.seed([(APPROVE_TEXT, "sid-b2")])
            r2 = code_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, batch_name="beta")
            assert r2.blocking_count == 0, f"expected blocking_count=0, got {r2.blocking_count}"
            print("PASS test8b: no BLOCKING headings -> blocking_count == 0")

        except AssertionError as exc:
            errors += 1
            print(f"FAIL test8: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test8 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 9 — ERROR parity: initial LLM call raises (per-batch)
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        mill_dir, wiki_root, project_root, cfg = _make_fixture(tmpdir)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        original_run = stub.run
        def _raise_boom(prompt_text, **kw):
            raise LLMError("seeded boom")
        stub.run = _raise_boom
        stub.seed([])  # clear prompts log
        try:
            r = code_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, batch_name="alpha")
            assert r.verdict == "ERROR", f"expected ERROR for all-ERROR run, got {r.verdict}"
            assert len(r.reviews) == 1
            rev = r.reviews[0]
            assert rev["verdict"] == "ERROR", f"expected ERROR entry, got {rev['verdict']}"
            assert rev["file"] is None, f"expected file=None, got {rev['file']}"
            assert "seeded boom" in rev["error"], f"error field wrong: {rev['error']}"
            assert rev["session_id"] is None
            assert all(rv["verdict"] == "ERROR" for rv in r.reviews), f"expected all sub-reviews ERROR, got {[rv['verdict'] for rv in r.reviews]}"
            print("PASS test9: initial LLM failure -> ReviewResult(ERROR) not raise")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test9: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test9 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            stub.run = original_run
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 10 — ERROR parity: initial LLM call raises (holistic)
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        mill_dir, wiki_root, project_root, cfg = _make_fixture(tmpdir)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        original_run = stub.run
        def _raise_boom(prompt_text, **kw):
            raise LLMError("seeded boom")
        stub.run = _raise_boom
        stub.seed([])
        try:
            r = code_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, batch_name=None)
            assert r.verdict == "ERROR", f"expected ERROR for all-ERROR run, got {r.verdict}"
            rev = r.reviews[0]
            assert rev["verdict"] == "ERROR"
            assert rev["scope"] == "holistic"
            assert "seeded boom" in rev["error"]
            assert all(rv["verdict"] == "ERROR" for rv in r.reviews), f"expected all sub-reviews ERROR, got {[rv['verdict'] for rv in r.reviews]}"
            print("PASS test10: holistic LLM failure -> ReviewResult(ERROR) not raise")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test10: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test10 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            stub.run = original_run
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 11 — ERROR on resume: first call returns NEED_CONTEXT, retry raises
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        mill_dir, wiki_root, project_root, cfg = _make_fixture(tmpdir)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        original_run = stub.run
        call_count = 0
        def _seq(prompt_text, **kw):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return original_run(prompt_text, **kw)
            raise LLMError("seeded boom")
        stub.seed([(NEED_CONTEXT_TEXT, "sid-1")])
        stub.run = _seq
        try:
            r = code_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, batch_name="alpha")
            assert r.verdict == "ERROR", f"expected ERROR for all-ERROR run, got {r.verdict}"
            rev = r.reviews[0]
            assert rev["verdict"] == "ERROR"
            assert rev["error"].startswith("resume retry failed:"), (
                f"error should start with 'resume retry failed:': {rev['error']}"
            )
            assert rev["session_id"] is None
            assert all(rv["verdict"] == "ERROR" for rv in r.reviews), f"expected all sub-reviews ERROR, got {[rv['verdict'] for rv in r.reviews]}"
            print("PASS test11: resume LLM failure -> ERROR entry with 'resume retry failed:' prefix")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test11: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test11 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            stub.run = original_run
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 12 — deletes surface: ## Intentionally deleted in prompt
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        worktree = tmpdir / "container" / "wts" / SLUG
        worktree.mkdir(parents=True)
        _repo = _test_helpers.init_minimal_git_repo(worktree, branch="main")
        _test_helpers.checkout_new_branch(_repo, f"hanf/{SLUG}")
        (worktree / ".gitignore").write_text("\n", encoding="utf-8")
        mill_dir = worktree / ".millhouse"
        mill_dir.mkdir(parents=True, exist_ok=True)
        wiki_root = tmpdir / "wiki"
        wiki_root.mkdir(parents=True, exist_ok=True)
        seed_wiki_config(wiki_root)
        (wiki_root / "Home.md").write_text(f"## Test Task\n[[{SLUG}]] [active]\n\n_body_\n", encoding="utf-8")
        (mill_dir / "config.local.yaml").write_text(
            f"paths:\n  wiki: '{wiki_root.as_posix()}'\n"
            f"spawn:\n  branch_prefix: 'hanf/'\n", encoding="utf-8"
        )
        project_root = worktree
        plan_dir = worktree / "plan"
        plan_dir.mkdir(parents=True)
        (plan_dir / "00-overview.md").write_text(
            _make_overview([("alpha", "01-alpha.md")]), encoding="utf-8"
        )
        (plan_dir / "01-alpha.md").write_text(
            _make_batch_file("alpha", ["src/a.py"], [], deletes=["legacy/x.py"]),
            encoding="utf-8",
        )
        (project_root / "src").mkdir(parents=True)
        (project_root / "src" / "a.py").write_text("x", encoding="utf-8")
        cfg12 = {
            "paths": {
                "discussion_file": "discussion.md",
                "plan_dir":        "plan/",
                "reviews_dir":     "reviews/",
            },
            "llm": {"bulk_timeout": None, "holistic_timeout": None},
            "roles": {
                "code-review": {
                    "batch":   {"rounds": 3, "reviewer": "test_stub"},
                    "holistic": {"rounds": 3, "reviewer": "test_stub"},
                },
            },
        }
        _test_registry.write_to(wiki_root)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        _seed_approve(1)
        try:
            code_run(cfg12, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, batch_name="alpha")
            prompts = stub.captured_prompts()
            assert prompts, "expected at least one captured prompt"
            first_prompt = prompts[0][0]
            assert "## Intentionally deleted" in first_prompt, (
                "'## Intentionally deleted' heading absent from prompt"
            )
            assert "legacy/x.py" in first_prompt, (
                "'legacy/x.py' token absent from prompt"
            )
            print("PASS test12: Deletes: token surfaces as '## Intentionally deleted' in prompt")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test12: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test12 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 13 — timeout plumbing: bulk_timeout and holistic_timeout forwarded
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        mill_dir, wiki_root, project_root, cfg = _make_fixture(tmpdir)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        cfg["llm"]["bulk_timeout"] = 900
        cfg["llm"]["holistic_timeout"] = 1800
        try:
            _seed_approve(1)
            code_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, batch_name="alpha")
            prompts = stub.captured_prompts()
            assert prompts, "expected at least one captured prompt"
            _, kwargs = prompts[0]
            assert kwargs["timeout"] == 900, (
                f"per-batch call: expected timeout=900, got {kwargs['timeout']}"
            )
            print("PASS test13a: bulk_timeout=900 forwarded to reviewer for per-batch call")

            _seed_approve(1)
            code_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, batch_name=None)
            prompts = stub.captured_prompts()
            _, kwargs = prompts[0]
            assert kwargs["timeout"] == 1800, (
                f"holistic call: expected timeout=1800, got {kwargs['timeout']}"
            )
            print("PASS test13b: holistic_timeout=1800 forwarded to reviewer for holistic call")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test13: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test13 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 14 — diff-scoping (effort threading removed; covered by test-reviewer-single.py)
    # ------------------------------------------------------------------

    # 14c: per-batch with start_sha present -> prompt contains DIFF delimiter
    with _test_helpers.safe_temp_dir() as tmpdir:
        mill_dir, wiki_root, project_root, cfg = _make_fixture(tmpdir)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            subprocess.run(
                ["git", "-C", str(project_root), "config", "user.email", "t@t.com"],
                check=True, capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(project_root), "config", "user.name", "T"],
                check=True, capture_output=True,
            )
            (project_root / "src" / "a.py").write_text("x\n" * 2000, encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(project_root), "add", "src/a.py"],
                check=True, capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(project_root), "commit", "-m", "initial a.py"],
                check=True, capture_output=True,
            )
            start_sha = subprocess.run(
                ["git", "-C", str(project_root), "rev-parse", "HEAD"],
                check=True, capture_output=True, text=True,
            ).stdout.strip()
            with open(project_root / "src" / "a.py", "a", encoding="utf-8") as fh:
                fh.write("y\n" * 5)
            subprocess.run(
                ["git", "-C", str(project_root), "add", "src/a.py"],
                check=True, capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(project_root), "commit", "-m", "small change"],
                check=True, capture_output=True,
            )
            (project_root / "_mill").mkdir(exist_ok=True)
            (project_root / "_mill" / "status.md").write_text(
                "# Status\n\n"
                "```yaml\n"
                f"phase: coding\nslug: {SLUG}\nbranch: {SLUG}\n"
                "plan: plan\nparent: main\ntask: test\n"
                "```\n\n"
                "## Batches\n\n"
                "```yaml\n"
                f"batches:\n  - name: alpha\n    state: approved\n    start_sha: {start_sha}\n"
                "```\n",
                encoding="utf-8",
            )
            _seed_approve(1)
            code_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, batch_name="alpha")
            prompts = stub.captured_prompts()
            assert prompts, "expected at least one captured prompt"
            assert "--- DIFF:" in prompts[0][0], (
                f"expected DIFF delimiter in prompt; prompt[:300]={prompts[0][0][:300]!r}"
            )
            print("PASS test14c: per-batch with start_sha uses diff-scoping (DIFF delimiter in prompt)")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test14c: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test14c (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # 14d: per-batch with missing start_sha -> prompt uses FILE delimiter (no DIFF)
    with _test_helpers.safe_temp_dir() as tmpdir:
        mill_dir, wiki_root, project_root, cfg = _make_fixture(tmpdir)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            (project_root / "status.md").write_text(
                "# Status\n\n"
                "```yaml\n"
                f"phase: coding\nslug: {SLUG}\nbranch: {SLUG}\n"
                "plan: plan\nparent: main\ntask: test\n"
                "```\n\n"
                "## Batches\n\n"
                "```yaml\n"
                f"batches:\n  - name: alpha\n    state: approved\n"
                "```\n",
                encoding="utf-8",
            )
            _seed_approve(1)
            code_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, batch_name="alpha")
            prompts = stub.captured_prompts()
            assert prompts, "expected at least one captured prompt"
            assert "--- DIFF:" not in prompts[0][0], (
                "expected no DIFF delimiter when start_sha is absent"
            )
            print("PASS test14d: per-batch with missing start_sha falls back to full file content")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test14d: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test14d (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # 14e: per-batch with large diff -> prompt uses FILE delimiter (not DIFF)
    with _test_helpers.safe_temp_dir() as tmpdir:
        mill_dir, wiki_root, project_root, cfg = _make_fixture(tmpdir)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            subprocess.run(
                ["git", "-C", str(project_root), "config", "user.email", "t@t.com"],
                check=True, capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(project_root), "config", "user.name", "T"],
                check=True, capture_output=True,
            )
            (project_root / "src" / "a.py").write_text("x\n" * 20, encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(project_root), "add", "src/a.py"],
                check=True, capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(project_root), "commit", "-m", "initial a.py"],
                check=True, capture_output=True,
            )
            start_sha = subprocess.run(
                ["git", "-C", str(project_root), "rev-parse", "HEAD"],
                check=True, capture_output=True, text=True,
            ).stdout.strip()
            (project_root / "src" / "a.py").write_text("y\n" * 20, encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(project_root), "add", "src/a.py"],
                check=True, capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(project_root), "commit", "-m", "large rewrite"],
                check=True, capture_output=True,
            )
            (project_root / "status.md").write_text(
                "# Status\n\n"
                "```yaml\n"
                f"phase: coding\nslug: {SLUG}\nbranch: {SLUG}\n"
                "plan: plan\nparent: main\ntask: test\n"
                "```\n\n"
                "## Batches\n\n"
                "```yaml\n"
                f"batches:\n  - name: alpha\n    state: approved\n    start_sha: {start_sha}\n"
                "```\n",
                encoding="utf-8",
            )
            _seed_approve(1)
            code_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, batch_name="alpha")
            prompts = stub.captured_prompts()
            assert prompts, "expected at least one captured prompt"
            assert "--- DIFF:" not in prompts[0][0], (
                "expected no DIFF delimiter when diff exceeds threshold"
            )
            print("PASS test14e: per-batch with large diff falls back to full file content")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test14e: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test14e (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 15 — code review parse_verdict failure returns ERROR envelope (#315)
    # Tests both holistic (batch_name=None) and per-batch (batch_name="alpha").
    # Unparseable output -> ERROR entry with file path.
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        mill_dir, wiki_root, project_root, cfg = _make_fixture(tmpdir)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            # Test holistic mode (batch_name=None)
            stub.seed([
                ("# Raw prose without yaml block\n\nCode looks good.", "sid-hol"),
            ])
            r_hol = code_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, batch_name=None)
            assert r_hol.verdict in ("ERROR", "REQUEST_CHANGES"), (
                f"expected ERROR or REQUEST_CHANGES, got {r_hol.verdict}"
            )
            assert len(r_hol.reviews) >= 1, f"expected at least 1 review, got {len(r_hol.reviews)}"
            assert r_hol.reviews[0]["verdict"] == "ERROR", (
                f"expected ERROR verdict, got {r_hol.reviews[0]['verdict']}"
            )
            assert "parse_verdict failed" in r_hol.reviews[0].get("error", ""), (
                f"error message missing 'parse_verdict failed': {r_hol.reviews[0].get('error')}"
            )
            assert r_hol.reviews[0]["file"] is not None, "ERROR entry should have a file path"
            file_path_hol = Path(r_hol.reviews[0]["file"])
            assert file_path_hol.exists(), f"review file should exist on disk: {file_path_hol}"

            # Test per-batch mode (batch_name="alpha")
            stub.seed([
                ("# Raw prose\n\nBatch code OK.", "sid-batch"),
            ])
            r_batch = code_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, batch_name="alpha")
            assert r_batch.verdict in ("ERROR", "REQUEST_CHANGES"), (
                f"expected ERROR or REQUEST_CHANGES for per-batch, got {r_batch.verdict}"
            )
            assert len(r_batch.reviews) >= 1, f"expected at least 1 review, got {len(r_batch.reviews)}"
            assert r_batch.reviews[0]["verdict"] == "ERROR", (
                f"expected ERROR verdict for per-batch, got {r_batch.reviews[0]['verdict']}"
            )
            assert "parse_verdict failed" in r_batch.reviews[0].get("error", ""), (
                f"error message missing 'parse_verdict failed': {r_batch.reviews[0].get('error')}"
            )
            assert r_batch.reviews[0]["file"] is not None, "per-batch ERROR entry should have a file path"
            file_path_batch = Path(r_batch.reviews[0]["file"])
            assert file_path_batch.exists(), f"review file should exist on disk: {file_path_batch}"

            print("PASS test15: code review parse_verdict failure emits ERROR envelope (#315)")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test15: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test15 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 16 — rounds=0 holistic early return (APPROVE stub)
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        mill_dir, wiki_root, project_root, cfg = _make_fixture(tmpdir)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        cfg["roles"]["code-review"]["holistic"]["rounds"] = 0
        try:
            r = code_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, batch_name=None)
            assert r.verdict == "APPROVE", f"expected APPROVE for rounds=0, got {r.verdict}"
            assert r.round == 0, f"expected round=0, got {r.round}"
            assert r.blocking_count == 0, f"expected blocking_count=0, got {r.blocking_count}"
            print("PASS test16: rounds=0 holistic -> APPROVE stub with round=0, blocking_count=0")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test16: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test16 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 17 — nit_count computed from review output
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        mill_dir, wiki_root, project_root, cfg = _make_fixture(tmpdir)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            # Review with 3 NITs and APPROVE verdict
            review_with_nits = (
                "# Review: test\n\n"
                "```yaml\nverdict: APPROVE\n```\n\n"
                "### [NIT] minor style issue\n"
                "### [NIT] another minor issue\n"
                "### [NIT] third minor note\n"
            )
            _seed_approve(0)
            stub.seed([(review_with_nits, "sid-nits")])
            r = code_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, batch_name="alpha")
            assert r.verdict == "APPROVE", f"expected APPROVE, got {r.verdict}"
            assert r.nit_count == 3, f"expected nit_count=3, got {r.nit_count}"
            print("PASS test17a: nit_count=3 computed from review with 3 [NIT] headings")

            # Review with zero NITs (only APPROVE, no [NIT] headings)
            review_no_nits = (
                "# Review: test\n\n"
                "```yaml\nverdict: APPROVE\n```\n\n"
                "This looks good.\n"
            )
            _seed_approve(0)
            stub.seed([(review_no_nits, "sid-no-nits")])
            r = code_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, batch_name="beta")
            assert r.verdict == "APPROVE", f"expected APPROVE, got {r.verdict}"
            assert r.nit_count == 0, f"expected nit_count=0, got {r.nit_count}"
            print("PASS test17b: nit_count=0 when no [NIT] headings present")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test17: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test17 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 18 — prior-notes digest renders correctly in prompt
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        mill_dir, wiki_root, project_root, cfg = _make_fixture(tmpdir)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            # Create a prior-notes digest file
            briefs_dir = project_root / "_mill" / "briefs"
            briefs_dir.mkdir(parents=True, exist_ok=True)
            prior_notes_path = briefs_dir / "prior-digest.txt"
            prior_notes_content = (
                "- Title 1: issue was about naming conventions\n"
                "- Title 2: style suggestion, prefer foo over bar\n"
            )
            prior_notes_path.write_text(prior_notes_content, encoding="utf-8")

            # Run code review with prior_notes
            _seed_approve(1)
            r = code_run(
                cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root,
                batch_name="alpha", prior_notes=prior_notes_path
            )
            assert r.verdict == "APPROVE", f"expected APPROVE, got {r.verdict}"

            # Check that the digest appears in the rendered prompt
            prompts = stub.captured_prompts()
            assert prompts, "expected at least one prompt"
            prompt_text = prompts[0][0]
            assert "Title 1: issue was about naming conventions" in prompt_text, (
                "prior-notes content should appear in prompt"
            )
            assert "Title 2: style suggestion" in prompt_text, (
                "prior-notes content should appear in prompt"
            )
            assert "Do NOT escalate" in prompt_text, (
                "escalation-justification rule should appear in prompt"
            )
            print("PASS test18a: prior-notes digest renders in prompt")

            # Test round 1: prior_notes=None should render (none)
            mill_dir2, wiki_root2, project_root2, cfg2 = _make_fixture(tmpdir / "test2")
            orig_dir2 = os.getcwd()
            os.chdir(project_root2)
            _seed_approve(1)
            r2 = code_run(cfg2, SLUG, mill_dir2, wiki_root2, project_root2, git_root=project_root2, batch_name="alpha")
            assert r2.verdict == "APPROVE"
            prompts2 = stub.captured_prompts()
            prompt_text2 = prompts2[-1][0]  # last prompt
            # Should contain (none) or mention round 1 explicitly
            assert "(none)" in prompt_text2 or "Prior non-blocking items" in prompt_text2, (
                f"prompt should mention prior-nonblocking section, got: {prompt_text2[200:600]}"
            )
            print("PASS test18b: round 1 without prior-notes renders (none) without KeyError")
            os.chdir(orig_dir2)

        except AssertionError as exc:
            errors += 1
            print(f"FAIL test18: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test18 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 19 — Move targets included in code review bulk (Card 19)
    # A batch declares a Moves: entry;
    # the target file exists on disk (simulating post-implementation state).
    # The code-review prompt must reference the target file path so the reviewer can inspect the result.
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
        mill_dir, wiki_root, project_root, cfg = _make_fixture(tmpdir)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            plan_dir = project_root / "plan"
            # Overwrite the alpha batch to declare a move: old/module.py -> new/module.py
            (plan_dir / "01-alpha.md").write_text(
                _make_batch_file_with_moves(
                    "alpha",
                    ["src/a.py"],
                    [],
                    moves=[("old/module.py", "new/module.py")],
                ),
                encoding="utf-8",
            )
            # Create the move TARGET on disk (post-implementation: target exists, source gone)
            (project_root / "new").mkdir(parents=True)
            (project_root / "new" / "module.py").write_text(
                "# relocated module content\n", encoding="utf-8"
            )

            _seed_approve(1)
            code_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, batch_name="alpha")

            prompts = stub.captured_prompts()
            assert prompts, "expected at least one captured prompt"
            prompt_text = prompts[0][0]
            assert "new/module.py" in prompt_text, (
                "move target 'new/module.py' not found in code-review prompt"
            )
            print("PASS test19: Moves: target appears in code-review prompt")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test19: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test19 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 21 — Rename NIT spliced into per-batch finalize (Card 21)
    # When a batch declares Moves: and git diff reports add+delete (not a rename), finalize must splice an advisory [NIT] into the written review file without changing the verdict from APPROVE.
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        mill_dir, wiki_root, project_root, cfg = _make_fixture(tmpdir)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            plan_dir = project_root / "plan"
            # Overwrite the alpha batch file to declare a move pair.
            def _make_batch_with_moves_for_finalize(name: str, moves: list[tuple[str, str]]) -> str:
                """Return minimal batch file text with a Moves: field."""
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
                    "- **Context:** none\n"
                    "- **Edits:** none\n"
                    "- **Creates:** none\n"
                    "- **Deletes:** none\n"
                    f"- **Moves:**{moves_part}\n"
                )

            (plan_dir / "01-alpha.md").write_text(
                _make_batch_with_moves_for_finalize(
                    "alpha",
                    [("old/module.py", "new/module.py")],
                ),
                encoding="utf-8",
            )

            # Write status.md with a start_sha so _splice_rename_nit_findings can find a start_sha for the batch.
            # The SHA value is a plausible git hash;
            # the actual git diff is mocked so validity does not matter.
            fake_start_sha = "aabbccdd1234567890abcdef1234567890abcdef"
            mill_state_dir = project_root / "_mill"
            mill_state_dir.mkdir(parents=True, exist_ok=True)
            (mill_state_dir / "status.md").write_text(
                "# Status: test-slug\n\n"
                "```yaml\n"
                "phase: implement\n"
                "```\n\n"
                "## Batches\n\n"
                "```yaml\n"
                f"batches:\n  - name: alpha\n    start_sha: {fake_start_sha}\n"
                "```\n",
                encoding="utf-8",
            )

            # Mock _subprocess_util.run so git diff returns an add+delete diff (no R-status line), which the rename check must flag as a NIT.
            add_delete_diff = "A\tnew/module.py\nD\told/module.py\n"
            fake_completed = subprocess.CompletedProcess(
                args=[], returncode=0, stdout=add_delete_diff, stderr=""
            )

            reviews_dir = project_root / "reviews"
            reviews_dir.mkdir(parents=True, exist_ok=True)

            approve_raw = (
                "# Review: test\n\n"
                "```yaml\nverdict: APPROVE\n```\n\n"
                "## Findings\n\n(none)\n\n"
                "## Verdict\n\nAPPROVE\n"
            )

            with unittest.mock.patch("_subprocess_util.run", return_value=fake_completed):
                result = code_finalize(
                    cfg,
                    SLUG,
                    approve_raw,
                    scope="alpha",
                    round_n=1,
                    reviews_dir=reviews_dir,
                    mill_dir=mill_dir,
                    project_root=project_root,
                    wiki_root=wiki_root,
                    git_root=project_root,
                )

            assert result.verdict == "APPROVE", (
                f"NIT must not change verdict from APPROVE, got {result.verdict!r}"
            )
            assert result.blocking_count == 0, (
                f"NIT must not increment blocking_count, got {result.blocking_count}"
            )
            # Read the written review file and confirm the [NIT] block is present.
            review_files = list(reviews_dir.glob("*.md"))
            assert review_files, "finalize must have written a review file"
            review_text = review_files[0].read_text(encoding="utf-8")
            assert "[NIT]" in review_text, (
                "advisory rename NIT was not spliced into the review file"
            )
            assert "old/module.py" in review_text, (
                "NIT must reference the undetected move source path"
            )
            assert "new/module.py" in review_text, (
                "NIT must reference the undetected move destination path"
            )
            print("PASS test21: rename NIT spliced into finalize; verdict unchanged")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test21: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test21 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 22 — nested-hub-layout: prepare-stage brief_path resolves under the nested hub_root's _mill/briefs/, not under git_root's (#607).
    # Regression test for the bug fixed by Card 7: millpy-review-code.py used to write briefs under git_root instead of hub_root/project_root.
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        mill_dir, wiki_root, hub_root, git_root = _make_nested_code_fixture(tmpdir)
        orig_dir = os.getcwd()
        os.chdir(hub_root)
        try:
            result = subprocess.run(
                [
                    "uv", "run",
                    "--project", str(HUB / "plugins" / "mill"),
                    "python", str(HUB / "plugins" / "mill" / "scripts" / "millpy-review-code.py"),
                    "--stage", "prepare",
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
            print("PASS test22: nested-hub-layout prepare-stage brief_path resolves under hub_root, not git_root (#607)")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test22: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test22 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 23 — Moves: source suppresses a stale cross-batch Context: ref (#686).
    # Batch "alpha"'s Card 1 Context: references docs/old-name.md.
    # Batch "beta" (later in the plan, depends on alpha) relocates that exact path via Moves:.
    # Post-implementation, docs/new-name.md exists on disk and docs/old-name.md does not.
    # Before the fix, prepare() discarded the moves-sources half of compute_moves_union()'s return value, so the stale ref hard-failed resolve_ref_paths with ReviewError instead of being suppressed the same way an already-deleted path is (mirrors test3's creates_union-suppression baseline and test4's confirmation that an unsuppressed missing path still hard-fails).
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        worktree = tmpdir / "container" / "wts" / SLUG
        worktree.mkdir(parents=True)
        _repo = _test_helpers.init_minimal_git_repo(worktree, branch="main")
        _test_helpers.checkout_new_branch(_repo, f"hanf/{SLUG}")
        (worktree / ".gitignore").write_text("\n", encoding="utf-8")
        mill_dir = worktree / ".millhouse"
        mill_dir.mkdir(parents=True, exist_ok=True)
        wiki_root = tmpdir / "wiki"
        wiki_root.mkdir(parents=True, exist_ok=True)
        seed_wiki_config(wiki_root)
        (wiki_root / "Home.md").write_text(f"## Test Task\n[[{SLUG}]] [active]\n\n_body_\n", encoding="utf-8")
        (mill_dir / "config.local.yaml").write_text(
            f"paths:\n  wiki: '{wiki_root.as_posix()}'\n"
            f"spawn:\n  branch_prefix: 'hanf/'\n", encoding="utf-8"
        )
        project_root = worktree
        plan_dir = worktree / "plan"
        plan_dir.mkdir(parents=True)

        def _make_batch_with_context_and_moves(
            name: str,
            *,
            context: list[str] | None = None,
            moves: list[tuple[str, str]] | None = None,
        ) -> str:
            """Return minimal batch file text with Context:/Moves: fields."""
            context_part = ", ".join(f"`{c}`" for c in (context or [])) if context else "none"
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
                f"- **Context:** {context_part}\n"
                "- **Edits:** none\n"
                "- **Creates:** none\n"
                "- **Deletes:** none\n"
                f"- **Moves:**{moves_part}\n"
            )

        # Batch A ("alpha"): Card 1's Context: references docs/old-name.md.
        (plan_dir / "00-overview.md").write_text(
            _make_overview([("alpha", "01-alpha.md"), ("beta", "02-beta.md")]),
            encoding="utf-8",
        )
        (plan_dir / "01-alpha.md").write_text(
            _make_batch_with_context_and_moves("alpha", context=["docs/old-name.md"]),
            encoding="utf-8",
        )
        # Batch B ("beta"), later in the plan and depending on alpha, relocates the exact path alpha's Context: still references.
        (plan_dir / "02-beta.md").write_text(
            _make_batch_with_context_and_moves(
                "beta", moves=[("docs/old-name.md", "docs/new-name.md")]
            ),
            encoding="utf-8",
        )
        # Post-implementation disk state: the move landed -- target present, source absent -- so alpha's stale Context: ref cannot resolve to a file on disk and must fall back to deletes_union-style suppression.
        (project_root / "docs").mkdir(parents=True)
        (project_root / "docs" / "new-name.md").write_text("# relocated\n", encoding="utf-8")

        cfg23 = {
            "paths": {
                "discussion_file": "discussion.md",
                "plan_dir":        "plan/",
                "reviews_dir":     "reviews/",
            },
            "llm": {"bulk_timeout": None, "holistic_timeout": None},
            "roles": {
                "code-review": {
                    "batch":   {"rounds": 3, "reviewer": "test_stub"},
                    "holistic": {"rounds": 3, "reviewer": "test_stub"},
                },
            },
        }
        _test_registry.write_to(wiki_root)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        _seed_approve(1)
        try:
            r = code_run(cfg23, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, batch_name="alpha")
            assert r.verdict == "APPROVE", f"expected APPROVE, got {r.verdict}"
            prompts = stub.captured_prompts()
            assert prompts, "expected at least one captured prompt"
            first_prompt = prompts[0][0]
            # File-content delimiters bulk the *resolved absolute* path, not the raw plan-relative token.
            # docs/old-name.md still appears as literal text inside beta's own bulked batch-file content (its Moves: declaration names both sides of the relocation) -- that is expected and not what this assertion is about.
            # What must NOT happen is a bulked "file contents" delimiter for the moved-away source, which is what resolve_ref_paths would have produced had it not suppressed the stale ref (and what a hard-fail ReviewError would have pre-empted entirely before any prompt was ever built).
            old_path = project_root / "docs" / "old-name.md"
            new_path = project_root / "docs" / "new-name.md"
            assert f"--- FILE: {old_path} ---" not in first_prompt, (
                "moved-away source path must be suppressed from the resolved "
                "source-file list, not bulked in as its own FILE section"
            )
            assert f"--- FILE: {new_path} ---" in first_prompt, (
                "move target should still be resolved onto disk and bulked normally"
            )
            print("PASS test23: Moves: source suppresses a stale cross-batch Context: ref (#686)")
        except ReviewError as exc:
            errors += 1
            print(f"FAIL test23: prepare() raised ReviewError instead of suppressing: {exc}", file=sys.stderr)
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test23: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test23 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 24 — code stage's default blocking_classes is the full class set, so every classed
    # BLOCKING heading survives the ceiling as BLOCKING with no demotion (Card 18, check 1).
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        mill_dir, wiki_root, project_root, cfg = _make_fixture(tmpdir)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            classed_text = (
                "# Review: test\n\n"
                "### [BLOCKING:design] missing decision\n\n- b\n\n"
                "### [BLOCKING:scope] incomplete inventory\n\n- b\n\n"
                "### [BLOCKING:decision] undisposed artifact\n\n- b\n\n"
                "### [BLOCKING:consistency] contradicts convention\n\n- b\n\n"
                "```yaml\nverdict: REQUEST_CHANGES\n```\n"
            )
            stub.seed([(classed_text, "sid-classed")])
            r = code_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, batch_name="alpha")
            assert r.verdict == "REQUEST_CHANGES", f"expected REQUEST_CHANGES, got {r.verdict}"
            assert r.blocking_count == 4, f"expected blocking_count=4, got {r.blocking_count}"
            assert len(r.findings) == 4, f"expected 4 findings, got {len(r.findings)}"
            for finding in r.findings:
                assert finding["severity"] == "BLOCKING", (
                    f"expected every finding to stay BLOCKING at the code stage, got {finding}"
                )
                assert finding["demoted"] is False, (
                    f"code stage's default blocking_classes is the full class set -- no finding "
                    f"should be demoted, got {finding}"
                )
            print(
                "PASS test24: all four classed BLOCKING headings survive at the code stage "
                "(demotion-free ceiling, Card 18)"
            )
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test24: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test24 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 25 — advisory rename-check NITs spliced by _splice_rename_nit_findings appear in the
    # finalize envelope's findings list, confirming the splice happens before extraction (Card 18,
    # check 2).
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        mill_dir, wiki_root, project_root, cfg = _make_fixture(tmpdir)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            plan_dir = project_root / "plan"

            def _make_batch_with_moves_for_splice(name: str, moves: list[tuple[str, str]]) -> str:
                """Return minimal batch file text with a Moves: field."""
                moves_lines = "\n".join(f"  - `{s}` -> `{d}`" for s, d in moves)
                return (
                    f"# Batch: {name}\n\n"
                    "```yaml\n"
                    f"task: test\nbatch: {name}\ncards: 1\nverify: null\ndepends-on: []\n"
                    "```\n\n"
                    "## Cards\n\n### Card 1\n\n"
                    "- **Context:** none\n"
                    "- **Edits:** none\n"
                    "- **Creates:** none\n"
                    "- **Deletes:** none\n"
                    f"- **Moves:**\n{moves_lines}\n"
                )

            (plan_dir / "01-alpha.md").write_text(
                _make_batch_with_moves_for_splice(
                    "alpha", [("old/module.py", "new/module.py")]
                ),
                encoding="utf-8",
            )

            fake_start_sha = "aabbccdd1234567890abcdef1234567890abcdef"
            mill_state_dir = project_root / "_mill"
            mill_state_dir.mkdir(parents=True, exist_ok=True)
            (mill_state_dir / "status.md").write_text(
                "# Status: test-slug\n\n"
                "```yaml\n"
                "phase: implement\n"
                "```\n\n"
                "## Batches\n\n"
                "```yaml\n"
                f"batches:\n  - name: alpha\n    start_sha: {fake_start_sha}\n"
                "```\n",
                encoding="utf-8",
            )

            add_delete_diff = "A\tnew/module.py\nD\told/module.py\n"
            fake_completed = subprocess.CompletedProcess(
                args=[], returncode=0, stdout=add_delete_diff, stderr=""
            )

            reviews_dir = project_root / "reviews"
            reviews_dir.mkdir(parents=True, exist_ok=True)

            approve_raw = (
                "# Review: test\n\n"
                "```yaml\nverdict: APPROVE\n```\n\n"
                "## Findings\n\n(none)\n\n"
                "## Verdict\n\nAPPROVE\n"
            )

            with unittest.mock.patch("_subprocess_util.run", return_value=fake_completed):
                result = code_finalize(
                    cfg,
                    SLUG,
                    approve_raw,
                    scope="alpha",
                    round_n=1,
                    reviews_dir=reviews_dir,
                    mill_dir=mill_dir,
                    project_root=project_root,
                    wiki_root=wiki_root,
                    git_root=project_root,
                )

            assert result.verdict == "APPROVE", (
                f"advisory rename NIT must not change verdict from APPROVE, got {result.verdict!r}"
            )
            assert len(result.findings) == 1, (
                f"expected the spliced NIT to appear once in the envelope's findings list, "
                f"got {result.findings}"
            )
            spliced_finding = result.findings[0]
            assert spliced_finding["severity"] == "NIT", (
                f"expected the spliced finding's severity to be NIT, got {spliced_finding}"
            )
            assert "old/module.py" in spliced_finding["title"] and "new/module.py" in spliced_finding["title"], (
                f"expected the spliced finding's title to reference both move-pair paths, "
                f"got {spliced_finding['title']!r}"
            )
            assert result.reviews[0]["findings"] == result.findings, (
                "per-scope reviews[] findings must match the top-level findings list"
            )
            print(
                "PASS test25: rename-check advisory NIT spliced before extraction appears in "
                "finalize envelope's findings list (Card 18)"
            )
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test25: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test25 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 26 — cost metadata happy path: reviews[0] carries duration_s/tool_calls/cost_usd
    # and the written file's yaml header has an injected duration_s: line.
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        mill_dir, wiki_root, project_root, cfg = _make_fixture(tmpdir)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            stub.seed([(APPROVE_TEXT, "sid-cost-happy")])
            r = code_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, batch_name="alpha")
            assert r.verdict == "APPROVE", f"expected APPROVE, got {r.verdict}"
            entry = r.reviews[0]
            # The stub's ReviewerCallResult carries duration_s=0.0 (a real in-process call
            # that took no measurable time) and tool_calls/cost_usd=None (unsupported signals).
            assert entry["duration_s"] == 0.0, f"expected duration_s=0.0, got {entry['duration_s']!r}"
            assert entry["tool_calls"] is None, f"expected tool_calls=None, got {entry['tool_calls']!r}"
            assert entry["cost_usd"] is None, f"expected cost_usd=None, got {entry['cost_usd']!r}"
            file_text = Path(entry["file"]).read_text(encoding="utf-8")
            assert "duration_s:" in file_text, (
                f"expected 'duration_s:' line in written review file, got:\n{file_text}"
            )
            print(
                "PASS test26: cost metadata happy path -- reviews[0] carries duration_s/"
                "tool_calls/cost_usd and the written file's yaml header carries duration_s:"
            )
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test26: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test26 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 27 — cost metadata summation: NEED_CONTEXT retry -> final entry carries the sum
    # of both calls' duration_s/tool_calls/cost_usd, not just the retry's values.
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        mill_dir, wiki_root, project_root, cfg = _make_fixture(tmpdir)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        original_run = stub.run
        call_count = 0

        def _seq_summation(prompt_text, **kw):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ReviewerCallResult(
                    text=NEED_CONTEXT_TEXT, session_id="sid-1",
                    duration_s=10.0, tool_calls=2, cost_usd=0.01,
                )
            return ReviewerCallResult(
                text=APPROVE_TEXT, session_id="sid-2",
                duration_s=5.0, tool_calls=3, cost_usd=0.02,
            )

        stub.run = _seq_summation
        stub.seed([])  # clear prompts log
        try:
            r = code_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, batch_name="alpha")
            assert r.verdict == "APPROVE", f"expected APPROVE after retry, got {r.verdict}"
            entry = r.reviews[0]
            assert entry["duration_s"] == 15.0, f"expected summed duration_s=15.0, got {entry['duration_s']!r}"
            assert entry["tool_calls"] == 5, f"expected summed tool_calls=5, got {entry['tool_calls']!r}"
            assert abs(entry["cost_usd"] - 0.03) < 1e-9, (
                f"expected summed cost_usd~=0.03, got {entry['cost_usd']!r}"
            )
            print(
                "PASS test27: NEED_CONTEXT retry summation -- final entry carries the sum "
                "of both calls, not just the retry's values"
            )
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test27: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test27 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            stub.run = original_run
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 28 — cost metadata None-absorbing: retry's tool_calls/cost_usd are None ->
    # the first call's values survive rather than being zeroed or dropped.
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        mill_dir, wiki_root, project_root, cfg = _make_fixture(tmpdir)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        original_run = stub.run
        call_count = 0

        def _seq_none_absorbing(prompt_text, **kw):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ReviewerCallResult(
                    text=NEED_CONTEXT_TEXT, session_id="sid-1",
                    duration_s=10.0, tool_calls=2, cost_usd=0.01,
                )
            return ReviewerCallResult(
                text=APPROVE_TEXT, session_id="sid-2",
                duration_s=5.0, tool_calls=None, cost_usd=None,
            )

        stub.run = _seq_none_absorbing
        stub.seed([])  # clear prompts log
        try:
            r = code_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, batch_name="alpha")
            assert r.verdict == "APPROVE", f"expected APPROVE after retry, got {r.verdict}"
            entry = r.reviews[0]
            assert entry["duration_s"] == 15.0, f"expected summed duration_s=15.0, got {entry['duration_s']!r}"
            assert entry["tool_calls"] == 2, (
                f"expected first call's tool_calls=2 to survive the None-absorbing sum, "
                f"got {entry['tool_calls']!r}"
            )
            assert entry["cost_usd"] == 0.01, (
                f"expected first call's cost_usd=0.01 to survive the None-absorbing sum, "
                f"got {entry['cost_usd']!r}"
            )
            print(
                "PASS test28: None-absorbing summation -- first call's tool_calls/cost_usd "
                "survive a retry that reports None for those signals"
            )
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test28: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test28 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            stub.run = original_run
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 29 — cost metadata call-failure ERROR: LLMError's duration_s surfaces on the
    # initial call, file stays None (call never returned).
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        mill_dir, wiki_root, project_root, cfg = _make_fixture(tmpdir)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        original_run = stub.run

        def _raise_with_duration(prompt_text, **kw):
            raise LLMError("seeded boom", duration_s=12.5)

        stub.run = _raise_with_duration
        stub.seed([])  # clear prompts log
        try:
            r = code_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, batch_name="alpha")
            assert r.verdict == "ERROR", f"expected ERROR, got {r.verdict}"
            entry = r.reviews[0]
            assert entry["duration_s"] == 12.5, f"expected duration_s=12.5, got {entry['duration_s']!r}"
            assert entry["tool_calls"] is None, f"expected tool_calls=None, got {entry['tool_calls']!r}"
            assert entry["cost_usd"] is None, f"expected cost_usd=None, got {entry['cost_usd']!r}"
            assert entry["file"] is None, f"expected file=None, got {entry['file']!r}"
            print(
                "PASS test29: cost metadata call-failure ERROR -- LLMError.duration_s "
                "surfaces on the synthetic ERROR entry with file=None"
            )
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test29: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test29 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            stub.run = original_run
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 30 — cost metadata retry call-failure ERROR: a successful first call plus an
    # LLMError on the retry -> the entry's duration_s is the sum of both.
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        mill_dir, wiki_root, project_root, cfg = _make_fixture(tmpdir)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        original_run = stub.run
        call_count = 0

        def _seq_retry_failure(prompt_text, **kw):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ReviewerCallResult(
                    text=NEED_CONTEXT_TEXT, session_id="sid-1",
                    duration_s=10.0, tool_calls=2, cost_usd=0.01,
                )
            raise LLMError("retry boom", duration_s=4.0)

        stub.run = _seq_retry_failure
        stub.seed([])  # clear prompts log
        try:
            r = code_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, batch_name="alpha")
            assert r.verdict == "ERROR", f"expected ERROR, got {r.verdict}"
            entry = r.reviews[0]
            assert entry["duration_s"] == 14.0, (
                f"expected duration_s=14.0 (10.0 first call + 4.0 retry), got {entry['duration_s']!r}"
            )
            assert entry["tool_calls"] == 2, f"expected first call's tool_calls=2, got {entry['tool_calls']!r}"
            assert entry["cost_usd"] == 0.01, f"expected first call's cost_usd=0.01, got {entry['cost_usd']!r}"
            assert entry["file"] is None, f"expected file=None, got {entry['file']!r}"
            print(
                "PASS test30: retry call-failure ERROR -- duration_s is the sum of the "
                "first call and the failed retry"
            )
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test30: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test30 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            stub.run = original_run
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # Test 31 — cost metadata parse-failure ERROR: parse_verdict rejects the text -> the
    # entry carries the call's metrics AND the raw file written by that branch has
    # duration_s: injected into its header.
    # ------------------------------------------------------------------
    with _test_helpers.safe_temp_dir() as tmpdir:
        mill_dir, wiki_root, project_root, cfg = _make_fixture(tmpdir)
        orig_dir = os.getcwd()
        os.chdir(project_root)
        original_run = stub.run
        unparseable_with_fence = "# Review\n\n```yaml\nnot_a_verdict: true\n```\n"

        def _return_unparseable(prompt_text, **kw):
            return ReviewerCallResult(
                text=unparseable_with_fence, session_id="sid-parse-fail",
                duration_s=7.25, tool_calls=3, cost_usd=0.0123,
            )

        stub.run = _return_unparseable
        stub.seed([])  # clear prompts log
        try:
            r = code_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, batch_name="alpha")
            assert r.verdict == "ERROR", f"expected ERROR, got {r.verdict}"
            entry = r.reviews[0]
            assert entry["duration_s"] == 7.25, f"expected duration_s=7.25, got {entry['duration_s']!r}"
            assert entry["tool_calls"] == 3, f"expected tool_calls=3, got {entry['tool_calls']!r}"
            assert entry["cost_usd"] == 0.0123, f"expected cost_usd=0.0123, got {entry['cost_usd']!r}"
            assert entry["file"] is not None, "expected a written raw file, got file=None"
            file_text = Path(entry["file"]).read_text(encoding="utf-8")
            assert "duration_s: 7.2" in file_text, (
                f"expected injected 'duration_s:' line in raw file, got:\n{file_text}"
            )
            print(
                "PASS test31: parse-failure ERROR -- metrics survive into both the ERROR "
                "entry and the raw file's injected yaml header"
            )
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test31: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test31 (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            stub.run = original_run
            os.chdir(orig_dir)

    # ------------------------------------------------------------------
    # project_root rebind: briefs_dir resolves under resolve_active_hub, not resolve_hub_path's decoy (#675)
    # ------------------------------------------------------------------
    errors += test_project_root_rebind_uses_resolve_active_hub_not_resolve_hub_path()

    # ------------------------------------------------------------------
    # Context: soft-fail gitignore path -- a missing but confirmed git-ignored Context: ref degrades to a warning instead of a hard ReviewError (#733).
    # ------------------------------------------------------------------
    errors += test_context_only_gitignored_ref_soft_fails_prepare()

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All _review_code flow tests passed.")
    return 0


def test_project_root_rebind_uses_resolve_active_hub_not_resolve_hub_path() -> int:
    """project_root rebinds to resolve_active_hub's value, not resolve_hub_path's decoy.

    millpy-review-code.py's main() imports every module it needs (_agent_dispatch, _paths,
    _reviewers, _review_cli, _review_common, _review_code) inline, so this test loads the CLI script
    via importlib.util.spec_from_file_location and injects MagicMock stand-ins for each of those
    names into sys.modules before exec_module, exactly as test-review-discussion-flow.py's
    test_brief_path_nested_layout does.

    resolve_hub_path returns a decoy directory standing in for a stale/escaped resolve_hub_path()
    fallback;
    resolve_active_hub -- called after slug resolution, per the Card 13 rebind -- returns a distinct
    directory standing in for the corrected active task worktree.
    briefs_dir (surfaced via --stage prepare's brief_path in the printed envelope, and via the
    recorded resolve_task_path/write_brief call args) must resolve under the resolve_active_hub
    value, proving project_root was rebound and not left at resolve_hub_path's original value.

    A reversion of the Card 13 fix (never calling resolve_active_hub) causes the assertion to fail
    because resolve_task_path is called with the decoy directory instead.

    Returns 0 on success, 1 on failure (matching the errors-accumulator convention used throughout
    this file).
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
        mock_review_common.resolve_path.return_value = decoy_dir / "reviews"
        mock_review_common.ReviewError = Exception

        mock_review_code = MagicMock()
        mock_review_code.prepare.return_value = {
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

        injected_modules = {
            "_paths": mock_paths,
            "_review_common": mock_review_common,
            "_review_code": mock_review_code,
            "_agent_dispatch": mock_agent_dispatch,
            "_reviewers": mock_reviewers,
            "_review_cli": mock_review_cli,
        }

        with patch.dict(sys.modules, injected_modules):
            spec = importlib.util.spec_from_file_location(
                "millpy_review_code",
                scripts_dir / "millpy-review-code.py",
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            with patch("sys.argv", ["prog", "--stage", "prepare"]):
                try:
                    mod.main()
                except (TypeError, SystemExit, Exception):
                    # The resolve_active_hub/resolve_task_path calls are already recorded before any crash on a bare MagicMock field reaching json.dumps(envelope).
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

        # write_brief's own briefs_dir argument must agree.
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
            "PASS: code-review briefs_dir resolves under resolve_active_hub's value,"
            " not resolve_hub_path's decoy"
        )
        return 0


def test_context_only_gitignored_ref_soft_fails_prepare() -> int:
    """Context:-only refs confirmed git-ignored soft-fail prepare() instead of hard-failing (#733).

    Scenario (a): alpha's Context: field gains a missing ref (.scratch/probe.md) covered by an
    appended .gitignore rule.
    prepare() must not raise ReviewError,
    and the soft-skipped ref must not surface as its own bulked "--- FILE: ... ---" section in the
    rendered prompt_text (mirrors the moved-away-source assertion in test23 above -- a missing file
    is never bulked in regardless of soft-fail vs hard-fail, so the real assertion of interest is
    that prepare() completes at all).

    Scenario (b) is a regression guard, run in the same fixture shape: a DIFFERENT missing ref NOT
    covered by the .gitignore must still hard-fail prepare() with ReviewError -- soft-fail only
    fires on a confirmed git-ignore hit, exactly as resolve_ref_paths's own unit coverage in
    test-review-common.py.

    Returns 0 on success, 1 on failure (errors-accumulator convention used throughout this file).
    """
    errors = 0

    # Scenario (a): git-ignored missing Context: ref soft-fails prepare().
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_path = Path(tmpdir)
        mill_dir, wiki_root, project_root, cfg = _make_fixture(tmp_path)
        plan_dir = project_root / "plan"
        gitignore_path = project_root / ".gitignore"
        gitignore_path.write_text(
            gitignore_path.read_text(encoding="utf-8") + ".scratch/probe.md\n",
            encoding="utf-8",
        )
        alpha_path = plan_dir / "01-alpha.md"
        alpha_path.write_text(
            alpha_path.read_text(encoding="utf-8").replace(
                "- **Context:** `src/a.py`\n",
                "- **Context:** `src/a.py`, `.scratch/probe.md`\n",
            ),
            encoding="utf-8",
        )
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            result = prepare(
                cfg, SLUG, scope="alpha", mill_dir=mill_dir,
                project_root=project_root, wiki_root=wiki_root, git_root=project_root,
            )
            missing_ref = project_root / ".scratch" / "probe.md"
            assert f"--- FILE: {missing_ref} ---" not in result["prompt_text"], (
                "soft-skipped git-ignored Context: ref must not surface as its own"
                " bulked FILE section"
            )
            print(
                "PASS: test_context_only_gitignored_ref_soft_fails_prepare (a): "
                "git-ignored missing Context: ref soft-skipped, prepare() did not raise"
            )
        except AssertionError as exc:
            errors += 1
            print(
                f"FAIL test_context_only_gitignored_ref_soft_fails_prepare (a): {exc}",
                file=sys.stderr,
            )
        except Exception as exc:
            errors += 1
            print(
                f"FAIL test_context_only_gitignored_ref_soft_fails_prepare (a): prepare()"
                f" raised {type(exc).__name__} instead of soft-skipping: {exc}",
                file=sys.stderr,
            )
        finally:
            os.chdir(orig_dir)

    # Scenario (b): a DIFFERENT missing ref NOT covered by .gitignore still hard-fails.
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_path = Path(tmpdir)
        mill_dir, wiki_root, project_root, cfg = _make_fixture(tmp_path)
        plan_dir = project_root / "plan"
        gitignore_path = project_root / ".gitignore"
        gitignore_path.write_text(
            gitignore_path.read_text(encoding="utf-8") + ".scratch/probe.md\n",
            encoding="utf-8",
        )
        alpha_path = plan_dir / "01-alpha.md"
        alpha_path.write_text(
            alpha_path.read_text(encoding="utf-8").replace(
                "- **Context:** `src/a.py`\n",
                "- **Context:** `src/a.py`, `not_ignored_missing.py`\n",
            ),
            encoding="utf-8",
        )
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            prepare(
                cfg, SLUG, scope="alpha", mill_dir=mill_dir,
                project_root=project_root, wiki_root=wiki_root, git_root=project_root,
            )
            errors += 1
            print(
                "FAIL test_context_only_gitignored_ref_soft_fails_prepare (b): expected"
                " ReviewError for a missing, non-ignored Context: ref",
                file=sys.stderr,
            )
        except ReviewError:
            print(
                "PASS: test_context_only_gitignored_ref_soft_fails_prepare (b): missing,"
                " non-ignored Context: ref still hard-fails prepare()"
            )
        except AssertionError:
            raise
        except Exception as exc:
            errors += 1
            print(
                f"FAIL test_context_only_gitignored_ref_soft_fails_prepare (b): unexpected"
                f" {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
        finally:
            os.chdir(orig_dir)

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
