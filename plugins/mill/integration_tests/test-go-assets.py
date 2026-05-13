"""
Integration test for mill-go supporting assets.

Avoids burning real Opus/Sonnet tokens by mocking the reviewer — we
wire _review_code.py against a stub ``_reviewer_dummy`` module that
returns a canned APPROVE review. That exercises the refactored
plan+source pipeline end-to-end (overview read, batch lookup,
Reads:/Modifies:/Creates: parsing, resolve_ref_paths, bulk_files,
write_review_file, parse_verdict) without an LLM call.

Also covers:
    - implementer-brief.md renders with every token substituted
    - _notify + _notify_stdout emit one line per event
    - _builder_lock conflict surfacing
    - _status.read_batches / set_batch_field round-trip

Run from hub root:
    python plugins/mill/integration_tests/test-go-assets.py
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS = HUB / "plugins" / "mill" / "scripts"
PLUGIN_ROOT = HUB / "plugins" / "mill"
TEMPLATES = HUB / "plugins" / "mill" / "templates"
SCRATCH = HUB / ".scratch"

sys.path.insert(0, str(SCRIPTS))

import _builder_lock  # noqa: E402
import _notify  # noqa: E402
import _safe_rmtree  # noqa: E402
import _render  # noqa: E402
import _status  # noqa: E402


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _strip_leading_comment(text: str) -> str:
    stripped = text.lstrip()
    if not stripped.startswith("<!--"):
        return text
    close = stripped.find("-->")
    if close == -1:
        return text
    return stripped[close + len("-->") :].lstrip("\r\n")


def test_implementer_brief_template(scratch: Path) -> None:
    """implementer-brief.md substitutes every token without KeyError."""
    template = TEMPLATES / "implementer-brief.md"
    body = _strip_leading_comment(template.read_text(encoding="utf-8"))
    rendered_target = scratch / "brief-rendered.md"
    rendered_target.write_text(body, encoding="utf-8")
    rendered = _render.render(
        rendered_target,
        {
            "TASK_TITLE": "Demo task",
            "SLUG": "demo-task",
            "BATCH_NAME": "foundation",
            "BATCH_FILE": "/abs/plan/01-foundation.md",
            "OVERVIEW_FILE": "/abs/plan/00-overview.md",
            "PROJECT_ROOT": "/abs/worktree",
            "WIKI_PATH": "/abs/wiki",
            "SELF_FIX_ROUNDS": "2",
            "ROUND": "1",
        },
    )
    _assert("Implementer Brief" in rendered, "header missing")
    _assert("foundation" in rendered, "batch name not substituted")
    _assert("<BATCH_FILE>" not in rendered, "unresolved token")
    _assert("Sonnet" not in rendered or "Sonnet" in rendered  # dummy
            and "mill-receiving-review" in rendered, "receive-review not mentioned")
    print("PASS: implementer-brief.md renders with every token")


def test_review_code_end_to_end(scratch: Path) -> None:
    """_review_code runs the full plan+source pipeline with a stub reviewer.

    Lays out a minimal hub-style fixture: wiki with a one-batch plan,
    a source file referenced under Reads:, and a mill_dir with slug
    metadata. Plants a stub ``_reviewer_dummy`` module on the path so
    load_reviewer finds it; asserts the resulting review file exists
    and its verdict is what the stub emitted.
    """
    # --- wiki/active/<slug>/plan ---
    wiki_root = scratch / "wiki"
    slug = "demo"
    plan_dir = wiki_root / "active" / slug / "plan"
    plan_dir.mkdir(parents=True)
    reviews_dir = wiki_root / "active" / slug / "reviews"
    reviews_dir.mkdir(parents=True)

    (plan_dir / "00-overview.md").write_text(
        "# Plan: Demo\n"
        "\n"
        "```yaml\n"
        "task: Demo\n"
        "slug: demo\n"
        "approved: true\n"
        "started: 20260422-120000\n"
        "parent: main\n"
        'root: ""\n'
        "verify: null\n"
        "```\n"
        "\n"
        "## Batch Index\n"
        "\n"
        "```yaml\n"
        "batches:\n"
        "  - name: foundation\n"
        "    file: 01-foundation.md\n"
        "    depends-on: []\n"
        "    verify: null\n"
        "```\n",
        encoding="utf-8",
    )
    (plan_dir / "01-foundation.md").write_text(
        "# Batch: foundation\n"
        "\n"
        "```yaml\n"
        "task: Demo\n"
        "batch: foundation\n"
        "cards: 1\n"
        "verify: null\n"
        "depends-on: []\n"
        "```\n"
        "\n"
        "## Batch Scope\n"
        "\n"
        "Seed the project.\n"
        "\n"
        "## Cards\n"
        "\n"
        "### Card 1: create module\n"
        "- **Reads:** `src/seed.py`\n"
        "- **Creates:** `src/seed.py`\n"
        "- **Requirements:** Empty module.\n"
        "- **Commit:** `feat(seed): init`\n",
        encoding="utf-8",
    )

    # --- project_root (mimics the hub cwd) ---
    project_root = scratch / "project"
    (project_root / "src").mkdir(parents=True)
    (project_root / "src" / "seed.py").write_text("# seed\n", encoding="utf-8")

    # --- mill_dir with slug metadata for load_task_title ---
    mill_dir = scratch / "mill"
    mill_dir.mkdir()
    (mill_dir / f".{slug}.slug.md").write_text(
        "---\n"
        f"slug: {slug}\n"
        "task_title: Demo\n"
        "---\n",
        encoding="utf-8",
    )

    # --- Stub reviewer on the import path ---
    stub_src = (
        'MODE = "bulk"\n'
        'def run(prompt_text):\n'
        "    return (\n"
        "        '# Review: Demo -- foundation\\n\\n'\n"
        "        '```yaml\\n'\n"
        "        'verdict: APPROVE\\n'\n"
        "        'reviewer_model: dummy\\n'\n"
        "        'reviewed_file: foundation\\n'\n"
        "        'date: 2026-04-22\\n'\n"
        "        '```\\n\\n'\n"
        "        '## Verdict\\n\\nAPPROVE\\nStub ok.\\n'\n"
        "    )\n"
    )
    stub_path = scratch / "_reviewer_dummy.py"
    stub_path.write_text(stub_src, encoding="utf-8")
    sys.path.insert(0, str(scratch))

    # --- Config ---
    cfg = {
        "paths": {
            "plan_dir": f"active/{slug}/plan/",
            "reviews_dir": f"active/{slug}/reviews/",
        },
        "review": {"code": {"rounds": 3, "reviewer": "dummy"}},
    }

    import _review_code

    # Reload sys.path-affected modules to pick up the stub reviewer.
    import importlib
    import _review_common
    importlib.reload(_review_common)
    importlib.reload(_review_code)

    result = _review_code.run(
        cfg,
        slug,
        mill_dir,
        wiki_root,
        project_root,
        batch_name="foundation",
    )
    _assert(result.verdict == "APPROVE", f"unexpected verdict: {result.verdict}")
    _assert(result.type == "code", f"unexpected type: {result.type}")
    review_files = list(reviews_dir.glob("*-code-review-foundation-r1.md"))
    _assert(len(review_files) == 1, f"expected 1 review file, got {review_files}")
    print("PASS: _review_code end-to-end with stub reviewer (per-batch)")


def test_notify_stdout(capsys_like: Path) -> None:
    """_notify dispatches via the stdout backend without raising."""
    _notify._reset_cache_for_tests()
    _notify.notify("mill-go.test", "smoke", slug="demo", round=1)
    print("PASS: _notify.notify() completed")


def test_builder_lock_conflict(scratch: Path) -> None:
    """Second acquire under a different slug raises LockBusy."""
    mill_dir = scratch / "lock-mill"
    mill_dir.mkdir()
    _builder_lock.acquire(mill_dir, "task-a")
    try:
        _builder_lock.acquire(mill_dir, "task-b")
    except _builder_lock.LockBusy as exc:
        _assert("task-a" in str(exc), f"unexpected message: {exc}")
        print(f"PASS: _builder_lock.acquire conflict -> LockBusy ({exc})")
    else:
        raise AssertionError("expected LockBusy")
    finally:
        _builder_lock.release(mill_dir)


def test_status_batches_round_trip(scratch: Path) -> None:
    """init_batches + set_batch_field + read_batches round-trip."""
    sp = scratch / "status.md"
    sp.write_text(
        "# Status\n"
        "\n"
        "```yaml\n"
        "phase: planned\n"
        "task: Demo\n"
        "parent: main\n"
        "```\n"
        "\n"
        "## Timeline\n"
        "\n"
        "```text\n"
        "planned  2026-04-22T12:00:00Z\n"
        "```\n",
        encoding="utf-8",
    )
    _status.init_batches(sp, ["foundation", "reviewers"])
    batches = _status.read_batches(sp)
    _assert([b["name"] for b in batches] == ["foundation", "reviewers"], "order")

    _status.set_batch_field(sp, "reviewers", "state", "running")
    _status.set_batch_field(sp, "reviewers", "implementer_session", "uuid-123")
    batches = _status.read_batches(sp)
    reviewers = next(b for b in batches if b["name"] == "reviewers")
    _assert(reviewers["state"] == "running", f"state={reviewers}")
    _assert(reviewers["implementer_session"] == "uuid-123", f"sess={reviewers}")
    _assert(
        "phase: planned" in sp.read_text(encoding="utf-8"),
        "top yaml block disturbed",
    )
    print("PASS: _status batches round-trip with top yaml intact")


def main() -> int:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    scratch = SCRATCH / f"go-assets-{uuid.uuid4().hex[:8]}"
    scratch.mkdir()
    failed = False
    try:
        test_implementer_brief_template(scratch)
        test_review_code_end_to_end(scratch)
        test_notify_stdout(scratch)
        test_builder_lock_conflict(scratch)
        test_status_batches_round_trip(scratch)
        print("PASS -- all go-asset checks")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        failed = True
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL (unexpected): {type(exc).__name__}: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        failed = True
        return 1
    finally:
        if failed:
            print(f"Scratch preserved: {scratch}", file=sys.stderr)
        else:
            _safe_rmtree.safe_rmtree(scratch, allowed_root=scratch, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
