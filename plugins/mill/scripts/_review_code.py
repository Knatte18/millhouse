"""
Review backend for code artefacts.

The LLM reviewer does NOT look at git diff. It reads the approved plan and
the source files the plan says were touched, then asks: "does the
implementation on disk realise what the plan promised?" The orchestrator
(mill-go) invokes this once per batch after the implementer commits that
batch, and optionally one holistic review at end-of-task.

The backend itself uses git deterministically in two places:
- ``bulk_files_with_diff`` (in ``prepare``) scopes large source files to
  their diff against ``start_sha`` so the reviewer sees a focused diff
  rather than the full file content.
- The mechanical rename check (in ``finalize``) runs
  ``git diff --name-status --find-renames`` to detect whether planned
  ``Moves:`` pairs landed as git-detected renames; advisory NIT findings
  are spliced into the review text for any pair that did not.

Two modes, selected by ``scope``:

- ``scope="<name>"`` -- per-batch review. Bulks
  ``00-overview.md`` + the single ``NN-<batch>.md`` + every file under
  that batch's ``Context:`` / ``Edits:`` / ``Creates:`` lines plus
  Move targets (the relocated files exist post-implementation).
- ``scope="holistic"`` -- holistic review. Bulks ``00-overview.md`` +
  every batch file + the union of all referenced files.

Both modes accept ``extra_files`` -- source files the orchestrator has
decided to include in the bulk this round, typically because a previous
round returned ``verdict: NEED_CONTEXT`` pointing at them.

Public API:
    prepare(cfg, slug, *, scope, mill_dir, project_root, wiki_root, git_root, extra_files=None) -> dict
        Render prompt and resolve spec; return prepare dict.
    finalize(cfg, slug, raw_text, *, scope, round_n, reviews_dir, mill_dir, project_root, wiki_root, git_root) -> ReviewResult
        Parse verdict from raw_text and return ReviewResult.
    run(cfg, slug, mill_dir, wiki_root, project_root,
        *, batch_name=None, extra_files=None) -> ReviewResult
        Legacy API; calls prepare -> reviewer -> finalize.
"""
from __future__ import annotations

import sys
from pathlib import Path

import re

import _moves_check
import _paths
import _reviewer_single
import _reviewers
import _subprocess_util
from _llm_common import LLMError
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
    compute_moves_union,
    discover_round,
    extract_review_content,
    finalize_scope,
    load_task_title,
    maybe_switch_spec_for_large_prompt,
    parse_batch_refs,
    parse_blocking_count,
    parse_missing_context,
    parse_moves,
    parse_verdict,
    read_constraints_md,
    render_prompt,
    resolve_existing_paths,
    resolve_path,
    resolve_ref_paths,
    worktree_snapshot_guard,
    write_review_file,
)


