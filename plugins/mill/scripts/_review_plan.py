"""
Review backend for plan artefacts.

Per-batch reviews run in parallel via ThreadPoolExecutor (bulk mode).
An optional holistic review follows (also bulk). Results are aggregated
worst-case; all-ERROR runs return REQUEST_CHANGES (no raise) so the
caller receives valid JSON even when every sub-review fails (#84).

Public API:
    run(cfg, slug, mill_dir, wiki_root, project_root) -> ReviewResult

resolve_ref_paths is the canonical version from _review_common; no local
shadow is defined here.
"""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from _llm_claude import LLMError
from _review_common import (
    RE_BATCH,
    RE_SIMPLE,
    ReviewError,
    ReviewResult,
    _load_root_from_overview,
    aggregate_verdict,
    build_deletes_section,
    build_manifest_section,
    build_reattached_section,
    build_tool_rule,
    bulk_files,
    compute_creates_union,
    compute_deletes_union,
    detect_resume_round,
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


def _scan_approved_batches(reviews_dir: Path) -> dict[str, dict]:
    """Scan reviews_dir for plan-batch reviews; return {stem: carryforward_entry} for approved batches.

    For each unique batch stem found via RE_BATCH (with type=='plan'),
    find the file with the highest round number, parse its verdict, and
    if APPROVE, build a carryforward dict to splice into reviews[].
    RE_SIMPLE is checked first per file to avoid mis-attributing a plan-
    holistic review to a batch.
    """
    if not reviews_dir.exists():
        return {}

    # Group by batch stem: {stem: (round_n, path)}
    best: dict[str, tuple[int, Path]] = {}
    for entry in reviews_dir.iterdir():
        if not entry.is_file():
            continue
        name = entry.name
        m_simple = RE_SIMPLE.match(name)
        if m_simple:
            continue  # holistic or non-batch file — skip
        m_batch = RE_BATCH.match(name)
        if m_batch and m_batch.group("type") == "plan":
            batch_stem = m_batch.group("batch")
            n = int(m_batch.group("n"))
            if batch_stem not in best or n > best[batch_stem][0]:
                best[batch_stem] = (n, entry)

    result: dict[str, dict] = {}
    for batch_stem, (n, path) in best.items():
        try:
            raw = path.read_text(encoding="utf-8")
            verdict = parse_verdict(raw)
        except ReviewError:
            print(
                f"[_review_plan] warn: could not parse verdict in {path.name}; will re-review",
                file=sys.stderr,
            )
            continue
        if verdict == "APPROVE":
            result[batch_stem] = {
                "scope": batch_stem,
                "round": n,
                "verdict": "APPROVE",
                "blocking_count": 0,
                "file": str(path),
                "session_id": None,
            }

    return result


def _review_one_batch(
    batch_path: Path,
    overview_path: Path,
    reviews_dir: Path,
    max_rounds: int,
    task_title: str,
    constraints: str,
    batch_reviewer_name: str,
    batch_reviewer,
    project_root: Path,
    root: str | None,
    creates_union: set[str],
    deletes_union: set[str],
    wiki_root: Path,
    bulk_timeout: int | None,
) -> dict:
    """Review a single plan batch file. Returns a reviews[] entry dict."""
    try:
        round_n = discover_round(reviews_dir, "plan", batch_path.stem)
        if round_n > max_rounds:
            raise ReviewError(
                f"Round {round_n} exceeds max {max_rounds} for plan review (batch={batch_path.stem})"
            )

        raw_refs = parse_batch_refs(batch_path)
        reads = resolve_ref_paths(
            raw_refs, project_root, root,
            creates_union=creates_union, deletes_union=deletes_union,
            wiki_root=wiki_root, caller_label="_review_plan",
        )

        ancestors_on_disk = resolve_existing_paths(
            [raw for raw in creates_union if raw not in raw_refs],
            project_root,
            root,
            wiki_root=wiki_root,
        )
        reads_set = {*reads, overview_path, batch_path}
        ancestors_on_disk = [p for p in ancestors_on_disk if p not in reads_set]

        tool_rule = build_tool_rule(batch_reviewer.MODE)

        all_bulked = [overview_path, batch_path, *reads, *ancestors_on_disk]
        manifest = build_manifest_section(all_bulked)

        if batch_reviewer.MODE == "tool-use":
            read_list = "\n".join(f"- {p}" for p in [*reads, *ancestors_on_disk]) or "(none)"
            artefact_section = (
                f"{manifest}\n\n"
                f"## Plan files to review\n"
                f"- Overview: `{overview_path}`\n"
                f"- Batch:    `{batch_path}`\n\n"
                f"Read both files above. Then read the source files listed under "
                f"`Reads:` / `Modifies:` / `Creates:` in the batch + cross-batch creates "
                f"that exist on disk:\n{read_list}"
            )
        else:
            bulked = bulk_files(all_bulked)
            artefact_section = (
                f"{manifest}\n\n"
                f"## Plan content (overview + batch + Reads/Modifies/Creates files + cross-batch ancestor creates)\n"
                f"{bulked}"
            )
        if deletes_union:
            artefact_section += "\n\n" + build_deletes_section(sorted(deletes_union))

        prompt_text = render_prompt(
            "review-plan-batch",
            task_title=task_title,
            batch_name=batch_path.stem,
            tool_rule=tool_rule,
            artefact_section=artefact_section,
            constraints=constraints,
            round=round_n,
            reviewer_model=batch_reviewer_name,
        )

        try:
            raw, session_id = batch_reviewer.run(prompt_text, timeout=bulk_timeout)
        except LLMError as exc:
            return {
                "scope": batch_path.stem,
                "round": round_n,
                "verdict": "ERROR",
                "blocking_count": 0,
                "file": None,
                "error": str(exc),
                "session_id": None,
            }

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
                    f"[_review_plan] batch {batch_path.stem} NEED_CONTEXT round-1; retrying with resume "
                    f"({len(missing_paths)} re-attached file(s)) session={(session_id or '?')[:8]}",
                    file=sys.stderr,
                )
                try:
                    raw, session_id = batch_reviewer.run(
                        retry_prompt, session_id=session_id, resume=True, timeout=bulk_timeout
                    )
                except LLMError as exc:
                    return {
                        "scope": batch_path.stem,
                        "round": round_n,
                        "verdict": "ERROR",
                        "blocking_count": 0,
                        "file": None,
                        "error": f"resume retry failed: {exc}",
                        "session_id": None,
                    }
                verdict = parse_verdict(raw)
                # Second NEED_CONTEXT propagates to caller untouched.

        blocking_count = parse_blocking_count(raw, severity="BLOCKING")
        path = write_review_file(
            reviews_dir, "plan", round_n, raw, scope=batch_path.stem
        )
        print(
            f"[_review_plan] batch {batch_path.stem}: verdict={verdict} file={path.name}",
            file=sys.stderr,
        )
        return {
            "scope": batch_path.stem,
            "round": round_n,
            "verdict": verdict,
            "blocking_count": blocking_count,
            "file": str(path),
            "session_id": session_id,
        }
    except ReviewError as exc:
        return {
            "scope": batch_path.stem,
            "round": round_n,
            "verdict": "ERROR",
            "blocking_count": 0,
            "file": None,
            "error": str(exc),
            "session_id": None,
        }


