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
import _status
from _review_common import (
    ReviewError,
    ReviewResult,
    _load_root_from_overview,
    build_deletes_section,
    build_manifest_section,
    build_reattached_section,
    build_tool_rule,
    bulk_files,
    bulk_files_with_diff,
    compute_creates_union,
    compute_deletes_union,
    discover_round,
    load_reviewer,
    load_task_title,
    parse_batch_refs,
    parse_blocking_count,
    parse_missing_context,
    parse_verdict,
    read_constraints_md,
    render_prompt,
    resolve_existing_paths,
    resolve_path,
    resolve_ref_paths,
    write_review_file,
)


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
    ancestors_on_disk: list[Path],
    deletes_union: set[str],
    *,
    start_sha: str | None = None,
    diff_threshold: float = 0.25,
    project_root: Path | None = None,
) -> str:
    """Return the ``<ARTEFACT_SECTION>`` block for the prompt.

    In tool-use mode we pass paths and tell the reviewer to Read them
    itself; in bulk mode we splice the file contents inline. Both modes
    list the same files — only the delivery mechanism differs.
    ``ancestors_on_disk`` holds cross-batch creates that already exist on
    disk; they are appended to the bulk so the reviewer can verify
    cross-batch contracts. ``deletes_union`` appends an
    ``## Intentionally deleted`` section when non-empty.
    """
    all_bulked = [overview_path, *batch_files, *source_files, *ancestors_on_disk]
    manifest = build_manifest_section(all_bulked)

    if reviewer_mode == "tool-use":
        batch_list = "\n".join(f"  - `{p}`" for p in batch_files) or "  (none)"
        read_list = "\n".join(f"- `{p}`" for p in [*source_files, *ancestors_on_disk]) or "(none)"
        body = (
            f"{manifest}\n\n"
            "## Plan + source files to review\n"
            f"- Overview: `{overview_path}`\n"
            f"- Batch file(s):\n{batch_list}\n\n"
            "Read the overview and every batch file above. Then read every "
            "source file listed below for full context (includes cross-batch "
            f"ancestor creates already on disk):\n{read_list}"
        )
    else:
        # Always bulk overview + batch files + ancestors at full content.
        # source_files use diff-scoping if start_sha is set.
        plan_and_ancestors = [overview_path, *batch_files, *ancestors_on_disk]
        if start_sha is not None and project_root is not None:
            scoped_sources = bulk_files_with_diff(source_files, start_sha, project_root, diff_threshold)
            bulked = bulk_files(plan_and_ancestors) + ("\n\n" + scoped_sources if scoped_sources else "")
        else:
            bulked = bulk_files(all_bulked)
        body = (
            f"{manifest}\n\n"
            "## Plan + source content (overview + batch files + referenced source + ancestor creates)\n"
            f"{bulked}"
        )

    if deletes_union:
        body += "\n\n" + build_deletes_section(sorted(deletes_union))
    return body


