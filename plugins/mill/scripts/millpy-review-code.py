"""mill-review-code — CLI entry point for code review.

Resolves project roots, loads config, finds the active task slug, calls
the code review backend, and prints JSON to stdout.

Flags:
    --slug <slug>      Override active-slug detection (run from hub/main).
    --batch <name>     run a per-batch review against the named batch in
                       the plan's Batch Index. Omit for a holistic review
                       covering every batch in one reviewer call.
    --extra-file <path> (repeatable) additional source file to include in
                       the reviewer's bulk. Used by mill-go on a
                       ``NEED_CONTEXT`` retry: the prior round listed the
                       files it could not find; the orchestrator passes
                       them explicitly here.
    --max-rounds <N>   Override roles.code-review.batch.rounds and roles.code-review.holistic.rounds
                       (overrides the active scope) for this invocation. Default: use config values.

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
        description="Run a code review for the active task."
    )
    parser.add_argument(
        "--slug",
        default=None,
        help="Override active-slug detection. Allows running from hub/main branch.",
    )
    parser.add_argument(
        "--batch",
        default=None,
        help="Batch name from the plan's Batch Index. Omit for holistic review.",
    )
    parser.add_argument(
        "--extra-file",
        action="append",
        default=[],
        help=(
            "Additional source file to include in the reviewer's bulk. "
            "Repeat for each file. Typically supplied by the orchestrator "
            "after a prior NEED_CONTEXT verdict."
        ),
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=None,
        help=(
            "Override roles.code-review.batch.rounds and roles.code-review.holistic.rounds "
            "(overrides the active scope) for this invocation. Default: use config values."
        ),
    )
    parser.add_argument(
        "--prior-notes",
        default=None,
        help=(
            "Path to a file containing prior-round non-blocking findings digest. "
            "Used to feed context to the reviewer about settled non-issues. "
            "Omit for round 1."
        ),
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
        help="Review round number from prepare envelope; required for finalize stage.",
    )
    args = parser.parse_args(argv)

    import _agent_dispatch
    import _paths
    import _reviewers
    from _paths import resolve_hub_path, resolve_wiki_path
    from _review_cli import print_error_envelope
    from _review_common import ReviewError, find_active_slug, load_config, resolve_path
    from _review_code import prepare, finalize, run

    try:
        project_root = Path.cwd()
        git_root = _paths.resolve_git_root()
        mill_dir = project_root / ".millhouse"
        wiki_root = resolve_wiki_path(project_root)
        cfg = load_config(resolve_hub_path(), mill_dir)
    except (ReviewError, ValueError, SystemExit) as exc:
        print_error_envelope("code", str(exc))
        return 1

    try:
        registry = _reviewers.load(project_root)
        _reviewers.validate_role_refs(cfg, registry)
    except _reviewers.ReviewerError as exc:
        print_error_envelope("code", str(exc))
        return 1

    extra_files: list[Path] = []
    for raw in args.extra_file:
        p = Path(raw)
        if not p.is_absolute():
            p = (project_root / p).resolve()
        if not p.exists():
            print_error_envelope("code", f"--extra-file not found: {p}")
            return 1
        extra_files.append(p)

    try:
        slug = args.slug or find_active_slug(project_root, wiki_root, cfg)
    except ReviewError as exc:
        print_error_envelope("code", str(exc))
        return 1

    if args.stage == "prepare":
        try:
            scope = args.batch or "holistic"
            prior_notes_path = Path(args.prior_notes) if args.prior_notes else None
            prepare_result = prepare(
                cfg, slug, scope=args.batch, mill_dir=mill_dir, project_root=project_root,
                wiki_root=wiki_root, git_root=git_root, extra_files=extra_files,
                max_rounds=args.max_rounds, prior_notes=prior_notes_path,
            )
            briefs_dir = _paths.resolve_task_path(project_root, "_mill/briefs/")
            brief_path = _agent_dispatch.write_brief(
                briefs_dir, "review-code", prepare_result["scope"],
                prepare_result["round"], prepare_result["prompt_text"]
            )
            envelope = {
                "stage": "prepare",
                "brief_path": str(brief_path),
                "subagent_type": _agent_dispatch.SUBAGENT_REVIEWER,
                "model": _agent_dispatch.model_to_tier(prepare_result["model"]),
                "session_id": None,
                "role": "review-code",
                "scope": prepare_result["scope"],
                "round": prepare_result["round"],
            }
            print(json.dumps(envelope))
            return 0
        except ReviewError as exc:
            print_error_envelope("code", str(exc))
            return 1
    elif args.stage == "finalize":
        if not args.agent_output:
            print_error_envelope("code", "--agent-output required for finalize stage")
            return 1
        if args.round is None:
            print_error_envelope("code", "--round is required for finalize stage")
            return 1
        try:
            agent_output_path = Path(args.agent_output)
            raw_text = agent_output_path.read_text(encoding="utf-8")
            reviews_dir = resolve_path(cfg["paths"]["reviews_dir"], slug)
            result = finalize(
                cfg, slug, raw_text, scope=args.batch, round_n=args.round,
                reviews_dir=reviews_dir, mill_dir=mill_dir,
                project_root=project_root, wiki_root=wiki_root, git_root=git_root
            )
            print(json.dumps(result.to_dict()))
            return 0
        except ReviewError as exc:
            print_error_envelope("code", str(exc))
            return 1
    else:  # full
        try:
            prior_notes_path = Path(args.prior_notes) if args.prior_notes else None
            result = run(
                cfg,
                slug,
                mill_dir,
                wiki_root,
                project_root,
                git_root=git_root,
                max_rounds=args.max_rounds,
                batch_name=args.batch,
                extra_files=extra_files,
                prior_notes=prior_notes_path,
            )
            print(json.dumps(result.to_dict()))
            return 0
        except ReviewError as exc:
            print_error_envelope("code", str(exc))
            return 1


if __name__ == "__main__":
    sys.exit(main())
