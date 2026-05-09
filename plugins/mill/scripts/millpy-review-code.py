"""mill-review-code — CLI entry point for code review.

Resolves project roots, loads config, finds the active task slug, calls
the code review backend, and prints JSON to stdout.

Flags:
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
    args = parser.parse_args(argv)

    import _reviewers
    from _paths import resolve_wiki_path
    from _review_cli import print_error
    from _review_common import ReviewError, find_active_slug, load_config
    from _review_code import run

    project_root = Path.cwd()
    mill_dir = project_root / ".millhouse"
    wiki_root = resolve_wiki_path(project_root)
    cfg = load_config(wiki_root, mill_dir)

    try:
        registry = _reviewers.load(wiki_root)
        _reviewers.validate_role_refs(cfg, registry)
    except _reviewers.ReviewerError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    extra_files: list[Path] = []
    for raw in args.extra_file:
        p = Path(raw)
        if not p.is_absolute():
            p = (project_root / p).resolve()
        if not p.exists():
            print(f"--extra-file not found: {p}", file=sys.stderr)
            return 1
        extra_files.append(p)

    try:
        slug = find_active_slug(mill_dir)
        result = run(
            cfg,
            slug,
            mill_dir,
            wiki_root,
            project_root,
            max_rounds=args.max_rounds,
            batch_name=args.batch,
            extra_files=extra_files,
        )
        print(json.dumps(result.to_dict()))
        return 0
    except ReviewError as exc:
        print_error(exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
