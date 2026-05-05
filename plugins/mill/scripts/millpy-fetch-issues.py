"""
mill-fetch-issues — thin CLI over ``_gh_issues.fetch``.

Fetches open GitHub issues for the current repo and writes them to a JSON
file. The output path defaults to ``<git_root>/.scratch/issues.json`` but
can be overridden via ``--out``. The absolute path of the written file is
printed as the last stdout line (parity with v1).

Usage:
    python mill-fetch-issues.py [--limit <N>] [--out <path>]

    --limit <N>    Maximum number of issues to fetch (default: 100).
    --out <path>   Output path (default: <git_root>/.scratch/issues.json).

Exit codes:
    0 — issues written successfully
    1 — fetch failed or gh not authed
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import _gh_issues
from _gh_issues import GhError
from _paths import resolve_git_root, resolve_hub_path


def main(argv: list[str] | None = None) -> int:
    """Fetch open GitHub issues and write them to a JSON file.

    Args:
        argv: Argument vector. Defaults to ``sys.argv[1:]``.

    Returns:
        Exit code: 0 on success, 1 on any error.
    """
    parser = argparse.ArgumentParser(
        prog="mill-fetch-issues",
        description="Fetch open GitHub issues and write them to JSON.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of issues to fetch (default: 100).",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output path (default: <git_root>/.scratch/issues.json).",
    )
    args = parser.parse_args(argv)

    resolve_git_root()

    if args.out is not None:
        out = Path(args.out)
    else:
        out = resolve_hub_path() / ".scratch" / "issues.json"

    out.parent.mkdir(parents=True, exist_ok=True)

    try:
        issues = _gh_issues.fetch(limit=args.limit)
    except GhError as exc:
        print(f"[mill-fetch-issues] {exc}", file=sys.stderr)
        return 1

    out.write_text(json.dumps(issues, indent=2), encoding="utf-8")
    print(str(out.resolve()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
