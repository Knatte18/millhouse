"""mill-validate-plan — standalone CLI for the static plan pre-validator.

Resolves project roots, loads config, finds the active task slug, runs
_plan_validate.run(), and prints a JSON envelope to stdout.

Flags: --skip-check <CHECK>  Skip a named validator check (repeatable). Silently ignores unknown names.
The CLI auto-discovers slug, plan_dir, and project_root from the
active task state. Path resolution goes through _paths (never the junction).

Exit codes:
    0 — validation passed; JSON result on stdout (summary: "no findings")
    1 — findings found or error; message on stderr / errors in JSON envelope
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the static plan pre-validator for the active task.")
    parser.add_argument(
        "--skip-check",
        action="append",
        dest="skip_checks",
        default=[],
        metavar="CHECK",
        help="Skip a named validator check (repeatable). Silently ignores unknown names.",
    )
    args = parser.parse_args(argv)

    from _paths import resolve_git_root, resolve_wiki_path
    from _review_common import ReviewError, find_active_slug, load_config, resolve_path
    import _plan_validate

    project_root = Path.cwd()
    mill_dir = project_root / ".millhouse"
    wiki_root = resolve_wiki_path(resolve_git_root())

    try:
        cfg = load_config(wiki_root, mill_dir)
        slug = find_active_slug(mill_dir)
        plan_dir = resolve_path(cfg["paths"]["plan_dir"], slug)
        errors = _plan_validate.run(plan_dir, project_root, wiki_root=wiki_root, skip_checks=frozenset(args.skip_checks))
    except ReviewError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if not errors:
        summary = "no findings"
    else:
        n = len(errors)
        m = len({e["batch"] for e in errors if e["batch"]})
        summary = f"{n} finding(s) across {m} batch(es)"

    print(json.dumps({"errors": errors, "summary": summary}))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
