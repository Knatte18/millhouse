"""Unit-test flow harness for _review_code.run.

Uses _reviewer_test_stub as the reviewer backend. All tests run in-process
with no real LLM, no network calls. Covers the bugs fixed in batches 01-05:
  - Per-scope round counter (#21/#62/#63)
  - Manifest presence in prompts (#5/#7 prevention)
  - creates_union suppression (#60)
  - Hard-fail on missing refs (#41/#43)
  - NEED_CONTEXT resume fallback (#5/#7 recovery)
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
from _review_code import run as code_run  # noqa: E402
from _review_common import ReviewError  # noqa: E402

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
    project_root is the worktree path; callers must os.chdir(project_root).
    alpha Reads src/a.py; beta Reads src/b.py; gamma Reads src/c.py.
    All three source files are created on disk.
    """
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

    cfg = {
        "paths": {
            "discussion_file": "discussion.md",
            "plan_dir":        "plan/",
            "reviews_dir":     "reviews/",
        },
        "llm": {
            "bulk_timeout":     None,
            "holistic_timeout": None,
        },
        "review": {
            "code": {
                "rounds": 3,
                "reviewer": "test_stub",
                "self_fix_rounds": 0,
                "holistic": True,
            },
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
    # Test 1 — per-scope round counter on sequential per-batch calls
    # Regression pin for #21/#62/#63: holistic must start at r1 even after
    # multiple per-batch rounds have been recorded.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        mill_dir, wiki_root, project_root, cfg = _make_fixture(Path(tmpdir))
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            # alpha round 1
            _seed_approve(1)
            r = code_run(cfg, SLUG, mill_dir, wiki_root, project_root, batch_name="alpha")
            assert r.round == 1, f"expected round 1, got {r.round}"
            assert r.verdict == "APPROVE"
            fname = Path(r.reviews[0]["file"]).name
            assert "code-review-alpha-r1" in fname, f"unexpected filename: {fname}"
            assert str(project_root / "reviews") in r.reviews[0]["file"], (
                f"review file must be under worktree/reviews/, got {r.reviews[0]['file']!r}"
            )
            print(f"PASS test1a: alpha r1 → {fname}")

            # alpha round 2 (counter increments per-scope)
            _seed_approve(1)
            r = code_run(cfg, SLUG, mill_dir, wiki_root, project_root, batch_name="alpha")
            assert r.round == 2, f"expected round 2, got {r.round}"
            fname = Path(r.reviews[0]["file"]).name
            assert "code-review-alpha-r2" in fname, f"unexpected filename: {fname}"
            print(f"PASS test1b: alpha r2 → {fname}")

            # beta round 1 (fresh per-scope counter, not r3)
            _seed_approve(1)
            r = code_run(cfg, SLUG, mill_dir, wiki_root, project_root, batch_name="beta")
            assert r.round == 1, f"expected round 1 for beta, got {r.round}"
            fname = Path(r.reviews[0]["file"]).name
            assert "code-review-beta-r1" in fname, f"unexpected filename: {fname}"
            print(f"PASS test1c: beta r1 (independent of alpha counter) → {fname}")

            # holistic round 1 (independent of both per-batch counters)
            _seed_approve(1)
            r = code_run(cfg, SLUG, mill_dir, wiki_root, project_root, batch_name=None)
            assert r.round == 1, f"expected holistic round 1, got {r.round}"
            fname = Path(r.reviews[0]["file"]).name
            assert "code-review-r1" in fname, f"unexpected holistic filename: {fname}"
            assert "alpha" not in fname and "beta" not in fname, (
                f"batch name leaked into holistic filename: {fname}"
            )
            print(f"PASS test1d: holistic r1 (per-scope regression #21/#62/#63) → {fname}")
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
    with tempfile.TemporaryDirectory() as tmpdir:
        mill_dir, wiki_root, project_root, cfg = _make_fixture(Path(tmpdir))
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            _seed_approve(1)
            code_run(cfg, SLUG, mill_dir, wiki_root, project_root, batch_name=None)
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
    # Test 3 — creates_union suppression
    # A batch's Reads: path that is in another batch's Creates: must not
    # raise ReviewError even when the file doesn't exist on disk (#60).
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        worktree = Path(tmpdir) / "container" / "wts" / SLUG
        worktree.mkdir(parents=True)
        subprocess.run(["git", "-C", str(worktree), "init"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(worktree), "checkout", "-b", f"hanf/{SLUG}"], capture_output=True)
        mill_dir = worktree / ".millhouse"
        mill_dir.mkdir(parents=True, exist_ok=True)
        wiki_root = Path(tmpdir) / "wiki"
        wiki_root.mkdir(parents=True, exist_ok=True)
        (wiki_root / "config.yaml").write_text(
            "paths:\n  discussion_file: discussion.md\n  plan_dir: plan/\n  reviews_dir: reviews/\n"
            "spawn:\n  branch_prefix: \"hanf/\"\n", encoding="utf-8",
        )
        (wiki_root / "Home.md").write_text(f"## Test Task\n[[{SLUG}]] [active]\n\n_body_\n", encoding="utf-8")
        (mill_dir / "config.local.yaml").write_text(
            f"paths:\n  wiki: '{wiki_root.as_posix()}'\n", encoding="utf-8"
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
            "review": {
                "code": {"rounds": 3, "reviewer": "test_stub", "self_fix_rounds": 0, "holistic": True},
            },
        }
        orig_dir = os.getcwd()
        os.chdir(project_root)
        _seed_approve(1)
        try:
            r = code_run(cfg3, SLUG, mill_dir, wiki_root, project_root, batch_name="beta")
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
    with tempfile.TemporaryDirectory() as tmpdir:
        worktree = Path(tmpdir) / "container" / "wts" / SLUG
        worktree.mkdir(parents=True)
        subprocess.run(["git", "-C", str(worktree), "init"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(worktree), "checkout", "-b", f"hanf/{SLUG}"], capture_output=True)
        mill_dir = worktree / ".millhouse"
        mill_dir.mkdir(parents=True, exist_ok=True)
        wiki_root = Path(tmpdir) / "wiki"
        wiki_root.mkdir(parents=True, exist_ok=True)
        (wiki_root / "config.yaml").write_text(
            "paths:\n  discussion_file: discussion.md\n  plan_dir: plan/\n  reviews_dir: reviews/\n"
            "spawn:\n  branch_prefix: \"hanf/\"\n", encoding="utf-8",
        )
        (wiki_root / "Home.md").write_text(f"## Test Task\n[[{SLUG}]] [active]\n\n_body_\n", encoding="utf-8")
        (mill_dir / "config.local.yaml").write_text(
            f"paths:\n  wiki: '{wiki_root.as_posix()}'\n", encoding="utf-8"
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
            "review": {
                "code": {"rounds": 3, "reviewer": "test_stub", "self_fix_rounds": 0, "holistic": True},
            },
        }
        orig_dir = os.getcwd()
        os.chdir(project_root)
        _seed_approve(1)
        try:
            code_run(cfg4, SLUG, mill_dir, wiki_root, project_root, batch_name="alpha")
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
    # Test 5 — NEED_CONTEXT resume fallback: 1 retry → APPROVE (#5/#7)
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        mill_dir, wiki_root, project_root, cfg = _make_fixture(Path(tmpdir))
        orig_dir = os.getcwd()
        os.chdir(project_root)
        # src/a.py exists on disk (created by _make_fixture); NEED_CONTEXT_TEXT
        # claims it is missing so resolve_existing_paths returns it → retry fires.
        stub.seed([
            (NEED_CONTEXT_TEXT, "sid-1"),
            (APPROVE_TEXT,      "sid-2"),
        ])
        try:
            r = code_run(cfg, SLUG, mill_dir, wiki_root, project_root, batch_name="alpha")
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
            print("PASS test5: NEED_CONTEXT retry → APPROVE, session_id from retry captured")
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
    with tempfile.TemporaryDirectory() as tmpdir:
        mill_dir, wiki_root, project_root, cfg = _make_fixture(Path(tmpdir))
        orig_dir = os.getcwd()
        os.chdir(project_root)
        stub.seed([
            (NEED_CONTEXT_TEXT, "sid-1"),
            (NEED_CONTEXT_TEXT, "sid-2"),
        ])
        try:
            r = code_run(cfg, SLUG, mill_dir, wiki_root, project_root, batch_name="alpha")
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
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir) / "container" / "wts" / SLUG
        project_root.mkdir(parents=True)
        subprocess.run(["git", "-C", str(project_root), "init"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(project_root), "checkout", "-b", f"hanf/{SLUG}"], capture_output=True)
        wiki_root = Path(tmpdir) / "wiki"
        wiki_root.mkdir(parents=True, exist_ok=True)
        (wiki_root / "config.yaml").write_text(
            "paths:\n  discussion_file: discussion.md\n  plan_dir: plan/\n  reviews_dir: reviews/\n"
            "spawn:\n  branch_prefix: \"hanf/\"\n", encoding="utf-8",
        )
        (wiki_root / "Home.md").write_text(f"## Test Task\n[[{SLUG}]] [active]\n\n_body_\n", encoding="utf-8")
        mill_dir = project_root / ".millhouse"
        mill_dir.mkdir(parents=True, exist_ok=True)
        (mill_dir / "config.local.yaml").write_text(
            f"paths:\n  wiki: '{wiki_root.as_posix()}'\n", encoding="utf-8"
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
            "review": {
                "code": {"rounds": 3, "reviewer": "test_stub", "self_fix_rounds": 0, "holistic": True},
            },
        }

        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            # Pre-populate 3 review files for batch "foo"
            _seed_approve(3)
            code_run(cfg7, SLUG, mill_dir, wiki_root, project_root, batch_name="foo")
            code_run(cfg7, SLUG, mill_dir, wiki_root, project_root, batch_name="foo")
            code_run(cfg7, SLUG, mill_dir, wiki_root, project_root, batch_name="foo")

            # Round 4 without kwarg: cfg.rounds == 3 → ReviewError
            try:
                _seed_approve(1)
                code_run(cfg7, SLUG, mill_dir, wiki_root, project_root, batch_name="foo")
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
            r4 = code_run(cfg7, SLUG, mill_dir, wiki_root, project_root, batch_name="foo", max_rounds=5)
            assert r4.round == 4, f"expected round 4, got {r4.round}"
            fname4 = Path(r4.reviews[0]["file"]).name
            assert "code-review-foo-r4" in fname4, f"unexpected filename: {fname4}"
            print(f"PASS test7b: round 4 succeeds with max_rounds=5 → {fname4}")

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
    with tempfile.TemporaryDirectory() as tmpdir:
        mill_dir, wiki_root, project_root, cfg = _make_fixture(Path(tmpdir))
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
            r = code_run(cfg, SLUG, mill_dir, wiki_root, project_root, batch_name="alpha")
            assert r.blocking_count == 3, f"expected blocking_count=3, got {r.blocking_count}"
            print("PASS test8a: three BLOCKING headings → blocking_count == 3")

            stub.seed([(APPROVE_TEXT, "sid-b2")])
            r2 = code_run(cfg, SLUG, mill_dir, wiki_root, project_root, batch_name="beta")
            assert r2.blocking_count == 0, f"expected blocking_count=0, got {r2.blocking_count}"
            print("PASS test8b: no BLOCKING headings → blocking_count == 0")

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
    with tempfile.TemporaryDirectory() as tmpdir:
        mill_dir, wiki_root, project_root, cfg = _make_fixture(Path(tmpdir))
        orig_dir = os.getcwd()
        os.chdir(project_root)
        original_run = stub.run
        def _raise_boom(prompt_text, **kw):
            raise LLMError("seeded boom")
        stub.run = _raise_boom
        stub.seed([])  # clear prompts log
        try:
            r = code_run(cfg, SLUG, mill_dir, wiki_root, project_root, batch_name="alpha")
            assert r.verdict == "REQUEST_CHANGES", f"expected REQUEST_CHANGES, got {r.verdict}"
            assert len(r.reviews) == 1
            rev = r.reviews[0]
            assert rev["verdict"] == "ERROR", f"expected ERROR entry, got {rev['verdict']}"
            assert rev["file"] is None, f"expected file=None, got {rev['file']}"
            assert "seeded boom" in rev["error"], f"error field wrong: {rev['error']}"
            assert rev["session_id"] is None
            print("PASS test9: initial LLM failure → ReviewResult(ERROR) not raise")
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
    with tempfile.TemporaryDirectory() as tmpdir:
        mill_dir, wiki_root, project_root, cfg = _make_fixture(Path(tmpdir))
        orig_dir = os.getcwd()
        os.chdir(project_root)
        original_run = stub.run
        def _raise_boom(prompt_text, **kw):
            raise LLMError("seeded boom")
        stub.run = _raise_boom
        stub.seed([])
        try:
            r = code_run(cfg, SLUG, mill_dir, wiki_root, project_root, batch_name=None)
            assert r.verdict == "REQUEST_CHANGES", f"expected REQUEST_CHANGES, got {r.verdict}"
            rev = r.reviews[0]
            assert rev["verdict"] == "ERROR"
            assert rev["scope"] == "holistic"
            assert "seeded boom" in rev["error"]
            print("PASS test10: holistic LLM failure → ReviewResult(ERROR) not raise")
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
    with tempfile.TemporaryDirectory() as tmpdir:
        mill_dir, wiki_root, project_root, cfg = _make_fixture(Path(tmpdir))
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
            r = code_run(cfg, SLUG, mill_dir, wiki_root, project_root, batch_name="alpha")
            assert r.verdict == "REQUEST_CHANGES", f"expected REQUEST_CHANGES, got {r.verdict}"
            rev = r.reviews[0]
            assert rev["verdict"] == "ERROR"
            assert rev["error"].startswith("resume retry failed:"), (
                f"error should start with 'resume retry failed:': {rev['error']}"
            )
            assert rev["session_id"] is None
            print("PASS test11: resume LLM failure → ERROR entry with 'resume retry failed:' prefix")
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
    with tempfile.TemporaryDirectory() as tmpdir:
        worktree = Path(tmpdir) / "container" / "wts" / SLUG
        worktree.mkdir(parents=True)
        subprocess.run(["git", "-C", str(worktree), "init"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(worktree), "checkout", "-b", f"hanf/{SLUG}"], capture_output=True)
        mill_dir = worktree / ".millhouse"
        mill_dir.mkdir(parents=True, exist_ok=True)
        wiki_root = Path(tmpdir) / "wiki"
        wiki_root.mkdir(parents=True, exist_ok=True)
        (wiki_root / "config.yaml").write_text(
            "paths:\n  discussion_file: discussion.md\n  plan_dir: plan/\n  reviews_dir: reviews/\n"
            "spawn:\n  branch_prefix: \"hanf/\"\n", encoding="utf-8",
        )
        (wiki_root / "Home.md").write_text(f"## Test Task\n[[{SLUG}]] [active]\n\n_body_\n", encoding="utf-8")
        (mill_dir / "config.local.yaml").write_text(
            f"paths:\n  wiki: '{wiki_root.as_posix()}'\n", encoding="utf-8"
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
            "review": {
                "code": {"rounds": 3, "reviewer": "test_stub", "self_fix_rounds": 0, "holistic": True},
            },
        }
        orig_dir = os.getcwd()
        os.chdir(project_root)
        _seed_approve(1)
        try:
            code_run(cfg12, SLUG, mill_dir, wiki_root, project_root, batch_name="alpha")
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
    with tempfile.TemporaryDirectory() as tmpdir:
        mill_dir, wiki_root, project_root, cfg = _make_fixture(Path(tmpdir))
        orig_dir = os.getcwd()
        os.chdir(project_root)
        cfg["llm"]["bulk_timeout"] = 900
        cfg["llm"]["holistic_timeout"] = 1800
        try:
            _seed_approve(1)
            code_run(cfg, SLUG, mill_dir, wiki_root, project_root, batch_name="alpha")
            prompts = stub.captured_prompts()
            assert prompts, "expected at least one captured prompt"
            _, kwargs = prompts[0]
            assert kwargs["timeout"] == 900, (
                f"per-batch call: expected timeout=900, got {kwargs['timeout']}"
            )
            print("PASS test13a: bulk_timeout=900 forwarded to reviewer for per-batch call")

            _seed_approve(1)
            code_run(cfg, SLUG, mill_dir, wiki_root, project_root, batch_name=None)
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
    # Test 14 — effort threading and diff-scoping
    # ------------------------------------------------------------------

    # 14a: holistic call passes holistic_effort='medium' to reviewer
    with tempfile.TemporaryDirectory() as tmpdir:
        mill_dir, wiki_root, project_root, cfg = _make_fixture(Path(tmpdir))
        cfg["review"]["code"]["holistic_effort"] = "medium"
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            _seed_approve(1)
            code_run(cfg, SLUG, mill_dir, wiki_root, project_root, batch_name=None)
            prompts = stub.captured_prompts()
            assert prompts, "expected at least one captured prompt"
            assert prompts[0][1]["effort"] == "medium", (
                f"expected effort='medium', got {prompts[0][1]['effort']!r}"
            )
            print("PASS test14a: holistic call passes holistic_effort='medium' to reviewer")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test14a: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test14a (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # 14b: per-batch call passes effort=None to reviewer
    with tempfile.TemporaryDirectory() as tmpdir:
        mill_dir, wiki_root, project_root, cfg = _make_fixture(Path(tmpdir))
        orig_dir = os.getcwd()
        os.chdir(project_root)
        try:
            _seed_approve(1)
            code_run(cfg, SLUG, mill_dir, wiki_root, project_root, batch_name="alpha")
            prompts = stub.captured_prompts()
            assert prompts, "expected at least one captured prompt"
            assert prompts[0][1]["effort"] is None, (
                f"expected effort=None for per-batch, got {prompts[0][1]['effort']!r}"
            )
            print("PASS test14b: per-batch call passes effort=None (no holistic_effort override)")
        except AssertionError as exc:
            errors += 1
            print(f"FAIL test14b: {exc}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"FAIL test14b (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        finally:
            os.chdir(orig_dir)

    # 14c: per-batch with start_sha present → prompt contains DIFF delimiter
    with tempfile.TemporaryDirectory() as tmpdir:
        mill_dir, wiki_root, project_root, cfg = _make_fixture(Path(tmpdir))
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
            code_run(cfg, SLUG, mill_dir, wiki_root, project_root, batch_name="alpha")
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

    # 14d: per-batch with missing start_sha → prompt uses FILE delimiter (no DIFF)
    with tempfile.TemporaryDirectory() as tmpdir:
        mill_dir, wiki_root, project_root, cfg = _make_fixture(Path(tmpdir))
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
            code_run(cfg, SLUG, mill_dir, wiki_root, project_root, batch_name="alpha")
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

    # 14e: per-batch with large diff → prompt uses FILE delimiter (not DIFF)
    with tempfile.TemporaryDirectory() as tmpdir:
        mill_dir, wiki_root, project_root, cfg = _make_fixture(Path(tmpdir))
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
            code_run(cfg, SLUG, mill_dir, wiki_root, project_root, batch_name="alpha")
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

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All _review_code flow tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
