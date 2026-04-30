"""
Integration test for mill-plan assets.

mill-plan itself is interactive Opus reasoning; we do not exercise the
full skill end-to-end here (that would burn real tokens and require a
live reviewer). Instead we verify the supporting assets the skill
depends on:

    - ``plan-overview.md`` + ``plan-batch.md`` templates render without
      KeyError once every token is supplied, and the rendered output
      has the structure the skill promises (fenced-yaml frontmatter,
      Batch Index block, Cards section).
    - ``_plan_dag.extract_batch_index`` + ``validate`` accept a small
      hand-written dummy plan and reject a cyclic variant of it.
    - ``_review_plan._load_root_from_overview`` reads the ``root:``
      field from the fenced-yaml frontmatter (the v2 shape) — the
      function used to only understand ``---`` frontmatter, which would
      silently drop ``root:`` on every v2 plan.
    - ``_timestamp.now_utc_compact`` + ``now_utc_iso`` produce the
      shapes the skill substitutes into templates.

Keeps a tiny fixture under ``.scratch/`` so a failure leaves
inspectable artefacts behind; on PASS the fixture is removed.

Run from hub root:
    python plugins/mill/integration_tests/test-plan-assets.py

Exit 0 = PASS, 1 = any failure.
"""
from __future__ import annotations

import re
import shutil
import sys
import uuid
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS = HUB / "plugins" / "mill" / "scripts"
PLUGIN_ROOT = HUB / "plugins" / "mill"
TEMPLATES = HUB / "plugins" / "mill" / "templates"
SCRATCH = HUB / ".scratch"

sys.path.insert(0, str(SCRIPTS))

import _plan_dag  # noqa: E402
import _render  # noqa: E402
import _review_plan  # noqa: E402
import _timestamp  # noqa: E402


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _strip_leading_comment(text: str) -> str:
    """Replicate _status._strip_leading_comment for template bodies."""
    stripped = text.lstrip()
    if not stripped.startswith("<!--"):
        return text
    close = stripped.find("-->")
    if close == -1:
        return text
    return stripped[close + len("-->") :].lstrip("\r\n")


def test_overview_template_renders(scratch: Path) -> None:
    """plan-overview.md renders with every token supplied."""
    template = TEMPLATES / "plan-overview.md"
    body = _strip_leading_comment(template.read_text(encoding="utf-8"))
    tmp = scratch / "overview-rendered.md"
    tmp.write_text(body, encoding="utf-8")
    rendered = _render.render(
        tmp,
        {
            "TASK_TITLE": "Demo task",
            "SLUG": "demo-task",
            "STARTED": _timestamp.now_utc_compact(),
            "PARENT_BRANCH": "main",
        },
    )
    _assert("# Plan: Demo task" in rendered, "title not substituted")
    _assert("slug: demo-task" in rendered, "slug yaml not substituted")
    _assert("parent: main" in rendered, "parent yaml not substituted")
    _assert("approved: false" in rendered, "approved default missing")
    _assert("## Batch Index" in rendered, "Batch Index heading missing")
    _assert("## Shared Decisions" in rendered, "Shared Decisions heading missing")
    _assert("## All Files Touched" in rendered, "All Files Touched heading missing")
    _assert("<TASK_TITLE>" not in rendered, "unresolved token in overview")
    print("PASS: plan-overview.md renders with every token substituted")


def test_batch_template_renders(scratch: Path) -> None:
    """plan-batch.md renders with every token supplied."""
    template = TEMPLATES / "plan-batch.md"
    body = _strip_leading_comment(template.read_text(encoding="utf-8"))
    tmp = scratch / "batch-rendered.md"
    tmp.write_text(body, encoding="utf-8")
    rendered = _render.render(
        tmp,
        {
            "TASK_TITLE": "Demo task",
            "BATCH_NAME": "foundation",
            "BATCH_SLUG": "foundation",
        },
    )
    _assert("# Batch: foundation" in rendered, "batch title not substituted")
    _assert("batch: foundation" in rendered, "batch yaml not substituted")
    _assert("## Batch Scope" in rendered, "Batch Scope heading missing")
    _assert("## Cards" in rendered, "Cards heading missing")
    _assert("## Batch Tests" in rendered, "Batch Tests heading missing")
    _assert("<BATCH_NAME>" not in rendered, "unresolved token in batch")
    print("PASS: plan-batch.md renders with every token substituted")


