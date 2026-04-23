"""
Mode-aware staging/commit helper for codeguide.

Usage
-----
Inline mode — stage files in the current repo (caller's cwd); the outer
@git-commit skill will commit them as part of the source-code commit::

    python codeguide_commit.py --mode inline --file <path> [--file <path> ...] -m "<msg>"

Sibling mode — stage AND commit files inside the sibling repo, which has
its own git history independent of the target repo::

    python codeguide_commit.py --mode sibling --sibling-anchor <path> --file <path> [--file <path> ...] -m "<msg>"

The caller (codeguide-update) already holds ``mode`` and
``sibling_anchor`` from its own ``resolve.py`` call. Those are passed
explicitly so this helper does NOT re-run resolve.py (which would be
fragile if cwd differs from the repo root and couples commit-time
behavior to import-time side effects).

Output
------
Stdout: one-line JSON summary ``{"mode": ..., "committed": true|false, "files": [...]}``.
Stderr: subprocess transcripts on failure.

Exit codes
----------
0 — success
1 — git subprocess failed
2 — argument validation failed
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str], cwd: Path | None = None) -> int:
    result = subprocess.run(cmd, cwd=str(cwd) if cwd else None, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"$ {' '.join(cmd)}", file=sys.stderr)
        if result.stdout:
            print(result.stdout, file=sys.stderr)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
    return result.returncode


def _parse(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog="codeguide_commit.py", add_help=True)
    ap.add_argument("--mode", choices=("inline", "sibling"), required=True)
    ap.add_argument("--sibling-anchor", type=Path, default=None)
    ap.add_argument("--file", action="append", dest="files", default=[], type=Path)
    ap.add_argument("-m", "--message", required=True)
    ns = ap.parse_args(argv)
    if ns.mode == "sibling" and ns.sibling_anchor is None:
        ap.error("--mode sibling requires --sibling-anchor")
    if not ns.files:
        ap.error("at least one --file is required")
    return ns


def main(argv: list[str]) -> int:
    try:
        ns = _parse(argv)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2

    files = [str(f) for f in ns.files]

    if ns.mode == "inline":
        rc = _run(["git", "add", "--"] + files)
        if rc != 0:
            print(json.dumps({"mode": "inline", "committed": False, "files": files}))
            return 1
        print(json.dumps({"mode": "inline", "committed": False, "files": files}))
        return 0

    anchor = ns.sibling_anchor
    rc = _run(["git", "-C", str(anchor), "add", "--"] + files)
    if rc != 0:
        print(json.dumps({"mode": "sibling", "committed": False, "files": files}))
        return 1
    rc = _run(["git", "-C", str(anchor), "commit", "-m", ns.message])
    if rc != 0:
        print(json.dumps({"mode": "sibling", "committed": False, "files": files}))
        return 1
    print(json.dumps({"mode": "sibling", "committed": True, "files": files}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
