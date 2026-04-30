"""mill-review-plan — CLI entry point for plan review.

Resolves project roots, loads config, finds the active task slug, calls
the plan review backend, and prints JSON to stdout.

Flags:
    --holistic-only    Skip per-batch reviews; run only the holistic plan review.
    --max-rounds <N>   Override review.plan.rounds for this invocation.
                       Default: use config value.
    --no-holistic      Skip the holistic plan review; run per-batch reviews only.
    --skip-validate    Bypass the auto pre-review validator. Use only when you
                       know the validator is false-positive on a finding.

Exit codes:
    0 — review complete; JSON result on stdout
    1 — error (missing slug, bad config, backend failure, validator findings);
        message on stderr or JSON findings on stdout
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a plan review for the active task."
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=None,
        help="Override review.plan.rounds for this invocation. Default: use config value.",
    )
    scope_group = parser.add_mutually_exclusive_group()
    scope_group.add_argument(
        "--holistic-only",
        action="store_true",
        help="Skip per-batch reviews; run only the holistic plan review.",
    )
    scope_group.add_argument(
        "--no-holistic",
        action="store_true",
        help="Skip the holistic plan review; run per-batch reviews only.",
    )
    parser.add_argument(
        "--skip-validate",
        action="store_true",
        help=(
            "Bypass the auto pre-review validator. Use only when you know the "
            "validator is false-positive on a finding."
        ),
    )
    args = parser.parse_args(argv)

    from _paths import resolve_wiki_path
    from _review_common import ReviewError, find_active_slug, load_config, resolve_path
    from _review_plan import run

    project_root = Path.cwd()
    mill_dir = project_root / ".millhouse"
    wiki_root = resolve_wiki_path(project_root)
    cfg = load_config(wiki_root, mill_dir)

    try:
        slug = find_active_slug(mill_dir)
        if not args.skip_validate:
            from _plan_validate import run as validate_run
            plan_dir = resolve_path(cfg["paths"]["plan_dir"], slug)
            errors = validate_run(plan_dir, project_root, wiki_root=wiki_root)
            if errors:
                n = len(errors)
                m = len({e["batch"] for e in errors if e["batch"]})
                summary = f"{n} finding(s) across {m} batch(es)"
                print(json.dumps({"errors": errors, "summary": summary}))
                return 1
        result = run(
            cfg,
            slug,
            mill_dir,
            wiki_root,
            project_root,
            max_rounds=args.max_rounds,
            holistic_only=args.holistic_only,
            no_holistic=args.no_holistic,
        )
        print(json.dumps(result.to_dict()))
        return 0
    except ReviewError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
