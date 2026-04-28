"""mill-abandon — mark the current task abandoned.

Run from inside the task's worktree.  Updates wiki/active/<slug>/status.md,
commits, and pushes.  Then run mill-cleanup from the hub to remove the
worktree and active dir.
"""
from __future__ import annotations

import argparse
import datetime
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS))

import _active
import _builder_lock
import _paths
import _status
import _wiki


def _parse_iso(ts: str) -> datetime.datetime:
    return datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=datetime.timezone.utc
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Mark the current task abandoned.")
    parser.add_argument("--force", action="store_true",
                        help="Skip confirmation prompt and builder-lock guard.")
    args = parser.parse_args()

    mill_dir = Path.cwd() / ".millhouse"

    # Step 1: verify we are inside a worktree
    if not (mill_dir / "active.slug.md").exists():
        sys.exit("Error: mill-abandon must run from a worktree, not from the hub.")

    # Step 2: resolve slug
    try:
        slug = _active.read_slug(mill_dir)
    except _active.ActiveError as exc:
        sys.exit(f"Error reading active slug: {exc}")

    # Step 3: resolve paths
    git_root = _paths.resolve_git_root()
    wiki_path = _paths.resolve_wiki_path(git_root)

    # Step 4: load status.md and check phase
    status_path = wiki_path / "active" / slug / "status.md"
    if not status_path.exists():
        sys.exit(f"Error: status.md not found for slug '{slug}'.")

    try:
        info = _status.read_status(status_path)
    except ValueError as exc:
        sys.exit(f"Error reading status.md: {exc}")

    phase = info.get("phase", "")
    if phase == "abandoned":
        sys.exit(f"Error: task '{slug}' is already abandoned.")
    if phase == "done":
        sys.exit(f"Error: task '{slug}' is already done and cannot be abandoned.")

    # Step 5: builder-lock guard (skipped when --force)
    if not args.force:
        lock_info = _builder_lock.read(mill_dir)
        if lock_info is not None:
            now = datetime.datetime.now(datetime.timezone.utc)
            try:
                age = (now - _parse_iso(lock_info.timestamp)).total_seconds()
                stale = age > _builder_lock.STALE_WINDOW_SEC
            except ValueError:
                stale = True
            if not stale:
                sys.exit(
                    f"Error: builder lock held by '{lock_info.slug}' at "
                    f"{lock_info.timestamp}. Use --force to override."
                )

    # Step 6: confirm unless --force
    if not args.force:
        print(f"Abandon {slug}? (y/N) ", end="", flush=True)
        response = sys.stdin.readline()
        if response.strip().lower() != "y":
            return 0

    # Step 7-10: update wiki
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    _wiki.acquire_lock(wiki_path, slug)
    try:
        _status.append_phase(status_path, "abandoned", timestamp)
        _wiki.write_commit_push(
            wiki_path,
            [f"active/{slug}/status.md"],
            f"task: abandon {slug}",
        )
    finally:
        _wiki.release_lock(wiki_path)

    # Step 11: success
    print(
        f"Task '{slug}' marked abandoned. "
        f"Run 'mill-cleanup' from the hub to remove the worktree and active dir, "
        f"and reset Home.md."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
