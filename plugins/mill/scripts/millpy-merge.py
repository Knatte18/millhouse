"""
mill-merge -- run the deterministic merge path as one script.

Usage:
    millpy-merge.py [--merged-in] [--confirm-parent <branch>] [--parent <branch>]

Flags:
    --merged-in               the parent branch was already merged in by the caller
    --confirm-parent <branch> confirm the parent branch after a halt asked for it
    --parent <branch>         parent branch to merge into, overriding the recorded one

Exit codes:
    0 -- a result was printed (including halt results)
    non-zero -- unexpected crash; traceback on stderr, no JSON on stdout

Stdout is exactly one ASCII JSON line: the result dict returned by ``_merge.run_merge``.
"""
from __future__ import annotations

import argparse
import json
import sys

import _merge


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Squash-merge the task branch into its parent.")
    parser.add_argument("--merged-in", action="store_true", help="Parent already merged into this branch.")
    parser.add_argument("--confirm-parent", default=None, help="Confirmed parent branch.")
    parser.add_argument("--parent", default=None, help="Parent branch override.")
    args = parser.parse_args(argv)

    options = _merge.MergeOptions(
        merged_in=args.merged_in,
        confirm_parent=args.confirm_parent,
        parent=args.parent,
    )
    result = _merge.run_merge(options)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