def _aggregate_top_verdict(reviews_list: list[dict], parsed_verdict: str) -> str:
    """Return 'ERROR' if every sub-review has verdict 'ERROR', else parsed_verdict."""
    return (
        "ERROR"
        if reviews_list and all(r.get("verdict") == "ERROR" for r in reviews_list)
        else parsed_verdict
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


def prepare(
    cfg: dict,
    slug: str,
    *,
    scope: str | None,
    mill_dir: Path,
    project_root: Path,
    wiki_root: Path,
    git_root: Path,
    extra_files: list[Path] | None = None,
    max_rounds: int | None = None,
    prior_notes: Path | None = None,
) -> dict:
    """Prepare a code review by rendering the prompt for a single scope.

    Args:
        scope: Batch name (e.g., "01-setup") or None for holistic.
        extra_files: Additional source files to include in the bulk.
        max_rounds: Override the configured round cap for this scope.
        prior_notes: Path to a file containing prior-round non-blocking findings digest.

    Returns:
        Dict with keys: prompt_text, model, round, reviews_dir, scope.
    """
    # 1. Paths + round counter
    plan_dir = resolve_path(cfg["paths"]["plan_dir"], slug)
    reviews_dir = resolve_path(cfg["paths"]["reviews_dir"], slug)
    scope_label = scope or "holistic"
    round_n = discover_round(reviews_dir, "code", scope_label)

    # Round cap check. The max_rounds kwarg overrides the configured cap
    # (mirrors run()'s pre-refactor behaviour); enforcing here covers both the
    # full path and the agent-mode CLI prepare stage.
    if scope is not None:
        configured_max = cfg["roles"]["code-review"]["batch"]["rounds"]
    else:
        configured_max = cfg["roles"]["code-review"]["holistic"]["rounds"]
    effective_max = max_rounds if max_rounds is not None else configured_max
    if round_n > effective_max:
        raise ReviewError(
            f"Round {round_n} exceeds max {effective_max} for code review"
        )

    # 2. Overview (required)
    overview_path = plan_dir / "00-overview.md"
    if not overview_path.exists():
        raise ReviewError(f"Plan overview not found: {overview_path}")
    root = _load_root_from_overview(overview_path)

    # 3. Target batch files + referenced source files
    batch_files = _collect_batch_files(plan_dir, scope, overview_path)

    # Per-batch diff-scoping: read start_sha from status.md if scope is set.
    start_sha: str | None = None
    diff_threshold: float = cfg["roles"]["code-review"].get("diff_scope_threshold", 0.25)
    if scope is not None:
        try:
            status_path = _paths.status_path(project_root, cfg)
            batches_list = _status.read_batches(status_path)
            entry = next((b for b in batches_list if b.get("name") == scope), None)
            start_sha = entry.get("start_sha") if entry else None
            if start_sha is None:
                print(
                    f"[_review_code] no start_sha for batch {scope!r}; using full file content",
                    file=sys.stderr,
                )
        except Exception as exc:
            print(
                f"[_review_code] warning: could not read start_sha for batch {scope!r}: {exc}; using full file content",
                file=sys.stderr,
            )

    all_raw_refs: dict[str, None] = {}
    for bp in batch_files:
        for ref in parse_batch_refs(bp):
            all_raw_refs[ref] = None
    creates_union = compute_creates_union(plan_dir)
    deletes_union = compute_deletes_union(plan_dir)
    # Move targets exist post-implementation; the code reviewer should see the
    # relocated file so it can verify the rename landed correctly.
    _, moves_targets_union = compute_moves_union(plan_dir)
    referenced = resolve_ref_paths(
        list(all_raw_refs.keys()), project_root, root,
        creates_union=creates_union, deletes_union=deletes_union, wiki_root=wiki_root, git_root=git_root,
    )

    # Deduplicate while preserving order across the three lists.
    seen: dict[Path, None] = {}
    source_files: list[Path] = []
    for p in (*referenced, *(extra_files or [])):
        if p not in seen:
            seen[p] = None
            source_files.append(p)

    # Resolve move targets not already in the explicit batch refs; use
    # resolve_existing_paths so a missing target (incomplete implementation)
    # is silently skipped rather than hard-failing code review.
    moves_targets_on_disk = resolve_existing_paths(
        [t for t in moves_targets_union if t not in all_raw_refs],
        project_root,
        root,
        wiki_root=wiki_root,
        git_root=git_root,
    )
    for p in moves_targets_on_disk:
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
        git_root=git_root,
    )
    ancestors_on_disk = [p for p in ancestors_on_disk if p not in source_files]

    # 4. Reviewer + prompt
    if scope is not None:
        reviewer_name = cfg["roles"]["code-review"]["batch"]["reviewer"]
    else:
        reviewer_name = cfg["roles"]["code-review"]["holistic"]["reviewer"]
    if reviewer_name is None:
        raise ReviewError(
            f"code-review {'batch' if scope else 'holistic'} reviewer is null; "
            f"the orchestrator should not have invoked this scope"
        )
    hub_dir = project_root
    registry = _reviewers.load(hub_dir)
    spec = _reviewers.resolve(registry, reviewer_name)

    template_name = "review-code-batch" if scope else "review-code-holistic"
    mode = "tool-use" if spec.get("tooluse") else "bulk"
    tool_rule = build_tool_rule(mode)
    artefact_section = _build_artefact_section(
        mode, overview_path, batch_files, source_files, ancestors_on_disk,
        deletes_union,
        start_sha=start_sha,
        diff_threshold=diff_threshold,
        project_root=project_root,
    )

    # Build prior-nonblocking digest: read file if provided and readable, else "(none)".
    # This is ALWAYS set so render_prompt does not raise KeyError on the <PRIOR_NONBLOCKING> token.
    if prior_notes is not None and prior_notes.is_file():
        prior_nonblocking = prior_notes.read_text(encoding="utf-8")
    else:
        prior_nonblocking = "(none)"

    prompt_kwargs = {
        "task_title": load_task_title(project_root, wiki_root, cfg, slug),
        "tool_rule": tool_rule,
        "artefact_section": artefact_section,
        "constraints": read_constraints_md(project_root),
        "round": round_n,
        "reviewer_model": reviewer_name,
        "prior_nonblocking": prior_nonblocking,
    }
    if scope:
        prompt_kwargs["batch_name"] = scope

    prompt_text = render_prompt(template_name, **prompt_kwargs)

    if scope is None:
        spec, reviewer_name = maybe_switch_spec_for_large_prompt(
            prompt_text, spec, reviewer_name, cfg, "code-review", "holistic", registry
        )

    return {
        "prompt_text": prompt_text,
        "model": spec.get("model"),
        "round": round_n,
        "reviews_dir": reviews_dir,
        "scope": scope_label,
    }