def run(
    cfg: dict,
    slug: str,
    mill_dir: Path,
    wiki_root: Path,
    project_root: Path,
    *,
    max_rounds: int | None = None,
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
    plan_dir = resolve_path(cfg["paths"]["plan_dir"], slug)
    reviews_dir = resolve_path(cfg["paths"]["reviews_dir"], slug)
    scope_label = batch_name or "holistic"
    round_n = discover_round(reviews_dir, "code", scope_label)
    max_rounds = max_rounds if max_rounds is not None else cfg["review"]["code"]["rounds"]
    if round_n > max_rounds:
        raise ReviewError(
            f"Round {round_n} exceeds max {max_rounds} for code review"
        )
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

    # Per-batch diff-scoping: read start_sha from status.md if batch_name is set.
    start_sha: str | None = None
    diff_threshold: float = cfg["review"]["code"].get("diff_scope_threshold", 0.25)
    if batch_name is not None:
        try:
            status_path = resolve_path("status.md", slug)
            batches_list = _status.read_batches(status_path)
            entry = next((b for b in batches_list if b.get("name") == batch_name), None)
            start_sha = entry.get("start_sha") if entry else None
            if start_sha is None:
                print(
                    f"[_review_code] no start_sha for batch {batch_name!r}; using full file content",
                    file=sys.stderr,
                )
        except Exception as exc:
            print(
                f"[_review_code] warning: could not read start_sha for batch {batch_name!r}: {exc}; using full file content",
                file=sys.stderr,
            )

    all_raw_refs: dict[str, None] = {}
    for bp in batch_files:
        for ref in parse_batch_refs(bp):
            all_raw_refs[ref] = None
    creates_union = compute_creates_union(plan_dir)
    deletes_union = compute_deletes_union(plan_dir)
    referenced = resolve_ref_paths(
        list(all_raw_refs.keys()), project_root, root,
        creates_union=creates_union, deletes_union=deletes_union, wiki_root=wiki_root,
    )

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

    ancestors_on_disk = resolve_existing_paths(
        [raw for raw in creates_union if raw not in all_raw_refs],
        project_root,
        root,
        wiki_root=wiki_root,
    )
    ancestors_on_disk = [p for p in ancestors_on_disk if p not in source_files]

    # 4. Reviewer + prompt
    reviewer_name = cfg["review"]["code"]["reviewer"]
    holistic_effort: str | None = cfg["review"]["code"].get("holistic_effort", "max") if batch_name is None else None
    reviewer = load_reviewer(reviewer_name)
    timeout = cfg["llm"]["holistic_timeout"] if batch_name is None else cfg["llm"]["bulk_timeout"]

    template_name = "review-code-batch" if batch_name else "review-code-holistic"
    tool_rule = build_tool_rule(reviewer.MODE)
    artefact_section = _build_artefact_section(
        reviewer.MODE, overview_path, batch_files, source_files, ancestors_on_disk,
        deletes_union,
        start_sha=start_sha,
        diff_threshold=diff_threshold,
        project_root=project_root,
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
        raw, session_id = reviewer.run(prompt_text, timeout=timeout, effort=holistic_effort)
    except LLMError as exc:
        return ReviewResult(
            type="code",
            round=round_n,
            verdict="REQUEST_CHANGES",
            blocking_count=0,
            reviews=[{
                "scope": scope_label,
                "verdict": "ERROR",
                "file": None,
                "error": str(exc),
                "session_id": None,
            }],
        )

    verdict = parse_verdict(raw)

    if verdict == "NEED_CONTEXT":
        missing_raw = parse_missing_context(raw)
        missing_paths = resolve_existing_paths(
            missing_raw, project_root, root, wiki_root=wiki_root
        )
        if missing_paths:
            retry_prompt = (
                build_reattached_section(missing_paths)
                + "\n\n"
                + "Please continue your review using the re-attached files above. "
                + "The original prompt is already in your session context."
            )
            print(
                f"[_review_code] NEED_CONTEXT round-1; retrying with resume "
                f"({len(missing_paths)} re-attached file(s)) session={(session_id or '?')[:8]}",
                file=sys.stderr,
            )
            try:
                raw, session_id = reviewer.run(
                    retry_prompt, session_id=session_id, resume=True, timeout=timeout, effort=holistic_effort
                )
            except LLMError as exc:
                return ReviewResult(
                    type="code",
                    round=round_n,
                    verdict="REQUEST_CHANGES",
                    blocking_count=0,
                    reviews=[{
                        "scope": scope_label,
                        "verdict": "ERROR",
                        "file": None,
                        "error": f"resume retry failed: {exc}",
                        "session_id": None,
                    }],
                )
            verdict = parse_verdict(raw)
            # Second NEED_CONTEXT propagates to caller untouched.

    blocking_count = parse_blocking_count(raw, severity="BLOCKING")
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
        blocking_count=blocking_count,
        reviews=[
            {
                "scope": scope_label,
                "verdict": verdict,
                "file": str(path),
                "session_id": session_id,
            }
        ],
    )
