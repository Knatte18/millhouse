"""
Review backend for plan artefacts.

Per-batch reviews run in parallel via ThreadPoolExecutor (bulk mode).
An optional holistic review follows (also bulk). Results are aggregated
worst-case; total failure raises ReviewError.

Public API:
    run(cfg, slug, mill_dir, wiki_root, project_root) -> ReviewResult
"""
from __future__ import annotations

import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yaml

from _llm_claude import LLMError
from _review_common import (
    ReviewError,
    ReviewResult,
    aggregate_verdict,
    build_tool_rule,
    bulk_files,
    discover_round,
    load_reviewer,
    load_task_title,
    parse_verdict,
    read_constraints_md,
    render_prompt,
    resolve_path,
    write_review_file,
)

# Regex to match Reads:/Modifies:/Creates: lines in batch files.
# Example:   - **Reads:** `path/a`, `path/b`
_RE_REFS = re.compile(
    r"^-\s*\*\*(Reads|Modifies|Creates):\*\*\s+(?P<rest>.+)$",
    re.MULTILINE,
)


def _parse_batch_refs(batch_path: Path) -> list[str]:
    """Extract path strings from Reads:/Modifies:/Creates: lines in a batch file.

    1. Match lines with _RE_REFS.
    2. From <rest>, extract backtick-wrapped tokens via re.findall.
    3. If no backticks on the line, fall back to comma-split + strip.
    Returns a deduplicated list preserving first-seen order.
    """
    text = batch_path.read_text(encoding="utf-8")
    seen: dict[str, None] = {}  # ordered set
    for m in _RE_REFS.finditer(text):
        rest = m.group("rest")
        backtick_tokens = re.findall(r"`([^`]+)`", rest)
        if backtick_tokens:
            tokens = backtick_tokens
        else:
            tokens = [t.strip() for t in rest.split(",") if t.strip()]
        for t in tokens:
            seen[t] = None
    return list(seen.keys())


def _load_root_from_overview(overview_path: Path) -> str | None:
    """Read the `root:` field from the overview's top fenced-yaml block.

    v2 plan overviews use fenced ```yaml``` frontmatter (per the
    project markdown convention; `---` is reserved for SKILL.md). This
    parser locates the first ```yaml``` block and reads `root:` from
    it. Returns the root string if present and truthy, else None.
    Any structural problem (no block, unterminated, bad yaml, absent
    key) silently yields None — the review surface degrades to
    resolving paths against project_root directly, which is the right
    behaviour for a mill-v2 worktree where root is typically empty.
    """
    try:
        text = overview_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None

    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == "```yaml":
            start = i + 1
            break
    if start is None:
        return None
    end = None
    for j in range(start, len(lines)):
        if lines[j].strip() == "```":
            end = j
            break
    if end is None:
        return None

    fm_text = "\n".join(lines[start:end])
    try:
        data = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict):
        return None
    return data.get("root") or None


def _resolve_ref_paths(
    raw_paths: list[str],
    project_root: Path,
    root: str | None,
) -> list[Path]:
    """Resolve raw path strings to absolute Paths.

    root: absent → project_root / path
    root: present → project_root / root / path
    Non-existent paths are dropped with a stderr warning.
    """
    resolved: list[Path] = []
    for raw in raw_paths:
        if root:
            candidate = project_root / root / raw
        else:
            candidate = project_root / raw
        if candidate.exists():
            resolved.append(candidate)
        else:
            print(
                f"[_review_plan] warning: referenced path not found, skipping: {candidate}",
                file=sys.stderr,
            )
    return resolved


def _review_one_batch(
    batch_path: Path,
    overview_path: Path,
    reviews_dir: Path,
    round_n: int,
    task_title: str,
    constraints: str,
    batch_reviewer_name: str,
    batch_reviewer,
    project_root: Path,
    root: str | None,
) -> dict:
    """Review a single plan batch file. Returns a reviews[] entry dict."""
    raw_refs = _parse_batch_refs(batch_path)
    reads = _resolve_ref_paths(raw_refs, project_root, root)

    tool_rule = build_tool_rule(batch_reviewer.MODE)
    if batch_reviewer.MODE == "tool-use":
        read_list = "\n".join(f"- {p}" for p in reads) or "(none)"
        artefact_section = (
            f"## Plan files to review\n"
            f"- Overview: `{overview_path}`\n"
            f"- Batch:    `{batch_path}`\n\n"
            f"Read both files above. Then read the source files listed under "
            f"`Reads:` / `Modifies:` / `Creates:` in the batch:\n{read_list}"
        )
    else:
        bulked = bulk_files([overview_path, batch_path, *reads])
        artefact_section = (
            "## Plan content (overview + batch + Reads/Modifies files)\n"
            f"{bulked}"
        )

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
        raw = batch_reviewer.run(prompt_text)
    except LLMError as exc:
        return {
            "scope": batch_path.stem,
            "verdict": "ERROR",
            "file": None,
            "error": str(exc),
        }

    verdict = parse_verdict(raw)
    path = write_review_file(
        reviews_dir, "plan", round_n, raw, scope=batch_path.stem
    )
    print(
        f"[_review_plan] batch {batch_path.stem}: verdict={verdict} file={path.name}",
        file=sys.stderr,
    )
    return {"scope": batch_path.stem, "verdict": verdict, "file": str(path)}


