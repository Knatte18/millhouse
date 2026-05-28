"""
Idempotent archive-tag creation with conflict resolution.

When re-running mill-merge after a partial teardown, the archive tag may
already exist from a prior attempt. This module provides create_or_resolve,
which handles three conflict cases: same-SHA no-op, ancestor force-update,
and divergent move-aside with numeric suffix.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import _subprocess_util


def create_or_resolve(
    worktree: Path,
    slug: str,
    child_branch: str,
) -> dict:
    """
    Idempotently create or resolve an archive tag for a task branch.

    When the tag already exists, inspects its relationship to the new target SHA:
    - Same SHA: no-op (tag already points at the desired commit).
    - Ancestor: force-update to the new SHA (tag is stale).
    - Divergent: move the existing tag aside with a numeric suffix (-01, -02, ...),
      then create a new tag at the new SHA.

    Args:
        worktree: Path to the git worktree.
        slug: Task slug (used to form the tag name "archive/<slug>").
        child_branch: Branch name or SHA to tag (typically the cleanup-commit branch).

    Returns:
        Dict with keys:
          - action: "created" | "noop" | "force_update" | "moved_aside"
          - tag: The final tag name (e.g. "archive/my-task" or "archive/my-task-01")
          - moved_aside_to: The moved-aside tag name if action=="moved_aside", else None
    """
    # Resolve target SHA
    target_result = _subprocess_util.run(
        ["git", "-C", str(worktree), "rev-parse", child_branch],
        check=True,
    )
    target_sha = target_result.stdout.strip()

    tag_name = f"archive/{slug}"

    # Check if tag exists
    check_result = _subprocess_util.run(
        ["git", "-C", str(worktree), "rev-parse", "--verify", "--quiet", f"refs/tags/{tag_name}"],
        check=False,
    )

    if check_result.returncode != 0:
        # Tag doesn't exist -- create it
        _subprocess_util.run(
            ["git", "-C", str(worktree), "tag", tag_name, child_branch],
            check=True,
        )
        # Attempt push; don't fail if it fails (tmp repo has no remote)
        _subprocess_util.run(
            ["git", "-C", str(worktree), "push", "origin", tag_name],
            check=False,
        )
        print("[archive-tag] created -- tag: archive/{}".format(slug), file=sys.stderr)
        return {
            "action": "created",
            "tag": tag_name,
            "moved_aside_to": None,
        }

    # Tag exists -- get its current SHA
    existing_result = _subprocess_util.run(
        ["git", "-C", str(worktree), "rev-parse", f"refs/tags/{tag_name}"],
        check=True,
    )
    existing_sha = existing_result.stdout.strip()

    # Same SHA -- noop
    if existing_sha == target_sha:
        print("[archive-tag] noop -- tag matches", file=sys.stderr)
        return {
            "action": "noop",
            "tag": tag_name,
            "moved_aside_to": None,
        }

    # Check if existing is ancestor of target
    ancestor_result = _subprocess_util.run(
        ["git", "-C", str(worktree), "merge-base", "--is-ancestor", existing_sha, child_branch],
        check=False,
    )

    if ancestor_result.returncode == 0:
        # Existing is ancestor -- force update
        _subprocess_util.run(
            ["git", "-C", str(worktree), "tag", "-f", tag_name, child_branch],
            check=True,
        )
        # Attempt push; don't fail if it fails
        _subprocess_util.run(
            ["git", "-C", str(worktree), "push", "--force-with-lease", "origin", tag_name],
            check=False,
        )
        print("[archive-tag] force-update -- ancestor", file=sys.stderr)
        return {
            "action": "force_update",
            "tag": tag_name,
            "moved_aside_to": None,
        }

    # Divergent -- move aside and create new
    # Find the next available suffix
    tags_result = _subprocess_util.run(
        ["git", "-C", str(worktree), "tag", "-l", f"archive/{slug}-*"],
        check=True,
    )
    existing_tags = tags_result.stdout.strip().split("\n") if tags_result.stdout.strip() else []

    used_suffixes = set()
    pattern = re.compile(r"^archive/{}-(\d{{2}})$".format(re.escape(slug)))
    for tag in existing_tags:
        match = pattern.match(tag)
        if match:
            used_suffixes.add(int(match.group(1)))

    # Find the first unused suffix in 01-99
    next_suffix = 1
    while next_suffix in used_suffixes and next_suffix <= 99:
        next_suffix += 1

    if next_suffix > 99:
        raise RuntimeError(f"Too many archive tag conflicts for {slug} (>99 suffixes)")

    moved_aside_tag = f"archive/{slug}-{next_suffix:02d}"

    # Move the old tag to -NN
    _subprocess_util.run(
        ["git", "-C", str(worktree), "tag", moved_aside_tag, existing_sha],
        check=True,
    )

    # Update the main tag to point at new SHA
    _subprocess_util.run(
        ["git", "-C", str(worktree), "tag", "-f", tag_name, child_branch],
        check=True,
    )

    # Push both tags; don't fail if push fails
    _subprocess_util.run(
        ["git", "-C", str(worktree), "push", "origin", moved_aside_tag],
        check=False,
    )
    _subprocess_util.run(
        ["git", "-C", str(worktree), "push", "--force-with-lease", "origin", tag_name],
        check=False,
    )

    print(
        "[archive-tag] moved aside -- {}: new tag created".format(moved_aside_tag),
        file=sys.stderr,
    )
    return {
        "action": "moved_aside",
        "tag": tag_name,
        "moved_aside_to": moved_aside_tag,
    }
