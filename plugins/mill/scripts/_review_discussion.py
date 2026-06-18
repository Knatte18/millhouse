"""
Review backend for discussion artefacts.

Single holistic review call. The reviewer's tooluse flag (from the registry spec)
decides whether the discussion file is inlined into the prompt or the reviewer is
pointed at its path and reads it via Read/Grep/Glob. The backend writes the
review file; the LLM does not use Write.

Public API:
    prepare(cfg, slug, mill_dir, project_root, wiki_root) -> dict
        Render prompt and resolve spec; return prepare dict with prompt_text, model, round, reviews_dir, scope.
    finalize(cfg, slug, raw_text, *, round_n, reviews_dir, mill_dir, project_root, wiki_root) -> ReviewResult
        Parse verdict from raw_text and return ReviewResult.
    run(cfg, slug, mill_dir, wiki_root, project_root, *, max_rounds=None) -> ReviewResult
        Legacy API; calls prepare -> reviewer -> finalize.
"""
from __future__ import annotations

import sys
from pathlib import Path

import _reviewer_single
import _reviewers
from _llm_common import LLMError
from _review_common import (
    ReviewError,
    ReviewResult,
    build_tool_rule,
    discover_round,
    extract_review_content,
    finalize_scope,
    load_task_title,
    maybe_switch_spec_for_large_prompt,
    parse_blocking_count,
    parse_verdict,
    read_constraints_md,
    render_prompt,
    resolve_path,
    worktree_snapshot_guard,
    write_review_file,
)


def prepare(
    cfg: dict,
    slug: str,
    mill_dir: Path,
    project_root: Path,
    wiki_root: Path,
    *,
    max_rounds: int | None = None,
) -> dict:
    """Prepare a holistic discussion review by rendering the prompt.

    Returns:
        Dict with keys: prompt_text, model, round, reviews_dir, scope.
    """
    # 1. Resolve paths
    discussion_path = resolve_path(cfg["paths"]["discussion_file"], slug)
    reviews_dir = resolve_path(cfg["paths"]["reviews_dir"], slug)

    # 2. Round discovery and cap check. The max_rounds kwarg overrides the
    # configured cap (mirrors run()'s pre-refactor behaviour); enforcing here
    # covers both the full path and the agent-mode CLI prepare stage.
    round_n = discover_round(reviews_dir, "discussion", "holistic")
    effective_max = max_rounds if max_rounds is not None else cfg["roles"]["discussion-review"]["holistic"]["rounds"]
    if effective_max == 0:
        raise ReviewError("discussion-review rounds=0 -- review disabled")
    if round_n > effective_max:
        raise ReviewError(
            f"Round {round_n} exceeds max {effective_max} for discussion review"
        )

    # 3. Resolve reviewer spec via registry
    reviewer_name = cfg["roles"]["discussion-review"]["holistic"]["reviewer"]
    if reviewer_name is None:
        raise ReviewError("discussion-review holistic reviewer is null; nothing to do")
    hub_dir = project_root
    registry = _reviewers.load(hub_dir)
    spec = _reviewers.resolve(registry, reviewer_name)
    mode = "tool-use" if spec.get("tooluse") else "bulk"
    tool_rule = build_tool_rule(mode)

    # 4. Build mode-specific artefact section + render prompt
    if mode == "tool-use":
        artefact_section = (
            f"Read the discussion at `{discussion_path}`. The discussion "
            f"file is the authoritative scope. Read files referenced in "
            f"`## Technical Context` to verify claims."
        )
    else:
        discussion_text = discussion_path.read_text(encoding="utf-8")
        artefact_section = (
            "Evaluate the discussion below. The inlined content is the "
            "authoritative scope.\n\n## Discussion\n"
            f"{discussion_text}"
        )

    prompt_text = render_prompt(
        "review-discussion",
        task_title=load_task_title(project_root, wiki_root, cfg, slug),
        tool_rule=tool_rule,
        artefact_section=artefact_section,
        constraints=read_constraints_md(project_root),
        round=round_n,
        reviewer_model=reviewer_name,
    )

    spec, reviewer_name = maybe_switch_spec_for_large_prompt(
        prompt_text, spec, reviewer_name, cfg, "discussion-review", "holistic", registry
    )

    return {
        "prompt_text": prompt_text,
        "model": spec.get("model"),
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
) -> ReviewResult:
    """Finalize a discussion review by parsing verdict and writing the review file.

    Args:
        raw_text: Raw review output from the reviewer (should be extracted via extract_review_content).
        round_n: Round number.
        reviews_dir: Directory where review files are stored.

    Returns:
        ReviewResult with verdict, blocking count, and review entries.

    Raises:
        ReviewError: if verdict cannot be parsed from raw_text.
    """
    try:
        review_entry = finalize_scope(
            reviews_dir, "discussion", round_n, raw_text, scope="holistic"
        )
    except ReviewError as exc:
        path = write_review_file(reviews_dir, "discussion", round_n, raw_text, scope="holistic")
        return ReviewResult(
            type="discussion",
            round=round_n,
            verdict="ERROR",
            blocking_count=0,
            reviews=[{
                "scope": "holistic",
                "verdict": "ERROR",
                "file": str(path),
                "error": f"parse_verdict failed: {exc}",
                "session_id": None,
            }],
        )

    return ReviewResult(
        type="discussion",
        round=round_n,
        verdict=review_entry["verdict"],
        blocking_count=review_entry["blocking_count"],
        nit_count=review_entry["nit_count"],
        reviews=[{
            "scope": "holistic",
            "verdict": review_entry["verdict"],
            "file": review_entry["file"],
            "session_id": None,
        }],
    )