def run(
    cfg: dict,
    slug: str,
    mill_dir: Path,
    wiki_root: Path,
    project_root: Path,
    *,
    max_rounds: int | None = None,
    holistic_only: bool = False,
    no_holistic: bool = False,
) -> ReviewResult:
    """Run plan review: parallel per-batch + optional holistic.

    Steps:
    1. Resolve plan_dir and reviews_dir; discover round.
    2. Verify overview exists; collect batch files.
    3. Load reviewers; verify bulk mode.
    4. Parallel per-batch reviews (skipped if batch_files is empty or holistic_only).
       Mid-round resume fires holistic only when per-batch files exist but holistic is missing.
    5. Holistic review (skipped if cfg.review.plan.holistic is None or no_holistic).
    6. Aggregate and return ReviewResult (all-ERROR → REQUEST_CHANGES; no raise).
    """
    if holistic_only and no_holistic:
        raise ReviewError("--holistic-only and --no-holistic are mutually exclusive")

    # 1. Paths and round
    plan_dir = resolve_path(cfg["paths"]["plan_dir"], slug)
    reviews_dir = resolve_path(cfg["paths"]["reviews_dir"], slug)
    max_rounds = max_rounds if max_rounds is not None else cfg["review"]["plan"]["rounds"]
    bulk_timeout = cfg["llm"]["bulk_timeout"]
    holistic_timeout = cfg["llm"]["holistic_timeout"]

    print(
        f"[_review_plan] slug={slug!r} plan_dir={plan_dir} max_rounds={max_rounds}",
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

    # 3. Load reviewers (accept bulk or tool-use)
    batch_reviewer_name = cfg["review"]["plan"]["batch"]
    batch_reviewer = load_reviewer(batch_reviewer_name)

    holistic_name = cfg["review"]["plan"].get("holistic")
    if holistic_name is not None:
        holistic_reviewer = load_reviewer(holistic_name)
    else:
        holistic_reviewer = None

    task_title = load_task_title(mill_dir, slug)
    constraints = read_constraints_md(project_root)

    reviews: list[dict] = []

    resume_round = detect_resume_round(reviews_dir, "plan")

    # 4. Per-batch parallel section (skipped when holistic_only=True)
    if not holistic_only:
        if resume_round is not None:
            # Mid-round resume: per-batch files for this round already exist on disk;
            # load them directly and fall through to the holistic.
            _disk_reviews: list[dict] = []
            if reviews_dir.exists():
                for _entry in reviews_dir.iterdir():
                    if not _entry.is_file():
                        continue
                    _m_simple = RE_SIMPLE.match(_entry.name)
                    if _m_simple:
                        continue
                    _m_batch = RE_BATCH.match(_entry.name)
                    if (
                        _m_batch
                        and _m_batch.group("type") == "plan"
                        and int(_m_batch.group("n")) == resume_round
                    ):
                        _batch_stem = _m_batch.group("batch")
                        _file_text = _entry.read_text(encoding="utf-8")
                        try:
                            _parsed_verdict = parse_verdict(_file_text)
                        except ReviewError:
                            _parsed_verdict = "ERROR"
                        _parsed_blocking = parse_blocking_count(_file_text, severity="BLOCKING")
                        _disk_reviews.append({
                            "scope": _batch_stem,
                            "round": resume_round,
                            "verdict": _parsed_verdict,
                            "blocking_count": _parsed_blocking,
                            "file": str(_entry),
                            "session_id": None,
                        })
            print(
                f"[_review_plan] resuming round {resume_round} from {len(_disk_reviews)} "
                f"on-disk per-batch files; firing holistic only",
                file=sys.stderr,
            )
            reviews.extend(_disk_reviews)
        else:
            # Normal path: skip-approved scan + ThreadPoolExecutor.
            approved_carry = _scan_approved_batches(reviews_dir)
            batch_files_to_review = [b for b in batch_files if b.stem not in approved_carry]
            if approved_carry:
                print(
                    f"[_review_plan] skipping {len(approved_carry)} already-approved batch(es): "
                    f"{sorted(approved_carry.keys())}",
                    file=sys.stderr,
                )

            if batch_files:
                order = {b.stem: i for i, b in enumerate(batch_files)}

                if batch_files_to_review:
                    futures_map: dict = {}
                    with ThreadPoolExecutor(max_workers=len(batch_files_to_review)) as ex:
                        for batch_path in batch_files_to_review:
                            future = ex.submit(
                                _review_one_batch,
                                batch_path,
                                overview_path,
                                reviews_dir,
                                max_rounds,
                                task_title,
                                constraints,
                                batch_reviewer_name,
                                batch_reviewer,
                                project_root,
                                root,
                                creates_union,
                                deletes_union,
                                wiki_root,
                                bulk_timeout,
                            )
                            futures_map[future] = batch_path

                        for future in as_completed(futures_map):
                            entry = future.result()
                            reviews.append(entry)

                # Append carryforward entries for already-approved batches
                for entry in approved_carry.values():
                    reviews.append(entry)

                # Re-sort reviews to match batch file ordering (futures complete out-of-order)
                reviews.sort(key=lambda r: order.get(r["scope"], 999))

    # 5. Holistic (if not skipped by config or no_holistic flag)
    if holistic_reviewer is not None and not no_holistic:
        round_n = discover_round(reviews_dir, "plan", "holistic")
        if round_n > max_rounds:
            raise ReviewError(
                f"Round {round_n} exceeds max {max_rounds} for plan review (batch=holistic)"
            )
        print("[_review_plan] running holistic review", file=sys.stderr)

        # Union all Reads:/Modifies:/Creates: across all batch files
        all_raw_refs: dict[str, None] = {}
        for batch_path in batch_files:
            for ref in parse_batch_refs(batch_path):
                all_raw_refs[ref] = None
        all_reads = resolve_ref_paths(
            list(all_raw_refs.keys()), project_root, root,
            creates_union=creates_union, deletes_union=deletes_union,
            wiki_root=wiki_root, caller_label="_review_plan",
        )

        all_creates_on_disk = resolve_existing_paths(
            [r for r in creates_union if r not in all_raw_refs],
            project_root,
            root,
            wiki_root=wiki_root,
        )
        reads_set = {*all_reads, overview_path, *batch_files}
        all_creates_on_disk = [p for p in all_creates_on_disk if p not in reads_set]

        tool_rule = build_tool_rule(holistic_reviewer.MODE)

        manifest = build_manifest_section([overview_path, *batch_files, *all_reads, *all_creates_on_disk])

        if holistic_reviewer.MODE == "tool-use":
            batch_list = "\n".join(f"- `{p}`" for p in batch_files) or "(none)"
            read_list = "\n".join(f"- `{p}`" for p in [*all_reads, *all_creates_on_disk]) or "(none)"
            artefact_section = (
                f"{manifest}\n\n"
                f"## Plan files to review\n"
                f"- Overview: `{overview_path}`\n"
                f"- Batches:\n{batch_list}\n\n"
                f"Read the overview and every batch listed above. Then read the "
                f"source files referenced across all batches:\n{read_list}"
            )
        else:
            bulked_all = bulk_files([overview_path, *batch_files, *all_reads, *all_creates_on_disk])
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

        try:
            raw, session_id = holistic_reviewer.run(prompt_text, timeout=holistic_timeout)
        except LLMError as exc:
            reviews.append({
                "scope": "holistic",
                "round": round_n,
                "verdict": "ERROR",
                "blocking_count": 0,
                "file": None,
                "error": str(exc),
                "session_id": None,
            })
        else:
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
                        f"[_review_plan] holistic NEED_CONTEXT round-1; retrying with resume "
                        f"({len(missing_paths)} re-attached file(s)) session={(session_id or '?')[:8]}",
                        file=sys.stderr,
                    )
                    try:
                        raw, session_id = holistic_reviewer.run(
                            retry_prompt, session_id=session_id, resume=True, timeout=holistic_timeout
                        )
                    except LLMError as exc:
                        reviews.append({
                            "scope": "holistic",
                            "round": round_n,
                            "verdict": "ERROR",
                            "blocking_count": 0,
                            "file": None,
                            "error": f"resume retry failed: {exc}",
                            "session_id": None,
                        })
                        # Skip the write_review_file + append below; retry failed.
                    else:
                        verdict = parse_verdict(raw)
                        # Second NEED_CONTEXT propagates to caller untouched.
                        blocking_count = parse_blocking_count(raw, severity="BLOCKING")
                        path = write_review_file(
                            reviews_dir, "plan", round_n, raw, scope="holistic"
                        )
                        print(
                            f"[_review_plan] holistic: verdict={verdict} file={path.name}",
                            file=sys.stderr,
                        )
                        reviews.append({
                            "scope": "holistic",
                            "round": round_n,
                            "verdict": verdict,
                            "blocking_count": blocking_count,
                            "file": str(path),
                            "session_id": session_id,
                        })
                else:
                    # No resolvable paths to re-attach — propagate NEED_CONTEXT.
                    blocking_count = parse_blocking_count(raw, severity="BLOCKING")
                    path = write_review_file(
                        reviews_dir, "plan", round_n, raw, scope="holistic"
                    )
                    print(
                        f"[_review_plan] holistic: verdict={verdict} file={path.name}",
                        file=sys.stderr,
                    )
                    reviews.append({
                        "scope": "holistic",
                        "round": round_n,
                        "verdict": verdict,
                        "blocking_count": blocking_count,
                        "file": str(path),
                        "session_id": session_id,
                    })
            else:
                blocking_count = parse_blocking_count(raw, severity="BLOCKING")
                path = write_review_file(
                    reviews_dir, "plan", round_n, raw, scope="holistic"
                )
                print(
                    f"[_review_plan] holistic: verdict={verdict} file={path.name}",
                    file=sys.stderr,
                )
                reviews.append({
                    "scope": "holistic",
                    "round": round_n,
                    "verdict": verdict,
                    "blocking_count": blocking_count,
                    "file": str(path),
                    "session_id": session_id,
                })

    aggregate = aggregate_verdict([r["verdict"] for r in reviews])
    agg_round = max(r["round"] for r in reviews) if reviews else 0
    aggregate_blocking = sum(r.get("blocking_count", 0) for r in reviews)
    return ReviewResult(
        type="plan",
        round=agg_round,
        verdict=aggregate,
        blocking_count=aggregate_blocking,
        reviews=reviews,
    )
