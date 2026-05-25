"""millpy-wikipush — commit and push manual wiki edits.

Resolves the wiki repo from the current git root, commits every local
change with an auto-generated message ``wiki: <file1>, <file2>``, and
pushes. Pulls with ``--rebase`` if the push is rejected non-fast-forward.

Usage:
    millpy-wikipush.py [--leave-conflicts]

Exit codes:
    0 — pushed (or no changes)
    1 — non-conflict failure (lock busy, push error, etc.)
    2 — conflict during rebase

When ``--leave-conflicts`` is passed (intended for skill/LLM use), the
wiki is left in mid-rebase state so the caller can resolve and continue.
Without the flag (manual operator use), the script aborts the rebase
and resets the local commit so the wiki returns to its pre-script state
(unstaged edits intact, no commit, no garbage) — "no harm done".
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS))

import _paths


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True)


def _changed_files(wiki: Path) -> list[str]:
    r = _run(["git", "-C", str(wiki), "status", "--porcelain"])
    return [line[3:] for line in r.stdout.splitlines() if line]


def _conflict_files(wiki: Path) -> list[str]:
    r = _run(["git", "-C", str(wiki), "diff", "--name-only", "--diff-filter=U"])
    return [line for line in r.stdout.splitlines() if line]


def _push_inner(wiki: Path, changed: list[str], *, leave_conflicts: bool) -> int:
    if not changed:
        print("no changes")
        return 0

    msg = f"wiki: {', '.join(changed)}"
    add = _run(["git", "-C", str(wiki), "add", "--"] + changed)
    if add.returncode != 0:
        print(f"git add failed: {add.stderr.strip()}", file=sys.stderr)
        return 1
    commit = _run(["git", "-C", str(wiki), "commit", "-m", msg])
    if commit.returncode != 0:
        print(f"git commit failed: {commit.stderr.strip()}", file=sys.stderr)
        return 1

    push = _run(["git", "-C", str(wiki), "push"])
    if push.returncode == 0:
        print(f"pushed: {msg}")
        return 0

    rebase = _run(["git", "-C", str(wiki), "pull", "--rebase"])
    if rebase.returncode != 0:
        cf = _conflict_files(wiki)
        if leave_conflicts:
            print(f"conflict on: {', '.join(cf)}", file=sys.stderr)
            return 2
        _run(["git", "-C", str(wiki), "rebase", "--abort"])
        _run(["git", "-C", str(wiki), "reset", "--mixed", "HEAD~1"])
        print(
            f"conflict on: {', '.join(cf)} — wiki reverted to working-tree state. "
            f"Run /mill-wiki-push to auto-resolve.",
            file=sys.stderr,
        )
        return 2

    push2 = _run(["git", "-C", str(wiki), "push"])
    if push2.returncode != 0:
        print(f"push failed: {push2.stderr.strip()}", file=sys.stderr)
        return 1
    print(f"pushed: {msg}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="commit + push wiki edits")
    parser.add_argument(
        "--leave-conflicts",
        action="store_true",
        help="leave wiki in mid-rebase state on conflict (for skill use)",
    )
    args = parser.parse_args(argv)

    git_root = _paths.resolve_git_root()
    wiki = _paths.resolve_wiki_path(git_root)

    # Capture changed files BEFORE pushing
    changed = _changed_files(wiki)

    return _push_inner(wiki, changed, leave_conflicts=args.leave_conflicts)


if __name__ == "__main__":
    sys.exit(main())
