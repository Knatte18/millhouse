"""mill-abandon — mark the current task abandoned.

Run from inside the task's worktree.  Updates `<active_hub>/task/status.md`
on the task branch, commits, and pushes.  Then run mill-cleanup from the hub
to remove the worktree and active dir.
"""
from __future__ import annotations

import argparse
import datetime
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS))

import _builder_lock
import _marker
import _paths
import _review_common
import _status
import _subprocess_util


def _parse_iso(ts: str) -> datetime.datetime:
    return datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=datetime.timezone.utc
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Mark the current task abandoned.")
    parser.add_argument("--force", action="store_true",
                        help="Skip confirmation prompt and builder-lock guard.")
    args = parser.parse_args()

    # Step 1+2: resolve paths and derive slug from current branch
    git_root = _paths.resolve_git_root()
    wiki_path = _paths.resolve_wiki_path(git_root)
    hub_dir = _paths.resolve_hub_path()
    mill_dir = hub_dir / ".millhouse"
    cfg = _review_common.load_config(wiki_path, mill_dir)
    try:
        slug = _marker.slug_from_branch(git_root, wiki_path, cfg)
    except _marker.MarkerError as exc:
        sys.exit(f"Error: mill-abandon must run from a worktree. ({exc})")

    # Step 3: resolve paths via the centralized helpers (post-task-32: status.md
    # lives at <active_hub>/task/status.md on the task branch, not in the wiki).
    # We use active_hub for both the file path and the git -C target so the
    # relative argument "task/status.md" stays correct under sub-dir hub configs.
    container_path = _paths.resolve_container_path(git_root)
    active_hub = _paths.resolve_active_hub(
        container_path, slug, cfg=cfg, git_root=git_root,
    )

    # Step 4: load status.md and check phase
    status_path = active_hub / "task" / "status.md"
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

    # Step 7-10: update task branch
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    _status.append_phase(status_path, "abandoned", timestamp)
    add_result = _subprocess_util.run(
        ["git", "-C", str(active_hub), "add", "task/status.md"]
    )
    if add_result.returncode != 0:
        sys.exit(f"Error: git add failed: {add_result.stderr.strip()!r}")
    commit_result = _subprocess_util.run(
        ["git", "-C", str(active_hub), "commit", "-m", f"task: abandon {slug}"]
    )
    if commit_result.returncode != 0:
        sys.exit(f"Error: git commit failed: {commit_result.stderr.strip()!r}")
    push_result = _subprocess_util.run(
        ["git", "-C", str(active_hub), "push"]
    )
    if push_result.returncode != 0:
        sys.exit(f"Error: git push failed: {push_result.stderr.strip()!r}")

    # Step 11: success
    print(
        f"Task '{slug}' marked abandoned. "
        f"Run 'mill-cleanup' from the hub to remove the worktree and active dir, "
        f"and reset Home.md."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
