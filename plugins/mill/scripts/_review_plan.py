"""
Review backend for plan artefacts.

The holistic review runs in bulk or tool-use mode.
An all-ERROR run returns ERROR (no raise) so the caller receives valid JSON even when the review
fails (#84, #228).

Public API:
    prepare(cfg, slug, *, mill_dir, project_root, wiki_root, git_root) -> dict
    Render prompt and resolve spec for the holistic scope; return prepare dict.
    finalize(cfg, slug, raw_text, *, round_n, reviews_dir, mill_dir, project_root, wiki_root, git_root) -> dict
    Parse verdict and write review file for the holistic scope; return review entry dict.
    run(cfg, slug, mill_dir, wiki_root, project_root, *, ...) -> ReviewResult
    Legacy holistic-only API; runs one holistic review round.

resolve_ref_paths is the canonical version from _review_common;
no local shadow is defined here.
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
    aggregate_verdict,
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
    finalize_scope,
    load_task_title,
    maybe_switch_spec_for_large_prompt,
    parse_batch_refs,
    extract_review_content,
    parse_missing_context,
    parse_verdict,
    read_constraints_md,
    render_prompt,
    resolve_blocking_classes,
    resolve_existing_paths,
    resolve_large_prompt_timeout,
    resolve_path,
    resolve_ref_paths,
    sum_optional,
    worktree_snapshot_guard,
    write_review_file,
)


def prepare(
    cfg: dict,
    slug: str,
    *,
    mill_dir: Path,
    project_root: Path,
    wiki_root: Path,
    git_root: Path,
    agent_mode: bool = False,
    reviewer_override: str | None = None,
    reviews_subdir: str | None = None,
    allow_missing_refs: bool = False,
) -> dict:
    """Prepare a plan review by rendering the holistic-scope prompt.

    Args:
        agent_mode: When True, the build_tool_rule call in this function returns the agent-mode
            cell (adds the single Write carve-out for the .out.md report).
            Defaults to False.
            This does NOT propagate to ``run()``'s own build_tool_rule call --
                that belongs to the `--stage full` path, which is a separate, non-prepare
                code path for plan review.
        reviewer_override: When not None, overrides the config-resolved plan-review holistic
            reviewer for this call only -- nothing is written back to config.
            Bypasses the `reviewer: null` disablement and skips the large-prompt auto-switch
                entirely.
        reviews_subdir: When not None, appended as a subdirectory under the config-resolved
            `reviews_dir` for this call only (e.g. `revise-2`) -- used by mill-plan's `--revise`
            re-entry mode to give a revision pass its own round-numbering namespace, distinct
            from the original approved pass's review files.
            Mirrors `reviewer_override`'s per-invocation-only contract; nothing is written back
            to config.
        allow_missing_refs: When True, a missing `Context:` ref not on disk (and not confirmed
            git-ignored) is dropped from the bulk with a stderr warning instead of hard-failing --
            per-invocation-only, mirroring `reviews_subdir`'s own contract; nothing is written
            back to config. Threaded into this function's `all_context_reads`
            call (#1083).

    Returns:
        Dict with keys: prompt_text, model, effort, round, reviews_dir, scope.
    """
    plan_dir = resolve_path(cfg["paths"]["plan_dir"], slug)
    reviews_dir = resolve_path(cfg["paths"]["reviews_dir"], slug)
    if reviews_subdir:
        reviews_dir = reviews_dir / reviews_subdir

    batch_files = sorted(
        p for p in plan_dir.glob("??-*.md") if p.name != "00-overview.md"
    )
    overview_path = plan_dir / "00-overview.md"
    if not overview_path.exists():
        raise ReviewError(f"Plan overview not found: {overview_path}")

    root = _load_root_from_overview(overview_path)
    creates_union = compute_creates_union(plan_dir)
    deletes_union = compute_deletes_union(plan_dir)
    # Move sources exist pre-implementation;
    # plan reviewers should see the file being relocated so they can verify the move is structurally sound.
    moves_sources_union, moves_targets_union = compute_moves_union(plan_dir)

    hub_dir = project_root
    registry = _reviewers.load(hub_dir)

    task_title = load_task_title(project_root, wiki_root, cfg, slug)
    constraints = read_constraints_md(project_root)

    round_n = discover_round(reviews_dir, "plan", "holistic")

    if reviewer_override is not None:
        try:
            holistic_spec = _reviewers.resolve_reviewer_override(
                registry, reviewer_override, reject_non_claude=True
            )
        except _reviewers.ReviewerError as exc:
            raise ReviewError(str(exc)) from exc
        holistic_name = reviewer_override
    else:
        holistic_name = cfg["roles"]["plan-review"]["holistic"]["reviewer"]
        if holistic_name is None:
            raise ReviewError("plan-review holistic reviewer is null")
        holistic_spec = _reviewers.resolve(registry, holistic_name)

    # Union all Context:/Edits:/Creates: across all batch files.
    # Context: refs are split from Edits:/Creates:/Deletes: refs so only the former can soft-fail on a confirmed git-ignore hit (#733) -- a missing Edits:/Creates:/Deletes: ref still hard-fails unconditionally, since those name files the batch is expected to produce or touch.
    all_context_refs: dict[str, None] = {}
    all_other_refs: dict[str, None] = {}
    for batch_path in batch_files:
        for ref in parse_batch_refs(batch_path, fields=("Context",)):
            all_context_refs[ref] = None
        for ref in parse_batch_refs(batch_path, fields=("Edits", "Creates", "Deletes")):
            all_other_refs[ref] = None
    all_raw_refs = {**all_context_refs, **all_other_refs}
    # Merge move targets into creates suppression set so downstream batches referencing a move target don't raise ReviewError.
    combined_creates = creates_union | moves_targets_union
    all_other_reads = resolve_ref_paths(
        list(all_other_refs.keys()), project_root, root,
        creates_union=combined_creates, deletes_union=deletes_union,
        wiki_root=wiki_root, git_root=git_root, caller_label="_review_plan",
    )
    all_context_reads = resolve_ref_paths(
        list(all_context_refs.keys()), project_root, root,
        creates_union=combined_creates, deletes_union=deletes_union,
        wiki_root=wiki_root, git_root=git_root, caller_label="_review_plan",
        soft_fail_gitignored=True,
        allow_missing_refs=allow_missing_refs,
    )
    all_reads = [*all_other_reads, *all_context_reads]

    all_creates_on_disk = resolve_existing_paths(
        [r for r in combined_creates if r not in all_raw_refs],
        project_root,
        root,
        wiki_root=wiki_root,
        git_root=git_root,
    )
    reads_set = {*all_reads, overview_path, *batch_files}
    all_creates_on_disk = [p for p in all_creates_on_disk if p not in reads_set]

    # Resolve move sources for the holistic reviewer so it sees the full rename picture.
    holistic_already_included = reads_set | set(all_creates_on_disk)
    holistic_moves_on_disk = resolve_existing_paths(
        [s for s in moves_sources_union if s not in all_raw_refs],
        project_root,
        root,
        wiki_root=wiki_root,
        git_root=git_root,
    )
    holistic_moves_on_disk = [p for p in holistic_moves_on_disk if p not in holistic_already_included]

    holistic_mode = "tool-use" if holistic_spec.get("tooluse") else "bulk"
    tool_rule = build_tool_rule(holistic_mode, agent_mode)

    roots = DisplayRoots(project_root=project_root, git_root=git_root, wiki_root=wiki_root)

    manifest = build_manifest_section(
        [overview_path, *batch_files, *all_reads, *all_creates_on_disk, *holistic_moves_on_disk],
        roots=roots,
    )

    if holistic_mode == "tool-use":
        batch_list = "\n".join(f"- `{roots.render(p)}`" for p in batch_files) or "(none)"
        read_list = "\n".join(
            f"- `{roots.render(p)}`"
            for p in [*all_reads, *all_creates_on_disk, *holistic_moves_on_disk]
        ) or "(none)"
        artefact_section = (
            f"{manifest}\n\n"
            f"## Plan files to review\n"
            f"- Overview: `{roots.render(overview_path)}`\n"
            f"- Batches:\n{batch_list}\n\n"
            f"Read the overview and every batch listed above. Then read the "
            f"source files referenced across all batches:\n{read_list}\n\n"
            f"Every path listed above is relative to the root stated in the "
            f"`## Path roots` block above and must be resolved against it before reading."
        )
    else:
        bulked_all = bulk_files(
            [overview_path, *batch_files, *all_reads, *all_creates_on_disk, *holistic_moves_on_disk],
            roots=roots,
        )
        artefact_section = (
            f"{manifest}\n\n"
            f"## Plan content (overview + all batches + referenced files + cross-batch ancestor creates)\n"
            f"{bulked_all}"
        )
    if deletes_union:
        artefact_section += "\n\n" + build_deletes_section(sorted(deletes_union))

    prompt_text = render_prompt(
        "review-plan-holistic",
        task_title=task_title,
        tool_rule=tool_rule,
        artefact_section=artefact_section,
        constraints=constraints,
        round=round_n,
        reviewer_model=holistic_name,
    )

    if reviewer_override is None:
        holistic_spec, holistic_name = maybe_switch_spec_for_large_prompt(
            prompt_text, holistic_spec, holistic_name, cfg, "plan-review", "holistic", registry
        )

    return {
        "prompt_text": prompt_text,
        "model": holistic_spec.get("model"),
        "effort": holistic_spec.get("effort"),
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
) -> dict:
    """Finalize a holistic plan review;
return a review entry dict.

    Args:
        raw_text: Raw review output from the reviewer.
        round_n: Round number.
        reviews_dir: Directory where review files are stored.
        actual_model: The model that actually produced this review, used to correct an unreliable
        self-reported ``reviewer_model:`` line before verdict parsing or disk write; passed through
        to ``finalize_scope`` on the success path only.
        duration_s: Orchestrator-supplied wall-clock seconds the round took (summed across every
            reviewer call in the round by the caller); threaded to ``finalize_scope`` on the
            success path, and injected into the raw parse-failure file on the ``except
            ReviewError`` path.
        tool_calls: Orchestrator-supplied tool-call count for the round; threaded the same way as
            ``duration_s``.
        cost_usd: Orchestrator-supplied dollar cost of the round; threaded the same way as
            ``duration_s``.

    Returns:
        Review entry dict for aggregation: {"scope", "round", "verdict", "blocking_count", "file",
        "session_id"}.
    """
    blocking_classes = resolve_blocking_classes(cfg, "plan", "holistic")

    try:
        review_entry = finalize_scope(
            reviews_dir, "plan", round_n, raw_text, scope="holistic", actual_model=actual_model,
            blocking_classes=blocking_classes,
            duration_s=duration_s, tool_calls=tool_calls, cost_usd=cost_usd,
        )
    except ReviewError as exc:
        raw_text = apply_cost_metadata(
            raw_text, duration_s=duration_s, tool_calls=tool_calls, cost_usd=cost_usd
        )
        path = write_review_file(
            reviews_dir, "plan", round_n, raw_text, scope="holistic"
        )
        return {
            "scope": "holistic",
            "round": round_n,
            "verdict": "ERROR",
            "blocking_count": 0,
            "nit_count": 0,
            "file": str(path),
            "error": f"parse_verdict failed: {exc}",
            "session_id": None,
            "findings": [],
            "duration_s": duration_s,
            "tool_calls": tool_calls,
            "cost_usd": cost_usd,
            "error_kind": "reviewer",
        }

    return {
        "scope": "holistic",
        "round": round_n,
        "verdict": review_entry["verdict"],
        "blocking_count": review_entry["blocking_count"],
        "nit_count": review_entry["nit_count"],
        "file": review_entry["file"],
        "session_id": None,
        "findings": review_entry["findings"],
        "duration_s": review_entry["duration_s"],
        "tool_calls": review_entry["tool_calls"],
        "cost_usd": review_entry["cost_usd"],
    }


def run(
    cfg: dict,
    slug: str,
    mill_dir: Path,
    wiki_root: Path,
    project_root: Path,
    *,
    git_root: Path,
    max_rounds: int | None = None,
    reviewer_override: str | None = None,
    reviews_subdir: str | None = None,
    allow_missing_refs: bool = False,
) -> ReviewResult:
    """Run a holistic plan review.

    Steps:
    1. Resolve plan_dir and reviews_dir.
    2. Verify overview exists;
        collect batch files.
    3. Load the holistic reviewer.
    4. Holistic review (rounds=0 returns an APPROVE stub).
    5. Aggregate and return ReviewResult (all-ERROR -> ERROR; no raise).

    Args:
        max_rounds: Overrides `cfg["roles"]["plan-review"]["holistic"]["rounds"]` for this call.
        reviewer_override: When not None, overrides the config-resolved plan-review holistic
            reviewer for this call only -- nothing is written back to config.
            Bypasses the `holistic_name is None` disablement in step 3,
            but not the separate `cfg["roles"]["plan-review"]["holistic"]["rounds"] == 0` gate,
                which is checked independently and still applies.
            Skips the large-prompt auto-switch entirely.
        reviews_subdir: When not None, appended as a subdirectory under the config-resolved
            `reviews_dir` for this call only (e.g. `revise-2`) -- used by mill-plan's `--revise`
            re-entry mode to give a revision pass its own round-numbering namespace, distinct
            from the original approved pass's review files.
            Mirrors `reviewer_override`'s per-invocation-only contract; nothing is written back
            to config.
        allow_missing_refs: When True, a missing `Context:` ref not on disk (and not confirmed
            git-ignored) is dropped from the bulk with a stderr warning instead of hard-failing --
            per-invocation-only, mirroring `reviews_subdir`'s own contract; nothing is written
            back to config. Threaded into this function's own `all_context_reads` call (#1083).
    """
    with worktree_snapshot_guard(project_root, expected_paths=[cfg["paths"]["reviews_dir"]]):
        # 1. Paths and round
        plan_dir = resolve_path(cfg["paths"]["plan_dir"], slug)
        reviews_dir = resolve_path(cfg["paths"]["reviews_dir"], slug)
        if reviews_subdir:
            reviews_dir = reviews_dir / reviews_subdir
        holistic_max_rounds = max_rounds if max_rounds is not None else cfg["roles"]["plan-review"]["holistic"]["rounds"]
        holistic_timeout = cfg["llm"]["holistic_timeout"]

        print(
            f"[_review_plan] slug={slug!r} plan_dir={plan_dir} "
            f"holistic_max_rounds={holistic_max_rounds}",
            file=sys.stderr,
        )

        # 2. Overview and batch files
        overview_path = plan_dir / "00-overview.md"
        if not overview_path.exists():
            raise ReviewError(f"Plan overview not found: {overview_path}")

        batch_files = sorted(
            p for p in plan_dir.glob("??-*.md") if p.name != "00-overview.md"
        )
        print(
            f"[_review_plan] found {len(batch_files)} batch file(s)",
            file=sys.stderr,
        )

        root = _load_root_from_overview(overview_path)
        creates_union = compute_creates_union(plan_dir)
        deletes_union = compute_deletes_union(plan_dir)
        # Move sources exist pre-implementation;
        # plan review should see the file being relocated so the reviewer can verify the move intent.
        moves_sources_union, moves_targets_union = compute_moves_union(plan_dir)

        # 3. Load reviewers via registry
        hub_dir = project_root
        registry = _reviewers.load(hub_dir)

        holistic_name = cfg["roles"]["plan-review"]["holistic"]["reviewer"]
        if reviewer_override is not None and cfg["roles"]["plan-review"]["holistic"]["rounds"] != 0:
            # An explicit --reviewer bypasses the `holistic_name is None` disablement below,
            # but not the independent `rounds == 0` gate -- a round-0 config still returns the APPROVE stub even with an override, per the overview's null-bypass Decision.
            try:
                holistic_spec = _reviewers.resolve_reviewer_override(
                    registry, reviewer_override, reject_non_claude=False
                )
            except _reviewers.ReviewerError as exc:
                raise ReviewError(str(exc)) from exc
            holistic_name = reviewer_override
        elif holistic_name is None:
            raise ReviewError("plan-review holistic reviewer is null")
        else:
            holistic_spec = _reviewers.resolve(registry, holistic_name)

        task_title = load_task_title(project_root, wiki_root, cfg, slug)
        constraints = read_constraints_md(project_root)

        reviews: list[dict] = []

        # 4. Holistic review

        if holistic_max_rounds == 0:
            print("[_review_plan] holistic rounds=0 -- review disabled, returning APPROVE stub", file=sys.stderr)
            return ReviewResult(
                type="plan", round=0, verdict="APPROVE", blocking_count=0,
                reviews=[{"scope": "holistic", "verdict": "APPROVE", "file": None, "skipped": True, "findings": []}],
            )
        round_n = discover_round(reviews_dir, "plan", "holistic")
        if round_n > holistic_max_rounds:
            raise ReviewError(
                f"Round {round_n} exceeds max {holistic_max_rounds} for plan review (holistic)"
            )
        print("[_review_plan] running holistic review", file=sys.stderr)

        # Union all Context:/Edits:/Creates: across all batch files.
        # Context: refs are split from Edits:/Creates:/Deletes: refs so only the former can soft-fail on a confirmed git-ignore hit (#733) -- a missing Edits:/Creates:/Deletes: ref still hard-fails unconditionally, since those name files the batch is expected to produce or touch.
        all_context_refs: dict[str, None] = {}
        all_other_refs: dict[str, None] = {}
        for batch_path in batch_files:
            for ref in parse_batch_refs(batch_path, fields=("Context",)):
                all_context_refs[ref] = None
            for ref in parse_batch_refs(batch_path, fields=("Edits", "Creates", "Deletes")):
                all_other_refs[ref] = None
        all_raw_refs = {**all_context_refs, **all_other_refs}
        # Merge move targets into creates suppression set so downstream batches referencing a move target don't raise ReviewError.
        combined_creates = creates_union | moves_targets_union
        all_other_reads = resolve_ref_paths(
            list(all_other_refs.keys()), project_root, root,
            creates_union=combined_creates, deletes_union=deletes_union,
            wiki_root=wiki_root, git_root=git_root, caller_label="_review_plan",
        )
        all_context_reads = resolve_ref_paths(
            list(all_context_refs.keys()), project_root, root,
            creates_union=combined_creates, deletes_union=deletes_union,
            wiki_root=wiki_root, git_root=git_root, caller_label="_review_plan",
            soft_fail_gitignored=True,
            allow_missing_refs=allow_missing_refs,
        )
        all_reads = [*all_other_reads, *all_context_reads]

        all_creates_on_disk = resolve_existing_paths(
            [r for r in combined_creates if r not in all_raw_refs],
            project_root,
            root,
            wiki_root=wiki_root,
            git_root=git_root,
        )
        reads_set = {*all_reads, overview_path, *batch_files}
        all_creates_on_disk = [p for p in all_creates_on_disk if p not in reads_set]

        # Add move sources to the holistic bulk so the reviewer sees the file being relocated across all batches in a single prompt.
        run_hol_already_included = reads_set | set(all_creates_on_disk)
        run_hol_moves_on_disk = resolve_existing_paths(
            [s for s in moves_sources_union if s not in all_raw_refs],
            project_root,
            root,
            wiki_root=wiki_root,
            git_root=git_root,
        )
        run_hol_moves_on_disk = [p for p in run_hol_moves_on_disk if p not in run_hol_already_included]

        holistic_mode = "tool-use" if holistic_spec.get("tooluse") else "bulk"
        tool_rule = build_tool_rule(holistic_mode)

        run_hol_roots = DisplayRoots(project_root=project_root, git_root=git_root, wiki_root=wiki_root)

        manifest = build_manifest_section(
            [overview_path, *batch_files, *all_reads, *all_creates_on_disk, *run_hol_moves_on_disk],
            roots=run_hol_roots,
        )

        if holistic_mode == "tool-use":
            batch_list = "\n".join(f"- `{run_hol_roots.render(p)}`" for p in batch_files) or "(none)"
            read_list = "\n".join(
                f"- `{run_hol_roots.render(p)}`"
                for p in [*all_reads, *all_creates_on_disk, *run_hol_moves_on_disk]
            ) or "(none)"
            artefact_section = (
                f"{manifest}\n\n"
                f"## Plan files to review\n"
                f"- Overview: `{run_hol_roots.render(overview_path)}`\n"
                f"- Batches:\n{batch_list}\n\n"
                f"Read the overview and every batch listed above. Then read the "
                f"source files referenced across all batches:\n{read_list}\n\n"
                f"Every path listed above is relative to the root stated in the "
                f"`## Path roots` block above and must be resolved against it before reading."
            )
        else:
            bulked_all = bulk_files(
                [overview_path, *batch_files, *all_reads, *all_creates_on_disk, *run_hol_moves_on_disk],
                roots=run_hol_roots,
            )
            artefact_section = (
                f"{manifest}\n\n"
                f"## Plan content (overview + all batches + referenced files + cross-batch ancestor creates)\n"
                f"{bulked_all}"
            )
        if deletes_union:
            artefact_section += "\n\n" + build_deletes_section(sorted(deletes_union))

        prompt_text = render_prompt(
            "review-plan-holistic",
            task_title=task_title,
            tool_rule=tool_rule,
            artefact_section=artefact_section,
            constraints=constraints,
            round=round_n,
            reviewer_model=holistic_name,
        )

        if reviewer_override is None:
            holistic_spec, holistic_name = maybe_switch_spec_for_large_prompt(
                prompt_text, holistic_spec, holistic_name, cfg, "plan-review", "holistic", registry
            )

        resolved_timeout = resolve_large_prompt_timeout(
            prompt_text, cfg, "plan-review", "holistic", holistic_timeout
        )

        try:
            res = _reviewer_single.run(holistic_spec, prompt_text, timeout=resolved_timeout)
            raw = extract_review_content(res.text)
            session_id = res.session_id
            duration_s = res.duration_s
            tool_calls = res.tool_calls
            cost_usd = res.cost_usd
        except LLMError as exc:
            reviews.append({
                "scope": "holistic",
                "round": round_n,
                "verdict": "ERROR",
                "blocking_count": 0,
                "nit_count": 0,
                "file": None,
                "error": str(exc),
                "session_id": None,
                "findings": [],
                "duration_s": getattr(exc, "duration_s", None),
                "tool_calls": None,
                "cost_usd": None,
            })
        else:
            try:
                verdict = parse_verdict(raw)

                if verdict == "NEED_CONTEXT":
                    missing_raw = parse_missing_context(raw)
                    missing_paths = resolve_existing_paths(
                        missing_raw, project_root, root, wiki_root=wiki_root, git_root=git_root
                    )
                    if missing_paths:
                        retry_prompt = (
                            build_reattached_section(missing_paths, roots=run_hol_roots)
                            + "\n\n"
                            + "Please continue your review using the re-attached files above. "
                            + "The original prompt is already in your session context."
                        )
                        print(
                            f"[_review_plan] holistic NEED_CONTEXT round-1; retrying with resume "
                            f"({len(missing_paths)} re-attached file(s)) session={(session_id or '?')[:8]}",
                            file=sys.stderr,
                        )
                        try:
                            retry_res = _reviewer_single.run(
                                holistic_spec, retry_prompt, session_id=session_id, resume=True, timeout=resolved_timeout
                            )
                            raw = extract_review_content(retry_res.text)
                            session_id = retry_res.session_id
                            # The round genuinely cost both attempts -- fold the retry's
                            # metrics into the running totals (None-absorbing sum) rather
                            # than replacing them.
                            duration_s = sum_optional(duration_s, retry_res.duration_s)
                            tool_calls = sum_optional(tool_calls, retry_res.tool_calls)
                            cost_usd = sum_optional(cost_usd, retry_res.cost_usd)
                        except LLMError as exc:
                            reviews.append({
                                "scope": "holistic",
                                "round": round_n,
                                "verdict": "ERROR",
                                "blocking_count": 0,
                                "nit_count": 0,
                                "file": None,
                                "error": f"resume retry failed: {exc}",
                                "session_id": None,
                                "findings": [],
                                "duration_s": sum_optional(duration_s, getattr(exc, "duration_s", None)),
                                "tool_calls": tool_calls,
                                "cost_usd": cost_usd,
                            })
                            # error entry appended above; else branch writes the review file on success
                        else:
                            # Second NEED_CONTEXT propagates to caller untouched.
                            review_entry = finalize_scope(
                                reviews_dir, "plan", round_n, raw, scope="holistic",
                                blocking_classes=resolve_blocking_classes(cfg, "plan", "holistic"),
                                duration_s=duration_s, tool_calls=tool_calls, cost_usd=cost_usd,
                            )
                            print(
                                f"[_review_plan] holistic: verdict={review_entry['verdict']} "
                                f"file={Path(review_entry['file']).name}",
                                file=sys.stderr,
                            )
                            reviews.append({
                                "scope": "holistic",
                                "round": round_n,
                                "verdict": review_entry["verdict"],
                                "blocking_count": review_entry["blocking_count"],
                                "nit_count": review_entry["nit_count"],
                                "file": review_entry["file"],
                                "session_id": session_id,
                                "findings": review_entry["findings"],
                                "duration_s": review_entry["duration_s"],
                                "tool_calls": review_entry["tool_calls"],
                                "cost_usd": review_entry["cost_usd"],
                            })
                    else:
                        # No resolvable paths to re-attach — propagate NEED_CONTEXT.
                        review_entry = finalize_scope(
                            reviews_dir, "plan", round_n, raw, scope="holistic",
                            blocking_classes=resolve_blocking_classes(cfg, "plan", "holistic"),
                            duration_s=duration_s, tool_calls=tool_calls, cost_usd=cost_usd,
                        )
                        print(
                            f"[_review_plan] holistic: verdict={review_entry['verdict']} "
                            f"file={Path(review_entry['file']).name}",
                            file=sys.stderr,
                        )
                        reviews.append({
                            "scope": "holistic",
                            "round": round_n,
                            "verdict": review_entry["verdict"],
                            "blocking_count": review_entry["blocking_count"],
                            "nit_count": review_entry["nit_count"],
                            "file": review_entry["file"],
                            "session_id": session_id,
                            "findings": review_entry["findings"],
                            "duration_s": review_entry["duration_s"],
                            "tool_calls": review_entry["tool_calls"],
                            "cost_usd": review_entry["cost_usd"],
                        })
                else:
                    review_entry = finalize_scope(
                        reviews_dir, "plan", round_n, raw, scope="holistic",
                        blocking_classes=resolve_blocking_classes(cfg, "plan", "holistic"),
                        duration_s=duration_s, tool_calls=tool_calls, cost_usd=cost_usd,
                    )
                    print(
                        f"[_review_plan] holistic: verdict={review_entry['verdict']} "
                        f"file={Path(review_entry['file']).name}",
                        file=sys.stderr,
                    )
                    reviews.append({
                        "scope": "holistic",
                        "round": round_n,
                        "verdict": review_entry["verdict"],
                        "blocking_count": review_entry["blocking_count"],
                        "nit_count": review_entry["nit_count"],
                        "file": review_entry["file"],
                        "session_id": session_id,
                        "findings": review_entry["findings"],
                        "duration_s": review_entry["duration_s"],
                        "tool_calls": review_entry["tool_calls"],
                        "cost_usd": review_entry["cost_usd"],
                    })
            except ReviewError as exc:
                raw = apply_cost_metadata(
                    raw, duration_s=duration_s, tool_calls=tool_calls, cost_usd=cost_usd
                )
                path = write_review_file(reviews_dir, "plan", round_n, raw, scope="holistic")
                reviews.append({
                    "scope": "holistic",
                    "round": round_n,
                    "verdict": "ERROR",
                    "blocking_count": 0,
                    "nit_count": 0,
                    "file": str(path),
                    "error": f"parse_verdict failed: {exc}",
                    "session_id": session_id,
                    "findings": [],
                    "duration_s": duration_s,
                    "tool_calls": tool_calls,
                    "cost_usd": cost_usd,
                })

        aggregate = aggregate_verdict([r["verdict"] for r in reviews])
        if reviews and all(r.get("verdict") == "ERROR" for r in reviews):
            aggregate = "ERROR"
        agg_round = max(r["round"] for r in reviews) if reviews else 0
        aggregate_blocking = sum(r.get("blocking_count", 0) for r in reviews)
        aggregate_nit = sum(r.get("nit_count", 0) for r in reviews)
        aggregate_findings = [f for r in reviews for f in r.get("findings", [])]
        return ReviewResult(
            type="plan",
            round=agg_round,
            verdict=aggregate,
            blocking_count=aggregate_blocking,
            nit_count=aggregate_nit,
            findings=aggregate_findings,
            reviews=reviews,
        )
