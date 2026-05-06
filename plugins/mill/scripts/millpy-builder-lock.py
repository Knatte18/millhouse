"""millpy-builder-lock.py — builder lock CLI (acquire / release / read).

Wraps the _builder_lock.py API behind a thin command-line interface so
mill-go can call it via `uv run` without inline Python.

Subcommands:
    acquire <slug>  — acquire the builder lock for <slug>; exit 1 on LockBusy
    release         — release the lock; always exits 0
    read            — print lock info if held (exit 0) or nothing if free (exit 1)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import _builder_lock


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Builder lock CLI — acquire, release, or read the per-worktree builder lock."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    acquire_p = sub.add_parser("acquire", help="Acquire the builder lock for a task slug.")
    acquire_p.add_argument("slug", help="Task slug to lock under.")

    sub.add_parser("release", help="Release the builder lock (idempotent).")
    sub.add_parser("read", help="Print lock info if held; exit 1 if free.")

    args = parser.parse_args(argv)
    mill_dir = Path.cwd() / ".millhouse"

    if args.command == "acquire":
        try:
            _builder_lock.acquire(mill_dir, args.slug)
        except _builder_lock.LockBusy as exc:
            print(str(exc), file=sys.stderr)
            return 1
        return 0

    if args.command == "release":
        _builder_lock.release(mill_dir)
        return 0

    if args.command == "read":
        info = _builder_lock.read(mill_dir)
        if info is None:
            return 1
        print(f"slug: {info.slug}")
        print(f"timestamp: {info.timestamp}")
        return 0

    return 1  # unreachable


if __name__ == "__main__":
    sys.exit(main())
