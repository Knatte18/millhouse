"""
Review backend for discussion artefacts.

Single holistic review call.
The reviewer's tooluse flag (from the registry spec) decides whether the discussion file is inlined into the prompt or the reviewer is pointed at its path and reads it via Read/Grep/Glob.
The backend writes the review file;
the LLM does not use Write.

Public API:
    prepare(cfg, slug, mill_dir, project_root, wiki_root) -> dict
    Render prompt and resolve spec; return prepare dict with prompt_text, model, effort, round, reviews_dir, scope.
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
    agent_mode: bool = False,
    reviewer_override: str | None = None,
) -> dict:
    """Prepare a holistic discussion review by rendering the prompt.

    Args:
        agent_mode: When True, build_tool_rule returns the agent-mode cell (adds the single Write carve-out for the .out.md report).
            Defaults to False so run()'s `--stage full` fallback keeps receiving today's non-agent rule unchanged.
        reviewer_override: When not None, overrides the config-resolved discussion-review holistic reviewer for this call only -- nothing is written back to config.
            Bypasses the `reviewer: null` disablement (but not the separate `rounds: 0` check above),
            and skips the large-prompt auto-switch entirely.
            Resolved with `reject_non_claude=agent_mode`: rejects a non-Claude model when called from the Agent-mode `--stage prepare` entrypoint (agent_mode=True),
            but accepts one when called from run()'s internal, non-agent-mode invocation.

    Returns:
        Dict with keys: prompt_text, model, effort, round, reviews_dir, scope.
    """
    # 1. Resolve paths
    discussion_path = resolve_path(cfg["paths"]["discussion_file"], slug)
    reviews_dir = resolve_path(cfg["paths"]["reviews_dir"], slug)

    # 2. Round discovery and cap check.
    # The max_rounds kwarg overrides the configured cap (mirrors run()'s pre-refactor behaviour); enforcing here covers both the full path and the agent-mode CLI prepare stage.
    round_n = discover_round(reviews_dir, "discussion", "holistic")
    effective_max = max_rounds if max_rounds is not None else cfg["roles"]["discussion-review"]["holistic"]["rounds"]
    if effective_max == 0:
        raise ReviewError("discussion-review rounds=0 -- review disabled")
    if round_n > effective_max:
        raise ReviewError(
            f"Round {round_n} exceeds max {effective_max} for discussion review"
        )

    # 3. Resolve reviewer spec via registry.
    # An explicit reviewer_override bypasses the `reviewer: null` disablement below;
    # the config-resolved path is otherwise unchanged.
    # reject_non_claude follows agent_mode: the Agent-mode `--stage prepare` CLI entrypoint (agent_mode=True) only ever dispatches Claude subagents, so an override naming another provider is rejected here;
    # run()'s internal call (agent_mode=False) is the legacy direct-dispatch path, which must keep accepting any configured provider -- its own downstream resolve already uses reject_non_claude=False, so this call must not reject first.
    hub_dir = project_root
    registry = _reviewers.load(hub_dir)
    if reviewer_override is not None:
        try:
            spec = _reviewers.resolve_reviewer_override(
                registry, reviewer_override, reject_non_claude=agent_mode
            )
        except _reviewers.ReviewerError as exc:
            raise ReviewError(str(exc)) from exc
        reviewer_name = reviewer_override
    else:
        reviewer_name = cfg["roles"]["discussion-review"]["holistic"]["reviewer"]
        if reviewer_name is None:
            raise ReviewError("discussion-review holistic reviewer is null; nothing to do")
        spec = _reviewers.resolve(registry, reviewer_name)
    mode = "tool-use" if spec.get("tooluse") else "bulk"
    tool_rule = build_tool_rule(mode, agent_mode)

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

    if reviewer_override is None:
        spec, reviewer_name = maybe_switch_spec_for_large_prompt(
            prompt_text, spec, reviewer_name, cfg, "discussion-review", "holistic", registry
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
    actual_model: str | None = None,
) -> ReviewResult:
    """Finalize a discussion review by parsing verdict and writing the review file.

    Args:
        raw_text: Raw review output from the reviewer (should be extracted via extract_review_content).
        round_n: Round number.
        reviews_dir: Directory where review files are stored.
        actual_model: The model that actually produced this review, used to correct an unreliable self-reported ``reviewer_model:`` line before verdict parsing or disk write; passed through to ``finalize_scope`` on the success path only.

    Returns:
        ReviewResult with verdict, blocking count, and review entries.

    Raises:
        ReviewError: if verdict cannot be parsed from raw_text.
    """
    try:
        review_entry = finalize_scope(
            reviews_dir,
            "discussion",
            round_n,
            raw_text,
            scope="holistic",
            actual_model=actual_model,
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
    reviewer_override: str | None = None,
) -> ReviewResult:
    """Run a holistic discussion review.

    Steps:
    1. prepare() to render prompt.
    2. Call reviewer via _reviewer_single.run().
    3. finalize() to parse verdict and return ReviewResult.

    Args:
        reviewer_override: When not None, overrides the config-resolved discussion-review holistic reviewer for this call only -- nothing is written back to config.
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
        prepare_result = prepare(
            cfg, slug, mill_dir, project_root, wiki_root,
            max_rounds=max_rounds, reviewer_override=reviewer_override,
        )
        prompt_text = prepare_result["prompt_text"]
        round_n = prepare_result["round"]
        reviews_dir = prepare_result["reviews_dir"]

        # Determine spec for reviewer call (need to resolve it again in prepare to get full spec).
        # An explicit reviewer_override bypasses the reviewer: null disablement and skips the large-prompt auto-switch;
        # reject_non_claude=False since this direct-dispatch path never calls model_to_tier and must keep accepting non-Claude aliases.
        registry = _reviewers.load(project_root)
        if reviewer_override is not None:
            try:
                spec = _reviewers.resolve_reviewer_override(
                    registry, reviewer_override, reject_non_claude=False
                )
            except _reviewers.ReviewerError as exc:
                raise ReviewError(str(exc)) from exc
            reviewer_name = reviewer_override
        else:
            reviewer_name = cfg["roles"]["discussion-review"]["holistic"]["reviewer"]
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