def finalize(
    cfg: dict,
    slug: str,
    raw_text: str,
    *,
    scope: str | None,
    round_n: int,
    reviews_dir: Path,
    mill_dir: Path,
    project_root: Path,
    wiki_root: Path,
    git_root: Path,
) -> ReviewResult:
    """Finalize a code review by parsing verdict and writing the review file.

    Args:
        raw_text: Raw review output from the reviewer.
        scope: Batch name or None for holistic.
        round_n: Round number.
        reviews_dir: Directory where review files are stored.

    Returns:
        ReviewResult with verdict, blocking count, and review entries.
    """
    scope_label = scope or "holistic"

    try:
        review_entry = finalize_scope(
            reviews_dir, "code", round_n, raw_text, scope=scope
        )
    except ReviewError as exc:
        path = write_review_file(
            reviews_dir,
            "code",
            round_n,
            raw_text,
            scope=scope,
        )
        return ReviewResult(
            type="code",
            round=round_n,
            verdict="ERROR",
            blocking_count=0,
            reviews=[{
                "scope": scope_label,
                "verdict": "ERROR",
                "file": str(path),
                "error": f"parse_verdict failed: {exc}",
                "session_id": None,
            }],
        )

    return ReviewResult(
        type="code",
        round=round_n,
        verdict=review_entry["verdict"],
        blocking_count=review_entry["blocking_count"],
        nit_count=review_entry["nit_count"],
        reviews=[{
            "scope": scope_label,
            "verdict": review_entry["verdict"],
            "file": review_entry["file"],
            "session_id": None,
        }],
    )


