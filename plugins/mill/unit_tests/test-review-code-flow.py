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

import _active  # noqa: E402
import _reviewer_test_stub as stub  # noqa: E402
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
            "discussion_file": f"active/{SLUG}/discussion.md",
            "plan_dir":        f"active/{SLUG}/plan/",
            "reviews_dir":     f"active/{SLUG}/reviews/",
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
        mill_dir = worktree / ".millhouse"
        wiki_root = Path(tmpdir) / "wiki"
        project_root = worktree
        _active.write(
            mill_dir,
            slug=SLUG, task_title="Test", branch="test",
            spawned_at="2026-01-01T00:00:00Z",
        )
        plan_dir = worktree / "active" / SLUG / "plan"
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
                "discussion_file": f"active/{SLUG}/discussion.md",
                "plan_dir":        f"active/{SLUG}/plan/",
                "reviews_dir":     f"active/{SLUG}/reviews/",
            },
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
        mill_dir = worktree / ".millhouse"
        wiki_root = Path(tmpdir) / "wiki"
        project_root = worktree
        _active.write(
            mill_dir,
            slug=SLUG, task_title="Test", branch="test",
            spawned_at="2026-01-01T00:00:00Z",
        )
        plan_dir = worktree / "active" / SLUG / "plan"
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
                "discussion_file": f"active/{SLUG}/discussion.md",
                "plan_dir":        f"active/{SLUG}/plan/",
                "reviews_dir":     f"active/{SLUG}/reviews/",
            },
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
            assert retry_kwargs == {"session_id": "sid-1", "resume": True}, (
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

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All _review_code flow tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