def run(
    cfg: dict,
    slug: str,
    mill_dir: Path,
    project_root: Path,
    wiki_root: Path,
    *,
    max_rounds: int | None = None,
) -> ReviewResult:
    """Run a holistic discussion review.

    Steps:
    1. prepare() to render prompt.
    2. Call reviewer via _reviewer_single.run().
    3. finalize() to parse verdict and return ReviewResult.
    """
    with worktree_snapshot_guard(project_root, expected_paths=[cfg["paths"]["reviews_dir"]]):
        # Check if review is disabled
        max_rounds_cfg = max_rounds if max_rounds is not None else cfg["roles"]["discussion-review"]["holistic"]["rounds"]
        if max_rounds_cfg == 0:
            reviews_dir = resolve_path(cfg["paths"]["reviews_dir"], slug)
            print(
                "[_review_discussion] rounds=0 -- review disabled, returning APPROVE",
                file=sys.stderr,
            )
            return ReviewResult(
                type="discussion",
                round=0,
                verdict="APPROVE",
                blocking_count=0,
                reviews=[{"scope": "holistic", "verdict": "APPROVE", "file": None, "skipped": True}],
            )

        # Prepare
        prepare_result = prepare(cfg, slug, mill_dir, project_root, wiki_root, max_rounds=max_rounds)
        prompt_text = prepare_result["prompt_text"]
        round_n = prepare_result["round"]
        reviews_dir = prepare_result["reviews_dir"]

        # Determine spec for reviewer call (need to resolve it again in prepare to get full spec)
        reviewer_name = cfg["roles"]["discussion-review"]["holistic"]["reviewer"]
        registry = _reviewers.load(project_root)
        spec = _reviewers.resolve(registry, reviewer_name)
        spec, _ = maybe_switch_spec_for_large_prompt(
            prompt_text, spec, reviewer_name, cfg, "discussion-review", "holistic", registry
        )

        # Invoke reviewer
        try:
            raw, session_id = _reviewer_single.run(spec, prompt_text)
            raw = extract_review_content(raw)
        except LLMError as exc:
            return ReviewResult(
                type="discussion",
                round=round_n,
                verdict="ERROR",
                blocking_count=0,
                reviews=[{
                    "scope": "holistic",
                    "verdict": "ERROR",
                    "file": None,
                    "error": str(exc),
                    "session_id": None,
                }],
            )

        # Finalize
        result = finalize(cfg, slug, raw, round_n=round_n, reviews_dir=reviews_dir, mill_dir=mill_dir, project_root=project_root, wiki_root=wiki_root)
        # Preserve session_id from reviewer call
        if result.reviews:
            result.reviews[0]["session_id"] = session_id
        return result
