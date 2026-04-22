"""
Review backend for code artefacts.

v2 code review does NOT look at git diff. It reads the approved plan and
the source files the plan says were touched, then asks the reviewer:
"does the implementation on disk realise what the plan promised?" The
orchestrator (mill-go) invokes this once per batch after the implementer
commits that batch, and optionally one holistic review at end-of-task.

Two modes, selected by ``batch_name``:

- ``batch_name="<name>"`` — per-batch review. Bulks
  ``00-overview.md`` + the single ``NN-<batch>.md`` + every file under
  that batch's ``Reads:`` / ``Modifies:`` / ``Creates:`` lines.
- ``batch_name=None`` — holistic review. Bulks ``00-overview.md`` +
  every batch file + the union of all referenced files.

Both modes accept ``extra_files`` — source files the orchestrator has
decided to include in the bulk this round, typically because a previous
round returned ``verdict: NEED_CONTEXT`` pointing at them. The reviewer
never scrapes git for files; the backend is explicit about what ends up
in the prompt.

Public API:
    run(cfg, slug, mill_dir, wiki_root, project_root,
        *, batch_name=None, extra_files=None) -> ReviewResult
"""
from __future__ import annotations

import sys
from pathlib import Path

from _llm_claude import LLMError
from _plan_dag import PlanDAGError, extract_batch_index
from _review_common import (
    ReviewError,
    ReviewResult,
    build_tool_rule,
    bulk_files,
    discover_round,
    load_reviewer,
    load_task_title,
    parse_batch_refs,
    parse_verdict,
    read_constraints_md,
    render_prompt,
    resolve_path,
    resolve_ref_paths,
    write_review_file,
)
from _review_plan import _load_root_from_overview


def _collect_batch_files(
    plan_dir: Path,
    batch_name: str | None,
    overview_path: Path,
) -> list[Path]:
    """Return the batch files this review covers.

    ``batch_name=None`` → every ``NN-<name>.md`` in ``plan_dir`` except
    ``00-overview.md``. ``batch_name="<name>"`` → the single batch file
    the overview's Batch Index maps ``<name>`` to.
    """
    if batch_name is None:
        files = sorted(
            p for p in plan_dir.glob("??-*.md") if p.name != "00-overview.md"
        )
        if not files:
            raise ReviewError(f"No batch files found in {plan_dir}")
        return files

    overview_text = overview_path.read_text(encoding="utf-8")
    try:
        batches = extract_batch_index(overview_text)
    except PlanDAGError as exc:
        raise ReviewError(f"Could not parse Batch Index: {exc}") from exc

    entry = next((b for b in batches if b.get("name") == batch_name), None)
    if entry is None:
        known = ", ".join(repr(b.get("name")) for b in batches) or "(none)"
        raise ReviewError(
            f"Batch {batch_name!r} not found in Batch Index; known: {known}"
        )
    batch_file = plan_dir / entry["file"]
    if not batch_file.exists():
        raise ReviewError(
            f"Batch {batch_name!r} declared but file missing: {batch_file}"
        )
    return [batch_file]


def _build_artefact_section(
    reviewer_mode: str,
    overview_path: Path,
    batch_files: list[Path],
    source_files: list[Path],
) -> str:
    """Return the ``<ARTEFACT_SECTION>`` block for the prompt.

    In tool-use mode we pass paths and tell the reviewer to Read them
    itself; in bulk mode we splice the file contents inline. Both modes
    list the same files — only the delivery mechanism differs.
    """
    if reviewer_mode == "tool-use":
        batch_list = "\n".join(f"  - `{p}`" for p in batch_files) or "  (none)"
        read_list = "\n".join(f"- `{p}`" for p in source_files) or "(none)"
        return (
            "## Plan + source files to review\n"
            f"- Overview: `{overview_path}`\n"
            f"- Batch file(s):\n{batch_list}\n\n"
            "Read the overview and every batch file above. Then read every "
            f"source file listed below for full context:\n{read_list}"
        )
    bulked = bulk_files([overview_path, *batch_files, *source_files])
    return (
        "## Plan + source content (overview + batch files + referenced source)\n"
        f"{bulked}"
    )