def run(
    cfg: dict,
    slug: str,
    mill_dir: Path,
    wiki_root: Path,
    project_root: Path,
) -> ReviewResult:
    """Run plan review: parallel per-batch + optional holistic.

    Steps:
    1. Resolve plan_dir and reviews_dir; discover round.
    2. Verify overview exists; collect batch files.
    3. Load reviewers; verify bulk mode.
    4. Parallel per-batch reviews (skipped if batch_files is empty).
    5. Holistic review (skipped if cfg.review.plan.holistic is None).
    6. Total-fail check; return ReviewResult.
    """
    # 1. Paths and round
    plan_dir = resolve_path(cfg["paths"]["plan_dir"], slug, wiki_root)
    reviews_dir = resolve_path(cfg["paths"]["reviews_dir"], slug, wiki_root)
    round_n = discover_round(reviews_dir, "plan")
    max_rounds = cfg["review"]["plan"]["rounds"]
    if round_n > max_rounds:
        raise ReviewError(
            f"Round {round_n} exceeds max {max_rounds} for plan review"
        )

    print(
        f"[_review_plan] slug={slug!r} round={round_n} plan_dir={plan_dir}",
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

    # 4. Per-batch parallel section (guarded: skip if no batch files)
    if batch_files:
        futures_map: dict = {}
        with ThreadPoolExecutor(max_workers=len(batch_files)) as ex:
            for batch_path in batch_files:
                future = ex.submit(
                    _review_one_batch,
                    batch_path,
                    overview_path,
                    reviews_dir,
                    round_n,
                    task_title,
                    constraints,
                    batch_reviewer_name,
                    batch_reviewer,
                    project_root,
                    root,
                )
                futures_map[future] = batch_path

            for future in as_completed(futures_map):
                entry = future.result()  # propagates ReviewError from parse_verdict
                reviews.append(entry)

        # Re-sort reviews to match batch file ordering (futures complete out-of-order)
        order = {b.stem: i for i, b in enumerate(batch_files)}
        reviews.sort(key=lambda r: order.get(r["scope"], 999))

    # 5. Holistic (if not skipped)
    if holistic_reviewer is not None:
        print("[_review_plan] running holistic review", file=sys.stderr)

        # Union all Reads:/Modifies:/Creates: across all batch files
        all_raw_refs: dict[str, None] = {}
        for batch_path in batch_files:
            for ref in _parse_batch_refs(batch_path):
                all_raw_refs[ref] = None
        all_reads = _resolve_ref_paths(list(all_raw_refs.keys()), project_root, root)

        tool_rule = build_tool_rule(holistic_reviewer.MODE)
        if holistic_reviewer.MODE == "tool-use":
            batch_list = "\n".join(f"- `{p}`" for p in batch_files) or "(none)"
            read_list = "\n".join(f"- `{p}`" for p in all_reads) or "(none)"
            artefact_section = (
                f"## Plan files to review\n"
                f"- Overview: `{overview_path}`\n"
                f"- Batches:\n{batch_list}\n\n"
                f"Read the overview and every batch listed above. Then read the "
                f"source files referenced across all batches:\n{read_list}"
            )
        else:
            bulked_all = bulk_files([overview_path, *batch_files, *all_reads])
            artefact_section = (
                "## Plan content (overview + all batches + referenced files)\n"
                f"{bulked_all}"
            )

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
            raw = holistic_reviewer.run(prompt_text)
        except LLMError as exc:
            reviews.append({
                "scope": "holistic",
                "verdict": "ERROR",
                "file": None,
                "error": str(exc),
            })
        else:
            verdict = parse_verdict(raw)
            path = write_review_file(
                reviews_dir, "plan", round_n, raw, scope="holistic"
            )
            print(
                f"[_review_plan] holistic: verdict={verdict} file={path.name}",
                file=sys.stderr,
            )
            reviews.append({
                "scope": "holistic",
                "verdict": verdict,
                "file": str(path),
            })

    # 6. Total-fail check
    if reviews and all(r["verdict"] == "ERROR" for r in reviews):
        errors_summary = "; ".join(
            r.get("error", "unknown error") for r in reviews
        )
        raise ReviewError(f"All sub-reviews failed: {errors_summary}")

    aggregate = aggregate_verdict([r["verdict"] for r in reviews])
    return ReviewResult(
        type="plan",
        round=round_n,
        verdict=aggregate,
        reviews=reviews,
    )
