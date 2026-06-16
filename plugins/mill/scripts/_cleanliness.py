"""Pre-batch dirt snapshot + gate-time diff helper for mill-go."""
from __future__ import annotations

import sys
from pathlib import Path

import _pygit2_util
import _subprocess_util

# Junction directory names that are gitignored and should be excluded from scope violations
_JUNCTION_SKIP_SET = frozenset({".active", ".portals", ".wiki", ".others"})


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


def compute_scope_violations(worktree: Path) -> list[str]:
    """Return untracked files outside _mill/ that appeared at batch end.

    Uses _pygit2_util.status_porcelain with include_untracked=True so
    gitignored files are excluded automatically. Excludes junction directories
    (.active, .portals, .wiki, .others) even though they appear in status.
    Returns bare path strings (no '?? ' prefix), sorted. Empty list means no violations.
    """
    lines = _pygit2_util.status_porcelain(worktree, include_untracked=True)
    violations = []
    for line in lines:
        if line.startswith("?? "):
            path = line[3:]
            if not path.startswith("_mill/"):
                # Extract the first path segment and check if it's a junction
                first_segment = path.split("/")[0]
                if first_segment not in _JUNCTION_SKIP_SET:
                    violations.append(path)
    return sorted(violations)


def _parent_diff_names(worktree: Path, parent_branch: str) -> list[str]:
    """Return file paths changed by the task vs the parent branch.

    Runs `git diff --name-only <parent_branch>...HEAD` and returns the
    parsed output as a list of relative paths.
    """
    result = _subprocess_util.run(
        ["git", "diff", "--name-only", f"{parent_branch}...HEAD"],
        cwd=worktree,
    )
    if result.returncode != 0:
        print(
            f"[cleanliness] warning: git diff --name-only {parent_branch}...HEAD"
            f" exited {result.returncode} -- treating parent diff as empty",
            file=sys.stderr,
        )
        return []
    return [line for line in result.stdout.splitlines() if line]


def _filter_to_task_scope(porcelain_lines: list[str], task_dir: Path, owned_paths: set[str]) -> list[str]:
    """Filter porcelain status lines to paths within task scope.

    Task scope = paths under task_dir (worktree-relative) OR in owned_paths.
    Extracts path via line[3:] (skips 2-char status + space), checks membership.

    Args:
        porcelain_lines: List of porcelain-format status strings.
        task_dir: Worktree-relative path to the task directory.
        owned_paths: Set of worktree-relative paths changed by the task.

    Returns:
        Sorted subset of porcelain lines whose path is in scope.
    """
    task_dir_str = task_dir.as_posix()
    in_scope = []
    for line in porcelain_lines:
        path = line[3:]  # strip "XY " prefix
        # Check if path is under task_dir or in the parent-diff set
        if path.startswith(task_dir_str + "/") or path == task_dir_str or path in owned_paths:
            in_scope.append(line)
    return sorted(in_scope)


def compute_terminal_dirt(worktree: Path, task_dir: Path, parent_branch: str) -> list[str]:
    """Return in-scope dirty files at task completion.

    Task scope = the task_dir subtree union paths changed by the task's own
    commits vs the parent branch. Runs git status --porcelain --untracked-files=no
    and filters the result to only include files within the task's owned scope.

    Args:
        worktree: Path to the task worktree.
        task_dir: Worktree-relative path to the task directory (e.g., Path("_mill")).
        parent_branch: Name of the parent branch (e.g., "main").

    Returns:
        Sorted list of dirty files within the task scope, in porcelain format.
    """
    # Get current dirt
    lines = _pygit2_util.status_porcelain(worktree, include_untracked=False)

    # Get paths changed by the task
    parent_diff_names = _parent_diff_names(worktree, parent_branch)
    owned_paths = set(parent_diff_names)

    # Ensure task_dir is worktree-relative for path membership checks.
    # Callers (e.g. mill-go) may pass an absolute path derived from status_path.parent;
    # _filter_to_task_scope compares against worktree-relative porcelain paths,
    # so an absolute task_dir_str would never match.
    task_dir_rel = task_dir.relative_to(worktree) if task_dir.is_absolute() else task_dir

    # Filter to task scope
    return _filter_to_task_scope(lines, task_dir_rel, owned_paths)


def revert_out_of_scope_drift(
    worktree: Path, task_dir: Path, parent_branch: str
) -> tuple[list[str], list[str]]:
    """
    Revert out-of-scope formatter drift and return status.

    Out-of-scope = a tracked modification (status code ` M`, `M `, `MM`) whose path is
    NOT under task_dir AND NOT in the task's parent-diff owned set. Such drift is
    reverted via `git checkout HEAD -- <path>`. Untracked files (`??`) and added
    files (`A `) are NOT reverted.

    Args:
        worktree: Path to the task worktree.
        task_dir: Worktree-relative path to the task directory (e.g., Path("_mill")).
            If absolute, relativized to worktree.
        parent_branch: Name of the parent branch (e.g., "main").

    Returns:
        A tuple of (reverted_paths, remaining_in_scope_lines) where:
        - reverted_paths: sorted list of file paths that were reverted.
        - remaining_in_scope_lines: sorted list of in-scope porcelain lines still dirty
          after revert.
    """
    # Get current dirt
    lines = _pygit2_util.status_porcelain(worktree, include_untracked=False)

    # Get paths changed by the task
    parent_diff_names = _parent_diff_names(worktree, parent_branch)
    owned_paths = set(parent_diff_names)

    # Ensure task_dir is worktree-relative for path membership checks.
    task_dir_rel = task_dir.relative_to(worktree) if task_dir.is_absolute() else task_dir
    task_dir_str = task_dir_rel.as_posix()

    # Partition lines into in-scope and out-of-scope tracked modifications.
    reverted_paths = []
    remaining_in_scope_lines = []

    for line in lines:
        # Extract status code and path from porcelain format "XY path"
        status_code = line[:2]
        path = line[3:]

        # Check if this path is in scope
        in_scope = (
            path.startswith(task_dir_str + "/")
            or path == task_dir_str
            or path in owned_paths
        )

        if in_scope:
            # In-scope: keep it
            remaining_in_scope_lines.append(line)
        else:
            # Out-of-scope: check if it's a tracked modification that should be reverted
            # Modified status codes: " M" (modified in worktree), "M " (modified in index),
            # "MM" (modified in both)
            if status_code in (" M", "M ", "MM"):
                # Revert the file
                result = _subprocess_util.run(
                    ["git", "checkout", "HEAD", "--", path],
                    cwd=worktree,
                )
                if result.returncode == 0:
                    reverted_paths.append(path)
                    print(
                        f"[cleanliness] reverted out-of-scope: {path}",
                        file=sys.stderr,
                    )
                else:
                    print(
                        f"[cleanliness] warning: failed to revert {path}: "
                        f"git checkout exited {result.returncode}",
                        file=sys.stderr,
                    )

    return (sorted(reverted_paths), sorted(remaining_in_scope_lines))
