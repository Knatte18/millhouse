"""mill-review-discussion — CLI entry point for discussion review.

Resolves project roots, loads config, finds the active task slug, calls
the discussion review backend, and prints JSON to stdout.

Flags:
    --max-rounds <N>   Override review.discussion.rounds for this invocation.
                       Default: use config value.

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
        "--max-rounds",
        type=int,
        default=None,
        help="Override review.discussion.rounds for this invocation. Default: use config value.",
    )
    args = parser.parse_args(argv)

    from _review_common import ReviewError, find_active_slug, load_config
    from _review_discussion import run

    project_root = Path.cwd()
    mill_dir = project_root / ".millhouse"
    wiki_root = (mill_dir / "wiki").resolve()
    cfg = load_config(wiki_root, mill_dir)

    try:
        slug = find_active_slug(mill_dir)
        result = run(cfg, slug, mill_dir, wiki_root, project_root, max_rounds=args.max_rounds)
        print(json.dumps(result.to_dict()))
        return 0
    except ReviewError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