def run(
    cfg: dict,
    slug: str,
    mill_dir: Path,
    wiki_root: Path,
    project_root: Path,
    *,
    batch_name: str | None = None,
    extra_files: list[Path] | None = None,
) -> ReviewResult:
    """Review the code produced for a task.

    ``batch_name`` selects per-batch vs. holistic mode (see module
    docstring). ``extra_files`` are additional source files to bulk
    this round — typically supplied by the orchestrator after a prior
    round returned ``NEED_CONTEXT``.
    """
    # 1. Paths + round counter
    plan_dir = resolve_path(cfg["paths"]["plan_dir"], slug, wiki_root)
    reviews_dir = resolve_path(cfg["paths"]["reviews_dir"], slug, wiki_root)
    round_n = discover_round(reviews_dir, "code")
    max_rounds = cfg["review"]["code"]["rounds"]
    if round_n > max_rounds:
        raise ReviewError(
            f"Round {round_n} exceeds max {max_rounds} for code review"
        )

    scope_label = batch_name or "holistic"
    print(
        f"[_review_code] slug={slug!r} round={round_n} scope={scope_label}",
        file=sys.stderr,
    )

    # 2. Overview (required)
    overview_path = plan_dir / "00-overview.md"
    if not overview_path.exists():
        raise ReviewError(f"Plan overview not found: {overview_path}")
    root = _load_root_from_overview(overview_path)

    # 3. Target batch files + referenced source files
    batch_files = _collect_batch_files(plan_dir, batch_name, overview_path)

    all_raw_refs: dict[str, None] = {}
    for bp in batch_files:
        for ref in parse_batch_refs(bp):
            all_raw_refs[ref] = None
    referenced = resolve_ref_paths(list(all_raw_refs.keys()), project_root, root)

    # Deduplicate while preserving order across the two lists.
    seen: dict[Path, None] = {}
    source_files: list[Path] = []
    for p in (*referenced, *(extra_files or [])):
        if p not in seen:
            seen[p] = None
            source_files.append(p)

    if not source_files and not (extra_files or []):
        print(
            f"[_review_code] warning: no source files resolved for scope={scope_label}; "
            f"reviewer will only see plan content",
            file=sys.stderr,
        )

    # 4. Reviewer + prompt
    reviewer_name = cfg["review"]["code"]["reviewer"]
    reviewer = load_reviewer(reviewer_name)

    template_name = "review-code-batch" if batch_name else "review-code-holistic"
    tool_rule = build_tool_rule(reviewer.MODE)
    artefact_section = _build_artefact_section(
        reviewer.MODE, overview_path, batch_files, source_files
    )

    prompt_kwargs = {
        "task_title": load_task_title(mill_dir, slug),
        "tool_rule": tool_rule,
        "artefact_section": artefact_section,
        "constraints": read_constraints_md(project_root),
        "round": round_n,
        "reviewer_model": reviewer_name,
    }
    if batch_name:
        prompt_kwargs["batch_name"] = batch_name

    prompt_text = render_prompt(template_name, **prompt_kwargs)

    # 5. Dispatch + record
    try:
        raw = reviewer.run(prompt_text)
    except LLMError as exc:
        # Single sub-review → total failure
        raise ReviewError(f"Code reviewer failed: {exc}") from exc

    verdict = parse_verdict(raw)
    path = write_review_file(
        reviews_dir,
        "code",
        round_n,
        raw,
        scope=batch_name,  # None for holistic → no batch segment in filename
    )
    print(
        f"[_review_code] wrote {path.name} verdict={verdict}",
        file=sys.stderr,
    )

    return ReviewResult(
        type="code",
        round=round_n,
        verdict=verdict,
        reviews=[
            {
                "scope": scope_label,
                "verdict": verdict,
                "file": str(path),
            }
        ],
    )
