"""mill-review-discussion — CLI entry point for discussion review.

Resolves project roots, loads config, finds the active task slug, calls
the discussion review backend, and prints JSON to stdout.

Flags:
    --slug <slug>      Override active-slug detection (run from hub/main).
    --max-rounds <N>   Override roles.discussion-review.holistic.rounds for this invocation.
                       Default: use config value.

Exit codes:
    0 — review complete; JSON result on stdout
    1 — error (missing slug, bad config, backend failure); message on stderr
"""
from __future__ import annotations

import argparse
import json
import sys


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
    args = parser.parse_args(argv)

    import _reviewers
    from _paths import resolve_git_root, resolve_hub_path, resolve_wiki_path
    from _review_cli import print_error_envelope
    from _review_common import ReviewError, find_active_slug, load_config
    from _review_discussion import run

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
        result = run(cfg, slug, mill_dir, project_root, wiki_root, max_rounds=args.max_rounds)
        print(json.dumps(result.to_dict()))
        return 0
    # Pre-launch errors only -- engine-internal failures return verdict:ERROR via run() (#338).
    except ReviewError as exc:
        print_error_envelope("discussion", str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
