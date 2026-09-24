"""
Review backend for code artefacts.

The LLM reviewer does NOT look at git diff.
It reads the approved plan and the source files the plan says were touched, then asks: "does the
implementation on disk realise what the plan promised?"
The orchestrator (mill-go) invokes this once at end-of-task as a holistic review.
It bulks ``00-overview.md`` + every batch file + the union of all referenced files.

``extra_files`` are source files the orchestrator has decided to include in the bulk this round,
typically because a previous round returned ``verdict: NEED_CONTEXT`` pointing at them.

Public API:
    prepare(cfg, slug, *, mill_dir, project_root, wiki_root, git_root, extra_files=None) -> dict
    Render prompt and resolve spec;
        return prepare dict.
    finalize(cfg, slug, raw_text, *, round_n, reviews_dir, mill_dir, project_root, wiki_root, git_root) -> ReviewResult
    Parse verdict from raw_text and return ReviewResult.
    run(cfg, slug, mill_dir, wiki_root, project_root, *, git_root, extra_files=None) -> ReviewResult Legacy API;
    calls prepare -> reviewer -> finalize.
"""
from __future__ import annotations

import sys
from pathlib import Path

import _reviewer_single
import _reviewers
from _llm_common import LLMError
from _review_common import (
    DisplayRoots,
    ReviewError,
    ReviewResult,
    _load_root_from_overview,
    apply_cost_metadata,
    build_deletes_section,
    build_manifest_section,
    build_reattached_section,
    build_tool_rule,
    bulk_files,
    compute_creates_union,
    compute_deletes_union,
    compute_moves_union,
    discover_round,
    extract_review_content,
    finalize_scope,
    load_task_title,
    maybe_switch_spec_for_large_prompt,
    parse_batch_refs,
    parse_missing_context,
    parse_verdict,
    read_constraints_md,
    render_prompt,
    resolve_blocking_classes,
    resolve_existing_paths,
    resolve_path,
    resolve_ref_paths,
    sum_optional,
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


def _collect_batch_files(plan_dir: Path) -> list[Path]:
    """Return every ``NN-<name>.md`` batch file in ``plan_dir`` except ``00-overview.md``."""
    files = sorted(
        p for p in plan_dir.glob("??-*.md") if p.name != "00-overview.md"
    )
    if not files:
        raise ReviewError(f"No batch files found in {plan_dir}")
    return files


def _build_artefact_section(
    reviewer_mode: str,
    overview_path: Path,
    batch_files: list[Path],
    source_files: list[Path],
    ancestors_on_disk: list[Path],
    deletes_union: set[str],
    *,
    roots: DisplayRoots | None = None,
) -> str:
    """Return the ``<ARTEFACT_SECTION>`` block for the prompt.

    In tool-use mode we pass paths and tell the reviewer to Read them itself;
    in bulk mode we splice the file contents inline.
    Both modes list the same files — only the delivery mechanism differs. ``ancestors_on_disk``
    holds cross-batch creates that already exist on disk;
    they are appended to the bulk so the reviewer can verify cross-batch contracts.
    ``deletes_union`` appends an ``## Intentionally deleted`` section when non-empty.

    When ``roots`` is not ``None``, every displayed path (manifest bullets, tool-use lists, bulk
    delimiters) is rendered relative via ``roots.render`` instead of as a raw absolute path, and the
    tool-use branch's instruction sentence tells the reviewer to resolve each listed path against
    the root stated in the ``## Path roots`` block.
    """
    all_bulked = [overview_path, *batch_files, *source_files, *ancestors_on_disk]
    manifest = build_manifest_section(all_bulked, roots=roots)

    if reviewer_mode == "tool-use":
        render = roots.render if roots is not None else str
        batch_list = "\n".join(f"  - `{render(p)}`" for p in batch_files) or "  (none)"
        read_list = "\n".join(
            f"- `{render(p)}`" for p in [*source_files, *ancestors_on_disk]
        ) or "(none)"
        body = (
            f"{manifest}\n\n"
            "## Plan + source files to review\n"
            f"- Overview: `{render(overview_path)}`\n"
            f"- Batch file(s):\n{batch_list}\n\n"
            "Read the overview and every batch file above. Then read every "
            "source file listed below for full context (includes cross-batch "
            f"ancestor creates already on disk):\n{read_list}\n\n"
            "Every path listed above is relative to the root stated in the "
            "`## Path roots` block above and must be resolved against it before reading."
        )
    else:
        bulked = bulk_files(all_bulked, roots=roots)
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
    mill_dir: Path,
    project_root: Path,
    wiki_root: Path,
    git_root: Path,
    extra_files: list[Path] | None = None,
    max_rounds: int | None = None,
    prior_notes: Path | None = None,
    agent_mode: bool = False,
) -> dict:
    """Prepare the holistic code review by rendering its prompt.

    Args:
        extra_files: Additional source files to include in the bulk.
        max_rounds: Override the configured holistic round cap.
        prior_notes: Path to a file containing prior-round non-blocking findings digest.
        agent_mode: When True, build_tool_rule returns the agent-mode cell (adds the single Write
            carve-out for the .out.md report).
            Defaults to False so run()'s `--stage full` fallback keeps receiving today's non-agent
                rule unchanged.

    Returns:
        Dict with keys: prompt_text, model, effort, round, reviews_dir, scope.
    """
    # 1. Paths + round counter
    plan_dir = resolve_path(cfg["paths"]["plan_dir"], slug)
    reviews_dir = resolve_path(cfg["paths"]["reviews_dir"], slug)
    round_n = discover_round(reviews_dir, "code", "holistic")

    # Round cap check.
    # The max_rounds kwarg overrides the configured cap (mirrors run()'s pre-refactor behaviour); enforcing here covers both the full path and the agent-mode CLI prepare stage.
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
    batch_files = _collect_batch_files(plan_dir)

    # Context: refs are split from Edits:/Creates:/Deletes: refs so only the former can soft-fail on a confirmed git-ignore hit (#733) -- a missing Edits:/Creates:/Deletes: ref still hard-fails unconditionally, since those name files the batch is expected to produce or touch.
    context_only_refs: dict[str, None] = {}
    other_refs: dict[str, None] = {}
    for bp in batch_files:
        for ref in parse_batch_refs(bp, fields=("Context",)):
            context_only_refs[ref] = None
        for ref in parse_batch_refs(bp, fields=("Edits", "Creates", "Deletes")):
            other_refs[ref] = None
    creates_union = compute_creates_union(plan_dir)
    deletes_union = compute_deletes_union(plan_dir)
    # Move targets exist post-implementation;
    # the code reviewer should see the relocated file so it can verify the rename landed correctly.
    # Move sources no longer exist post-implementation -- fold them into deletes_union so a stale Context: ref pointing at a path a later batch relocates is silently suppressed rather than hard-failing (#686).
    moves_sources_union, moves_targets_union = compute_moves_union(plan_dir)
    other_resolved = resolve_ref_paths(
        list(other_refs.keys()), project_root, root,
        creates_union=creates_union, deletes_union=deletes_union | moves_sources_union,
        wiki_root=wiki_root, git_root=git_root,
    )
    context_resolved = resolve_ref_paths(
        list(context_only_refs.keys()), project_root, root,
        creates_union=creates_union, deletes_union=deletes_union | moves_sources_union,
        wiki_root=wiki_root, git_root=git_root, soft_fail_gitignored=True,
    )
    referenced = [*other_resolved, *context_resolved]

    # Deduplicate while preserving order across the three lists.
    seen: dict[Path, None] = {}
    source_files: list[Path] = []
    for p in (*referenced, *(extra_files or [])):
        if p not in seen:
            seen[p] = None
            source_files.append(p)

    # Resolve move targets not already in the explicit batch refs;
    # use resolve_existing_paths so a missing target (incomplete implementation) is silently skipped rather than hard-failing code review.
    moves_targets_on_disk = resolve_existing_paths(
        [t for t in moves_targets_union if t not in other_refs and t not in context_only_refs],
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
            "[_review_code] warning: no source files resolved for the holistic scope; "
            "reviewer will only see plan content",
            file=sys.stderr,
        )

    ancestors_on_disk = resolve_existing_paths(
        [raw for raw in creates_union if raw not in other_refs and raw not in context_only_refs],
        project_root,
        root,
        wiki_root=wiki_root,
        git_root=git_root,
    )
    ancestors_on_disk = [p for p in ancestors_on_disk if p not in source_files]

    # 4. Reviewer + prompt
    reviewer_name = cfg["roles"]["code-review"]["holistic"]["reviewer"]
    if reviewer_name is None:
        raise ReviewError(
            "code-review holistic reviewer is null; "
            "the orchestrator should not have invoked this scope"
        )
    hub_dir = project_root
    registry = _reviewers.load(hub_dir)
    spec = _reviewers.resolve(registry, reviewer_name)

    template_name = "review-code-holistic"
    mode = "tool-use" if spec.get("tooluse") else "bulk"
    tool_rule = build_tool_rule(mode, agent_mode)
    roots = DisplayRoots(project_root=project_root, git_root=git_root, wiki_root=wiki_root)
    artefact_section = _build_artefact_section(
        mode, overview_path, batch_files, source_files, ancestors_on_disk,
        deletes_union,
        roots=roots,
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

    prompt_text = render_prompt(template_name, **prompt_kwargs)

    spec, reviewer_name = maybe_switch_spec_for_large_prompt(
        prompt_text, spec, reviewer_name, cfg, "code-review", "holistic", registry
    )

    return {
        "prompt_text": prompt_text,
        "model": spec.get("model"),
        "effort": spec.get("effort"),
        "round": round_n,
        "reviews_dir": reviews_dir,
        "scope": "holistic",
    }


def finalize(
    cfg: dict,
    slug: str,
    raw_text: str,
    *,
    round_n: int,
    reviews_dir: Path,
    mill_dir: Path,
    project_root: Path,
    wiki_root: Path,
    git_root: Path,
    actual_model: str | None = None,
    duration_s: float | None = None,
    tool_calls: int | None = None,
    cost_usd: float | None = None,
) -> ReviewResult:
    """Finalize a code review by parsing verdict and writing the review file.

    Args:
        raw_text: Raw review output from the reviewer.
        round_n: Round number.
        reviews_dir: Directory where review files are stored.
        actual_model: The model that actually produced this review, used to correct an unreliable
        self-reported ``reviewer_model:`` line before verdict parsing or disk write; passed through
        to ``finalize_scope`` on the success path only.
        duration_s: Orchestrator-supplied wall-clock seconds the round took (summed across every
        reviewer call in the round by the caller); threaded to ``finalize_scope`` on the success
        path, and injected into the raw parse-failure file on the ``except ReviewError`` path.
        tool_calls: Orchestrator-supplied tool-call count for the round; threaded the same way as
        ``duration_s``.
        cost_usd: Orchestrator-supplied dollar cost of the round; threaded the same way as
        ``duration_s``.

    Returns:
        ReviewResult with verdict, blocking count, and review entries.
    """
    blocking_classes = resolve_blocking_classes(cfg, "code", "holistic")
    try:
        review_entry = finalize_scope(
            reviews_dir, "code", round_n, raw_text, scope="holistic", actual_model=actual_model,
            blocking_classes=blocking_classes,
            duration_s=duration_s, tool_calls=tool_calls, cost_usd=cost_usd,
        )
    except ReviewError as exc:
        raw_text = apply_cost_metadata(
            raw_text, duration_s=duration_s, tool_calls=tool_calls, cost_usd=cost_usd
        )
        path = write_review_file(
            reviews_dir,
            "code",
            round_n,
            raw_text,
            scope="holistic",
        )
        return ReviewResult(
            type="code",
            round=round_n,
            verdict="ERROR",
            blocking_count=0,
            reviews=[{
                "scope": "holistic",
                "verdict": "ERROR",
                "file": str(path),
                "error": f"parse_verdict failed: {exc}",
                "findings": [],
                "session_id": None,
                "duration_s": duration_s,
                "tool_calls": tool_calls,
                "cost_usd": cost_usd,
                "error_kind": "reviewer",
            }],
        )

    return ReviewResult(
        type="code",
        round=round_n,
        verdict=review_entry["verdict"],
        blocking_count=review_entry["blocking_count"],
        nit_count=review_entry["nit_count"],
        findings=review_entry["findings"],
        reviews=[{
            "scope": "holistic",
            "verdict": review_entry["verdict"],
            "file": review_entry["file"],
            "findings": review_entry["findings"],
            "session_id": None,
            "duration_s": review_entry["duration_s"],
            "tool_calls": review_entry["tool_calls"],
            "cost_usd": review_entry["cost_usd"],
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
    extra_files: list[Path] | None = None,
    prior_notes: Path | None = None,
) -> ReviewResult:
    """Review the code produced for a task.

    ``extra_files`` are additional source files to bulk this round. ``prior_notes`` is a path to a file containing prior-round non-blocking
    findings digest.
    """
    with worktree_snapshot_guard(project_root, expected_paths=[cfg["paths"]["reviews_dir"]]):
        # Check if review is disabled
        reviews_dir = resolve_path(cfg["paths"]["reviews_dir"], slug)
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
                reviews=[{
                    "scope": "holistic",
                    "verdict": "APPROVE",
                    "file": None,
                    "skipped": True,
                    "findings": [],
                    "duration_s": None,
                    "tool_calls": None,
                    "cost_usd": None,
                }],
            )

        # Prepare
        prepare_result = prepare(
            cfg, slug, mill_dir=mill_dir, project_root=project_root,
            wiki_root=wiki_root, git_root=git_root, extra_files=extra_files,
            max_rounds=max_rounds, prior_notes=prior_notes,
        )
        prompt_text = prepare_result["prompt_text"]
        round_n = prepare_result["round"]
        reviews_dir = prepare_result["reviews_dir"]

        # Get spec for reviewer call
        reviewer_name = cfg["roles"]["code-review"]["holistic"]["reviewer"]
        registry = _reviewers.load(project_root)
        spec = _reviewers.resolve(registry, reviewer_name)
        timeout = cfg["llm"]["holistic_timeout"]
        spec, _ = maybe_switch_spec_for_large_prompt(
            prompt_text, spec, reviewer_name, cfg, "code-review", "holistic", registry
        )

        # Invoke reviewer
        try:
            res = _reviewer_single.run(spec, prompt_text, timeout=timeout)
            raw = extract_review_content(res.text)
            session_id = res.session_id
            duration_s = res.duration_s
            tool_calls = res.tool_calls
            cost_usd = res.cost_usd
        except LLMError as exc:
            return ReviewResult(
                type="code",
                round=round_n,
                verdict="ERROR",
                blocking_count=0,
                reviews=[{
                    "scope": "holistic",
                    "verdict": "ERROR",
                    "file": None,
                    "error": str(exc),
                    "findings": [],
                    "session_id": None,
                    "duration_s": getattr(exc, "duration_s", None),
                    "tool_calls": None,
                    "cost_usd": None,
                }],
            )

        # Try to parse verdict; if NEED_CONTEXT, retry
        try:
            verdict = parse_verdict(raw)
        except ReviewError as exc:
            raw = apply_cost_metadata(
                raw, duration_s=duration_s, tool_calls=tool_calls, cost_usd=cost_usd
            )
            path = write_review_file(
                reviews_dir,
                "code",
                round_n,
                raw,
                scope="holistic",
            )
            return ReviewResult(
                type="code",
                round=round_n,
                verdict="ERROR",
                blocking_count=0,
                reviews=[{
                    "scope": "holistic",
                    "verdict": "ERROR",
                    "file": str(path),
                    "error": f"parse_verdict failed: {exc}",
                    "findings": [],
                    "session_id": session_id,
                    "duration_s": duration_s,
                    "tool_calls": tool_calls,
                    "cost_usd": cost_usd,
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
                roots = DisplayRoots(
                    project_root=project_root, git_root=git_root, wiki_root=wiki_root
                )
                retry_prompt = (
                    build_reattached_section(missing_paths, roots=roots)
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
                    retry_res = _reviewer_single.run(
                        spec, retry_prompt, session_id=session_id, resume=True, timeout=timeout
                    )
                    raw = extract_review_content(retry_res.text)
                    session_id = retry_res.session_id
                    # The round genuinely cost both attempts -- fold the retry's metrics
                    # into the running totals (None-absorbing sum) rather than replacing them.
                    duration_s = sum_optional(duration_s, retry_res.duration_s)
                    tool_calls = sum_optional(tool_calls, retry_res.tool_calls)
                    cost_usd = sum_optional(cost_usd, retry_res.cost_usd)
                except LLMError as exc:
                    return ReviewResult(
                        type="code",
                        round=round_n,
                        verdict="ERROR",
                        blocking_count=0,
                        reviews=[{
                            "scope": "holistic",
                            "verdict": "ERROR",
                            "file": None,
                            "error": f"resume retry failed: {exc}",
                            "findings": [],
                            "session_id": None,
                            "duration_s": sum_optional(duration_s, getattr(exc, "duration_s", None)),
                            "tool_calls": tool_calls,
                            "cost_usd": cost_usd,
                        }],
                    )
                try:
                    verdict = parse_verdict(raw)
                except ReviewError as exc:
                    raw = apply_cost_metadata(
                        raw, duration_s=duration_s, tool_calls=tool_calls, cost_usd=cost_usd
                    )
                    path = write_review_file(
                        reviews_dir,
                        "code",
                        round_n,
                        raw,
                        scope="holistic",
                    )
                    return ReviewResult(
                        type="code",
                        round=round_n,
                        verdict="ERROR",
                        blocking_count=0,
                        reviews=[{
                            "scope": "holistic",
                            "verdict": "ERROR",
                            "file": str(path),
                            "error": f"parse_verdict failed: {exc}",
                            "findings": [],
                            "session_id": session_id,
                            "duration_s": duration_s,
                            "tool_calls": tool_calls,
                            "cost_usd": cost_usd,
                        }],
                    )

        # Finalize
        result = finalize(
            cfg, slug, raw, scope="holistic", round_n=round_n, reviews_dir=reviews_dir,
            mill_dir=mill_dir, project_root=project_root, wiki_root=wiki_root, git_root=git_root,
            duration_s=duration_s, tool_calls=tool_calls, cost_usd=cost_usd,
        )
        # Preserve session_id from reviewer call
        if result.reviews:
            result.reviews[0]["session_id"] = session_id
        return result
