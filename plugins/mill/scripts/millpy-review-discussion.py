"""mill-review-discussion — CLI entry point for discussion review.

Resolves project roots, loads config, finds the active task slug, calls
the discussion review backend, and prints JSON to stdout.

Flags:
    --slug <slug>      Override active-slug detection (run from hub/main).
    --max-rounds <N>   Override roles.discussion-review.holistic.rounds for this invocation.
                       Default: use config value.
    --stage {prepare,finalize,full}
                       Default: full. prepare=render prompt only, finalize=parse output only.
    --agent-output <path>
                       For finalize stage only; read reviewer output from this path.

Exit codes:
    0 — review complete; JSON result on stdout
    1 — error (missing slug, bad config, backend failure); message on stderr
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a discussion review for the active task."
    )
    parser.add_argument(
        "--slug",
        default=None,
        help="Override active-slug detection. Allows running from hub/main branch.",
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=None,
        help="Override roles.discussion-review.holistic.rounds for this invocation. Default: use config value.",
    )
    parser.add_argument(
        "--stage",
        choices=["prepare", "finalize", "full"],
        default="full",
        help="Stage to run: prepare (render prompt), finalize (parse output), or full (both). Default: full.",
    )
    parser.add_argument(
        "--agent-output",
        default=None,
        help="For finalize stage only; path to the reviewer's output file.",
    )
    parser.add_argument(
        "--round",
        type=int,
        default=None,
        help="Review round number from prepare envelope; auto-discovered when absent in finalize stage.",
    )
    args = parser.parse_args(argv)

    import _agent_dispatch
    import _paths
    import _reviewers
    from _paths import resolve_git_root, resolve_hub_path, resolve_wiki_path
    from _review_cli import print_error_envelope
    from _review_common import ReviewError, discover_round, find_active_slug, load_config, resolve_path
    from _review_discussion import prepare, finalize, run

    try:
        git_root = resolve_git_root()
        hub_dir = resolve_hub_path()
        mill_dir = hub_dir / ".millhouse"
        wiki_root = resolve_wiki_path(git_root)
        cfg = load_config(hub_dir, mill_dir)
        project_root = hub_dir
    except (ReviewError, ValueError, SystemExit) as exc:
        print_error_envelope("discussion", str(exc))
        return 1

    try:
        registry = _reviewers.load(project_root)
        _reviewers.validate_role_refs(cfg, registry)
    except _reviewers.ReviewerError as exc:
        print_error_envelope("discussion", str(exc))
        return 1

    try:
        slug = args.slug or find_active_slug(project_root, wiki_root, cfg)
    except ReviewError as exc:
        print_error_envelope("discussion", str(exc))
        return 1

    if args.stage == "prepare":
        try:
            prepare_result = prepare(cfg, slug, mill_dir, project_root, wiki_root, max_rounds=args.max_rounds)
            # Write the brief under the task worktree (git_root), not the hub root,
            # so the implementer's brief path is relative to the task branch checkout.
            briefs_dir = _paths.resolve_task_path(git_root, "_mill/briefs/")
            brief_path = _agent_dispatch.write_brief(
                briefs_dir, "review-discussion", prepare_result["scope"],
                prepare_result["round"], prepare_result["prompt_text"]
            )
            envelope = {
                "stage": "prepare",
                "brief_path": str(brief_path),
                "subagent_type": _agent_dispatch.SUBAGENT_REVIEWER,
                "model": _agent_dispatch.model_to_tier(prepare_result["model"]),
                "session_id": None,
                "role": "review-discussion",
                "scope": prepare_result["scope"],
                "round": prepare_result["round"],
            }
            print(json.dumps(envelope))
            return 0
        except ReviewError as exc:
            print_error_envelope("discussion", str(exc))
            return 1
    elif args.stage == "finalize":
        if not args.agent_output:
            print_error_envelope("discussion", "--agent-output required for finalize stage")
            return 1
        round_n = args.round
        if round_n is None:
            reviews_dir_for_discovery = resolve_path(cfg["paths"]["reviews_dir"], slug)
            round_n = discover_round(reviews_dir_for_discovery, "discussion", "holistic")
        try:
            agent_output_path = Path(args.agent_output)
            raw_text = agent_output_path.read_text(encoding="utf-8")
            reviews_dir = resolve_path(cfg["paths"]["reviews_dir"], slug)
            result = finalize(
                cfg, slug, raw_text, round_n=round_n,
                reviews_dir=reviews_dir, mill_dir=mill_dir,
                project_root=project_root, wiki_root=wiki_root
            )
            print(json.dumps(result.to_dict()))
            return 0
        except ReviewError as exc:
            print_error_envelope("discussion", str(exc))
            return 1
    else:  # full
        try:
            result = run(cfg, slug, mill_dir, project_root, wiki_root, max_rounds=args.max_rounds)
            print(json.dumps(result.to_dict()))
            return 0
        except ReviewError as exc:
            print_error_envelope("discussion", str(exc))
            return 1


if __name__ == "__main__":
    sys.exit(main())