def test_plan_dag_accepts_minimal_plan(scratch: Path) -> None:
    """A trivial two-batch plan with a valid DAG passes validate()."""
    plan_dir = scratch / "good-plan"
    plan_dir.mkdir(parents=True)
    overview = plan_dir / "00-overview.md"
    overview.write_text(
        "# Plan: Demo\n"
        "\n"
        "```yaml\n"
        'task: Demo\n'
        'slug: demo\n'
        'approved: false\n'
        'started: 20260422-120000\n'
        'parent: main\n'
        'root: ""\n'
        'verify: null\n'
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
        "  - name: integration\n"
        "    file: 02-integration.md\n"
        "    depends-on: [foundation]\n"
        "    verify: null\n"
        "```\n",
        encoding="utf-8",
    )
    (plan_dir / "01-foundation.md").write_text("# Batch: foundation\n", encoding="utf-8")
    (plan_dir / "02-integration.md").write_text("# Batch: integration\n", encoding="utf-8")

    batches = _plan_dag.extract_batch_index(overview.read_text(encoding="utf-8"))
    batch_files = sorted(
        p.name for p in plan_dir.glob("??-*.md") if p.name != "00-overview.md"
    )
    _plan_dag.validate(batches, batch_files)
    print("PASS: _plan_dag accepts a minimal valid plan")


def test_plan_dag_rejects_cycle(scratch: Path) -> None:
    """A cycle in depends-on raises PlanDAGError from validate()."""
    plan_dir = scratch / "bad-plan"
    plan_dir.mkdir(parents=True)
    overview = plan_dir / "00-overview.md"
    overview.write_text(
        "```yaml\n"
        "batches:\n"
        "  - name: a\n"
        "    file: 01-a.md\n"
        "    depends-on: [b]\n"
        "  - name: b\n"
        "    file: 02-b.md\n"
        "    depends-on: [a]\n"
        "```\n",
        encoding="utf-8",
    )
    (plan_dir / "01-a.md").write_text("", encoding="utf-8")
    (plan_dir / "02-b.md").write_text("", encoding="utf-8")
    batches = _plan_dag.extract_batch_index(overview.read_text(encoding="utf-8"))
    try:
        _plan_dag.validate(batches, ["01-a.md", "02-b.md"])
    except _plan_dag.PlanDAGError as exc:
        _assert("Cycle" in str(exc), f"wrong error: {exc}")
        print(f"PASS: _plan_dag rejects cycle -- {exc}")
        return
    raise AssertionError("cycle was not rejected")


def test_load_root_reads_fenced_yaml(scratch: Path) -> None:
    """_review_plan._load_root_from_overview picks up root from fenced yaml."""
    overview = scratch / "overview-with-root.md"
    overview.write_text(
        "# Plan: Root test\n"
        "\n"
        "```yaml\n"
        "task: Root test\n"
        "slug: root-test\n"
        "root: subrepo\n"
        "```\n",
        encoding="utf-8",
    )
    root = _review_plan._load_root_from_overview(overview)
    _assert(root == "subrepo", f"root not extracted; got {root!r}")

    overview_empty = scratch / "overview-empty-root.md"
    overview_empty.write_text(
        "```yaml\n"
        'task: x\n'
        'root: ""\n'
        "```\n",
        encoding="utf-8",
    )
    _assert(
        _review_plan._load_root_from_overview(overview_empty) is None,
        "empty root should yield None (falsy)",
    )
    print("PASS: _load_root_from_overview reads fenced-yaml frontmatter")


def test_timestamps_have_expected_shape() -> None:
    compact = _timestamp.now_utc_compact()
    iso = _timestamp.now_utc_iso()
    _assert(
        re.fullmatch(r"\d{8}-\d{6}", compact) is not None,
        f"compact wrong shape: {compact!r}",
    )
    _assert(
        re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", iso) is not None,
        f"iso wrong shape: {iso!r}",
    )
    print(f"PASS: timestamps -- compact={compact} iso={iso}")


def main() -> int:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    scratch = SCRATCH / f"plan-assets-{uuid.uuid4().hex[:8]}"
    scratch.mkdir()
    failed = False
    try:
        test_overview_template_renders(scratch)
        test_batch_template_renders(scratch)
        test_plan_dag_accepts_minimal_plan(scratch)
        test_plan_dag_rejects_cycle(scratch)
        test_load_root_reads_fenced_yaml(scratch)
        test_timestamps_have_expected_shape()
        print("PASS -- all plan-asset checks")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        failed = True
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL (unexpected): {type(exc).__name__}: {exc}", file=sys.stderr)
        failed = True
        return 1
    finally:
        if failed:
            print(f"Scratch preserved: {scratch}", file=sys.stderr)
        else:
            shutil.rmtree(str(scratch), ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
