"""
Review backend for discussion artefacts.

Single holistic review call. The reviewer's tooluse flag (from the registry spec)
decides whether the discussion file is inlined into the prompt or the reviewer is
pointed at its path and reads it via Read/Grep/Glob. The backend writes the
review file; the LLM does not use Write.

Public API:
    run(cfg, slug, mill_dir, wiki_root, project_root) -> ReviewResult
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
    1. Resolve paths.
    2. Determine round number; enforce round cap.
    3. Load registry, resolve reviewer spec.
    4. Render prompt.
    5. Call reviewer (catch LLMError → total-fail → raise ReviewError).
    6. Parse verdict, write review file, return ReviewResult.
    """
    with worktree_snapshot_guard(project_root, expected_paths=[cfg["paths"]["reviews_dir"]]):
        # 1. Resolve paths
        discussion_path = resolve_path(cfg["paths"]["discussion_file"], slug)
        reviews_dir = resolve_path(cfg["paths"]["reviews_dir"], slug)

        # 2. Round discovery and cap check
        round_n = discover_round(reviews_dir, "discussion", "holistic")
        max_rounds = max_rounds if max_rounds is not None else cfg["roles"]["discussion-review"]["holistic"]["rounds"]
        if max_rounds == 0:
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
        if round_n > max_rounds:
            raise ReviewError(
                f"Round {round_n} exceeds max {max_rounds} for discussion review"
            )

        print(
            f"[_review_discussion] slug={slug!r} round={round_n}",
            file=sys.stderr,
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

        # 5. Invoke reviewer — for discussion a single sub-review, so any LLMError
        #    means zero successes → engine-internal failure → return ERROR ReviewResult.
        try:
            raw, session_id = _reviewer_single.run(spec, prompt_text)
        except LLMError as exc:
            _reviews = [{
                "scope": "holistic",
                "verdict": "ERROR",
                "file": None,
                "error": str(exc),
                "session_id": None,
            }]
            return ReviewResult(
                type="discussion",
                round=round_n,
                verdict="ERROR",
                blocking_count=0,
                reviews=_reviews,
            )

        # 6. Parse, write, return
        try:
            verdict = parse_verdict(raw)
        except ReviewError as exc:
            write_review_file(reviews_dir, "discussion", round_n, raw)
            _reviews = [{
                "scope": "holistic",
                "verdict": "ERROR",
                "file": None,
                "error": str(exc),
                "session_id": session_id,
            }]
            return ReviewResult(
                type="discussion",
                round=round_n,
                verdict="ERROR",
                blocking_count=0,
                reviews=_reviews,
            )

        blocking_count = parse_blocking_count(raw, severity="GAP")
        review_file = write_review_file(reviews_dir, "discussion", round_n, raw)

        print(
            f"[_review_discussion] wrote {review_file.name} verdict={verdict}",
            file=sys.stderr,
        )

        return ReviewResult(
            type="discussion",
            round=round_n,
            verdict=verdict,
            blocking_count=blocking_count,
            reviews=[
                {
                    "scope": "holistic",
                    "verdict": verdict,
                    "file": str(review_file),
                    "session_id": session_id,
                }
            ],
        )
