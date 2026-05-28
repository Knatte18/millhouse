"""mill-review-plan — CLI entry point for plan review.

Resolves project roots, loads config, finds the active task slug, calls
the plan review backend, and prints JSON to stdout.

Flags:
    --slug <slug>      Override active-slug detection (run from hub/main).
    --holistic-only    Skip per-batch reviews; run only the holistic plan review.
    --max-rounds <N>   Override roles.plan-review.batch.rounds and roles.plan-review.holistic.rounds
                       (overrides both scopes) for this invocation. Default: use config values.
    --no-holistic      Skip the holistic plan review; run per-batch reviews only.
    --skip-check <CHECK>  Skip a named validator check (repeatable). Silently ignores unknown names.
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
        "--slug",
        default=None,
        help="Override active-slug detection. Allows running from hub/main branch.",
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=None,
        help=(
            "Override roles.plan-review.batch.rounds and roles.plan-review.holistic.rounds "
            "(overrides both scopes) for this invocation. Default: use config values."
        ),
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
    parser.add_argument(
        "--skip-check",
        action="append",
        dest="skip_checks",
        default=[],
        metavar="CHECK",
        help="Skip a named validator check (repeatable). Silently ignores unknown names.",
    )
    args = parser.parse_args(argv)

    import _paths
    import _reviewers
    from _paths import resolve_hub_path, resolve_wiki_path
    from _review_cli import print_error_envelope
    from _review_common import ReviewError, find_active_slug, load_config, resolve_path
    from _review_plan import run

    try:
        project_root = Path.cwd()
        git_root = _paths.resolve_git_root()
        mill_dir = project_root / ".millhouse"
        wiki_root = resolve_wiki_path(project_root)
        cfg = load_config(resolve_hub_path(), mill_dir)
    except (ReviewError, ValueError, SystemExit) as exc:
        print_error_envelope("plan", str(exc))
        return 1

    try:
        registry = _reviewers.load(project_root)
        _reviewers.validate_role_refs(cfg, registry)
    except _reviewers.ReviewerError as exc:
        print_error_envelope("plan", str(exc))
        return 1

    try:
        slug = args.slug or find_active_slug(project_root, wiki_root, cfg)
        if not args.skip_validate:
            from _plan_validate import run as validate_run
            plan_dir = resolve_path(cfg["paths"]["plan_dir"], slug)
            errors = validate_run(plan_dir, project_root, wiki_root=wiki_root, skip_checks=frozenset(args.skip_checks))
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
            git_root=git_root,
            max_rounds=args.max_rounds,
            holistic_only=args.holistic_only,
            no_holistic=args.no_holistic,
        )
        print(json.dumps(result.to_dict()))
        return 0
    # Pre-launch errors only -- engine-internal failures return verdict:ERROR via run() (#338).
    except ReviewError as exc:
        print_error_envelope("plan", str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
