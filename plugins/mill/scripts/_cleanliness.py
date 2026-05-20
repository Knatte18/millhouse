"""Pre-batch dirt snapshot + gate-time diff helper for mill-go."""
from __future__ import annotations

import sys
from pathlib import Path

import _pygit2_util


def capture_snapshot(worktree: Path, snapshot_path: Path) -> None:
    """Capture a pre-batch git status snapshot to disk.

    Called once per batch from the initial-dispatch path of millpy-implement.py.
    Runs git status --porcelain --untracked-files=no and writes stdout verbatim.
    The on-disk file is committed on the task branch by mill-go's batch-start
    commit so it survives crash/resume.
    """
    lines = _pygit2_util.status_porcelain(worktree, include_untracked=False)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def compute_new_dirt(worktree: Path, snapshot_path: Path) -> list[str]:
    """Compare current git status against the pre-batch snapshot.

    Reads snapshot_path if it exists; if missing, warns to stderr and treats
    pre-batch as empty. Runs git status --porcelain --untracked-files=no for
    the post-batch state. Line-set diff (post − pre) so a status-code change
    like ' M' → 'MM' is flagged as new dirt, but pre-existing dirt is not.
    Returns sorted(post_set - pre_set).
    """
    if snapshot_path.exists():
        pre_text = snapshot_path.read_text(encoding="utf-8")
    else:
        print(
            f"[cleanliness] warning: snapshot file not found at {snapshot_path},"
            " treating pre-batch as empty",
            file=sys.stderr,
        )
        pre_text = ""

    lines = _pygit2_util.status_porcelain(worktree, include_untracked=False)
    post_text = "\n".join(lines) + ("\n" if lines else "")

    pre_set = {line for line in pre_text.splitlines() if line}
    post_set = {line for line in post_text.splitlines() if line}
    return sorted(post_set - pre_set)