def run(
    cfg: dict,
    slug: str,
    mill_dir: Path,
    wiki_root: Path,
    project_root: Path,
    *,
    git_root: Path,
    max_rounds: int | None = None,
    batch_name: str | None = None,
    extra_files: list[Path] | None = None,
    prior_notes: Path | None = None,
) -> ReviewResult:
    """Review the code produced for a task.

    ``batch_name`` selects per-batch vs. holistic mode. ``extra_files`` are
    additional source files to bulk this round. ``prior_notes`` is a path to
    a file containing prior-round non-blocking findings digest.
    """
    with worktree_snapshot_guard(project_root, expected_paths=[cfg["paths"]["reviews_dir"]]):
        # Check if review is disabled
        scope_label = batch_name or "holistic"
        reviews_dir = resolve_path(cfg["paths"]["reviews_dir"], slug)
        if batch_name is not None:
            effective_max = max_rounds if max_rounds is not None else cfg["roles"]["code-review"]["batch"]["rounds"]
        else:
            effective_max = max_rounds if max_rounds is not None else cfg["roles"]["code-review"]["holistic"]["rounds"]
        if effective_max == 0:
            print(
                "[_review_code] rounds=0 -- review disabled, returning APPROVE",
                file=sys.stderr,
            )
            return ReviewResult(
                type="code",
                round=0,
                verdict="APPROVE",
                blocking_count=0,
                reviews=[{"scope": scope_label, "verdict": "APPROVE", "file": None, "skipped": True}],
            )

        # Prepare
        prepare_result = prepare(
            cfg, slug, scope=batch_name, mill_dir=mill_dir, project_root=project_root,
            wiki_root=wiki_root, git_root=git_root, extra_files=extra_files,
            max_rounds=max_rounds, prior_notes=prior_notes,
        )
        prompt_text = prepare_result["prompt_text"]
        round_n = prepare_result["round"]
        reviews_dir = prepare_result["reviews_dir"]

        # Get spec for reviewer call
        if batch_name is not None:
            reviewer_name = cfg["roles"]["code-review"]["batch"]["reviewer"]
        else:
            reviewer_name = cfg["roles"]["code-review"]["holistic"]["reviewer"]
        registry = _reviewers.load(project_root)
        spec = _reviewers.resolve(registry, reviewer_name)
        timeout = cfg["llm"]["holistic_timeout"] if batch_name is None else cfg["llm"]["bulk_timeout"]
        if batch_name is None:
            spec, _ = maybe_switch_spec_for_large_prompt(
                prompt_text, spec, reviewer_name, cfg, "code-review", "holistic", registry
            )

        # Invoke reviewer
        try:
            raw, session_id = _reviewer_single.run(spec, prompt_text, timeout=timeout)
            raw = extract_review_content(raw)
        except LLMError as exc:
            return ReviewResult(
                type="code",
                round=round_n,
                verdict="ERROR",
                blocking_count=0,
                reviews=[{
                    "scope": scope_label,
                    "verdict": "ERROR",
                    "file": None,
                    "error": str(exc),
                    "session_id": None,
                }],
            )

        # Try to parse verdict; if NEED_CONTEXT, retry
        try:
            verdict = parse_verdict(raw)
        except ReviewError as exc:
            path = write_review_file(
                reviews_dir,
                "code",
                round_n,
                raw,
                scope=batch_name,
            )
            return ReviewResult(
                type="code",
                round=round_n,
                verdict="ERROR",
                blocking_count=0,
                reviews=[{
                    "scope": scope_label,
                    "verdict": "ERROR",
                    "file": str(path),
                    "error": f"parse_verdict failed: {exc}",
                    "session_id": session_id,
                }],
            )

        # Handle NEED_CONTEXT with retry
        if verdict == "NEED_CONTEXT":
            root = _load_root_from_overview(resolve_path(cfg["paths"]["plan_dir"], slug) / "00-overview.md")
            missing_raw = parse_missing_context(raw)
            missing_paths = resolve_existing_paths(
                missing_raw, project_root, root, wiki_root=wiki_root, git_root=git_root
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
                    raw, session_id = _reviewer_single.run(
                        spec, retry_prompt, session_id=session_id, resume=True, timeout=timeout
                    )
                    raw = extract_review_content(raw)
                except LLMError as exc:
                    return ReviewResult(
                        type="code",
                        round=round_n,
                        verdict="ERROR",
                        blocking_count=0,
                        reviews=[{
                            "scope": scope_label,
                            "verdict": "ERROR",
                            "file": None,
                            "error": f"resume retry failed: {exc}",
                            "session_id": None,
                        }],
                    )
                try:
                    verdict = parse_verdict(raw)
                except ReviewError as exc:
                    path = write_review_file(
                        reviews_dir,
                        "code",
                        round_n,
                        raw,
                        scope=batch_name,
                    )
                    return ReviewResult(
                        type="code",
                        round=round_n,
                        verdict="ERROR",
                        blocking_count=0,
                        reviews=[{
                            "scope": scope_label,
                            "verdict": "ERROR",
                            "file": str(path),
                            "error": f"parse_verdict failed: {exc}",
                            "session_id": session_id,
                        }],
                    )

        # Finalize
        result = finalize(
            cfg, slug, raw, scope=batch_name, round_n=round_n, reviews_dir=reviews_dir,
            mill_dir=mill_dir, project_root=project_root, wiki_root=wiki_root, git_root=git_root
        )
        # Preserve session_id from reviewer call
        if result.reviews:
            result.reviews[0]["session_id"] = session_id
        return result
