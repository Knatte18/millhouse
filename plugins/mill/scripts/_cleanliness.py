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
    The on-disk file is committed on the task branch by mill-go's batch-start commit so it survives
    crash/resume.
    """
    lines = _pygit2_util.status_porcelain(worktree, include_untracked=False)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    # Use newline="" to suppress text-mode CRLF translation on Windows so the snapshot keeps LF terminators and does not itself appear as a dirty file.
    snapshot_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8", newline="")


def compute_new_dirt(worktree: Path, snapshot_path: Path) -> list[str]:
    """Compare current git status against the pre-batch snapshot.

    Reads snapshot_path if it exists;
    if missing, warns to stderr and treats pre-batch as empty.
    Runs git status --porcelain --untracked-files=no for the post-batch state.
    Line-set diff (post − pre) so a status-code change like ' M' → 'MM' is flagged as new dirt,
    but pre-existing dirt is not.
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

    # Strip trailing \r from each line so that a CRLF snapshot (possible on Windows even with newline="" when the file is read back via text mode) and an LF live-status output compare equal and produce no false-positive dirt.
    pre_set = {line.rstrip("\r") for line in pre_text.splitlines() if line.strip("\r")}
    post_set = {line.rstrip("\r") for line in post_text.splitlines() if line.strip("\r")}
    return sorted(post_set - pre_set)


def compute_scope_violations(hub_root: Path, git_root: Path | None) -> list[str]:
    """Return untracked files outside _mill/ that appeared at batch end, hub-relative.

    _pygit2_util.status_porcelain always returns paths relative to the git repository toplevel,
    regardless of which path is passed to it.
    In a nested hub layout (hub_root is a subdirectory of git_root), those git-root-relative paths
    must be rebased onto hub_root before the "_mill/"-prefix and junction checks -- which assume
    hub-relative paths -- can be applied correctly.

    When git_root is None, this call site is a flat-layout caller that never resolved a git_root
    (e.g.
    one that flows through _forward_output's git_root: Path | None = None default);
    treat that identically to git_root == hub_root (flat layout), i.e.
    hub_prefix = "".

    Otherwise hub_prefix = hub_root.relative_to(git_root).as_posix() (empty string when hub_root ==
    git_root, i.e.
    flat layout).
    For each untracked ("?? ") status line: if hub_prefix is non-empty and the git-root-relative
    path does not equal hub_prefix and does not start with hub_prefix + "/", the path belongs to a
    different subtree entirely and is dropped -- it is not a violation, just out of this hub's view.
    Otherwise the hub_prefix is stripped to produce the hub-relative remainder (unchanged from path
    when hub_prefix is empty).
    The existing _mill/-prefix and junction-directory checks are then applied to that hub-relative
    remainder.

    Returns bare hub-relative path strings (no '?? ' prefix), sorted.
    Empty list means no violations.
    """
    if git_root is None:
        hub_prefix = ""
    else:
        hub_prefix = hub_root.relative_to(git_root).as_posix()
        if hub_prefix == ".":
            hub_prefix = ""

    lines = _pygit2_util.status_porcelain(hub_root, include_untracked=True)
    violations = []
    for line in lines:
        if line.startswith("?? "):
            path = line[3:]
            if hub_prefix:
                if path != hub_prefix and not path.startswith(hub_prefix + "/"):
                    # Belongs to a different subtree of the git root, not this hub.
                    continue
                remainder = path[len(hub_prefix) + 1 :] if path != hub_prefix else ""
            else:
                remainder = path
            if not remainder.startswith("_mill/"):
                # Extract the first path segment and check if it's a junction
                first_segment = remainder.split("/")[0]
                if first_segment not in _JUNCTION_SKIP_SET:
                    violations.append(remainder)
    return sorted(violations)


def _parent_diff_names(worktree: Path, parent_branch: str) -> list[str] | None:
    """Return file paths changed by the task vs the parent branch.

    Runs `git diff --name-only <parent_branch>...HEAD` and returns the parsed output as a list of
    relative paths.

    Returns:
        The parsed list of relative paths, or None when the diff itself could not be resolved
        (e.g. the parent branch ref no longer exists) -- distinct from a genuinely empty `[]`
        result.
    """
    result = _subprocess_util.run(
        ["git", "diff", "--name-only", f"{parent_branch}...HEAD"],
        cwd=worktree,
    )
    if result.returncode != 0:
        print(
            f"[cleanliness] warning: git diff --name-only {parent_branch}...HEAD"
            f" exited {result.returncode} -- parent diff is unresolvable (unknown, not empty)",
            file=sys.stderr,
        )
        return None
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


def compute_terminal_dirt(worktree: Path, task_dir: Path, parent_branch: str) -> list[str] | None:
    """Return in-scope dirty files at task completion.

    Task scope = the task_dir subtree union paths changed by the task's own commits vs the parent
    branch.
    Runs git status --porcelain --untracked-files=no and filters the result to only include files
    within the task's owned scope.

    Args:
        worktree: Path to the task worktree.
        task_dir: Worktree-relative path to the task directory (e.g., Path("_mill")).
        parent_branch: Name of the parent branch (e.g., "main").

    Returns:
        Sorted list of dirty files within the task scope, in porcelain format, or None when the
        parent diff itself is unresolvable -- distinct from a genuinely empty result.
    """
    # Get current dirt
    lines = _pygit2_util.status_porcelain(worktree, include_untracked=False)

    # Get paths changed by the task
    parent_diff_names = _parent_diff_names(worktree, parent_branch)
    if parent_diff_names is None:
        return None
    owned_paths = set(parent_diff_names)

    # Ensure task_dir is worktree-relative for path membership checks.
    # Callers (e.g.
    # mill-go) may pass an absolute path derived from status_path.parent;
    # _filter_to_task_scope compares against worktree-relative porcelain paths, so an absolute task_dir_str would never match.
    task_dir_rel = task_dir.relative_to(worktree) if task_dir.is_absolute() else task_dir

    # Filter to task scope
    return _filter_to_task_scope(lines, task_dir_rel, owned_paths)


def _is_go_main_artifact(worktree: Path, path: str) -> bool:
    """
    Return True if the extensionless file at path is a Go package-main build artifact.

    Queries tracked Go files via git ls-files and checks whether any of them (a) live in a directory
    whose basename equals the violation's basename and (b) declare package main (a stripped line
    that starts with "package main").
    Only candidate files that can be read are checked;
    unreadable files are silently skipped.

    This is the corroborating heuristic for extensionless binary names.
    A bare name like "sandbox" is only auto-cleaned when a tracked Go file exists at a path like
    tools/sandbox/main.go that declares package main.
    This prevents over-matching non-Go files such as shell scripts or data files with no extension.

    Args:
        worktree: Path to the task worktree.
        path: Worktree-relative path of the violation (e.g. "sandbox").

    Returns:
        True if at least one tracked Go file qualifies as a package-main source for this binary
        name;
        False otherwise.
    """
    # The binary name to match against parent directory names in the Go source tree
    basename = Path(path).name

    # Retrieve all tracked Go files; a non-zero exit (e.g. not a git repo) means no match
    result = _subprocess_util.run(
        ["git", "ls-files", "*.go"],
        cwd=worktree,
    )
    if result.returncode != 0:
        return False

    # For each tracked Go file, check if its parent directory name matches the binary's basename and the file declares package main
    for go_file in result.stdout.splitlines():
        if not go_file:
            continue
        go_file_path = Path(go_file)
        # Only files directly inside a directory whose name equals the binary's name qualify
        if go_file_path.parent.name != basename:
            continue
        # Read the Go source file and scan for a package main declaration
        try:
            content = (worktree / go_file).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in content.splitlines():
            if line.strip().startswith("package main"):
                return True

    return False


def clean_ephemeral_scope_violations(hub_root: Path, git_root: Path) -> tuple[list[str], list[str]]:
    """
    Auto-clean ephemeral build artifacts from scope violations.

    Calls compute_scope_violations(hub_root, git_root) to get untracked out-of-scope files (already
    rebased to hub-relative paths -- see that function's docstring for the nested-hub-layout
    rebasing rule), partitions them by a conservative allowlist, removes allowlisted files from disk
    (swallowing already-gone errors), and returns the removed and blocking paths.

    Allowlist rules applied in order:
    1. Basename ends with '.exe': blanket Go compiled binary or test executable (e.g.
        sandbox.exe, foo.test.exe).
        The .exe suffix rule subsumes the historical .test.exe entry.
    2. Basename has no extension (no '.'
        in basename): allowlisted only when _is_go_main_artifact confirms a matching package-main
            source directory (e.g.
        extensionless 'sandbox' corroborated by tools/sandbox/main.go declaring package main).
    3. Basename matches the fixed allowlist: 'coverage.out',
        or suffix in {.test, .test.exe, .prof, .cover}.

    For allowlisted files: os.remove is called, FileNotFoundError is swallowed and the path is still
    reported as removed, OSError is reported as blocking instead.
    Non-allowlisted violations are reported as blocking without touching disk.

    Args:
        hub_root: Path to the mill hub root (the project root resolved via
            _paths.resolve_hub_path()).
            Hub-relative violation paths returned by compute_scope_violations are joined onto this
                root for disk removal.
        git_root: Path to the git repository toplevel resolved via _paths.resolve_git_root().
            Equal to hub_root in a flat layout.

    Returns:
        A tuple of (removed_paths, blocking_paths) where:
        - removed_paths: sorted list of allowlisted files that were removed from disk.
        - blocking_paths: sorted list of non-allowlisted untracked out-of-scope files.
    """
    import os

    violations = compute_scope_violations(hub_root, git_root)

    removed_paths = []
    blocking_paths = []

    for violation in violations:
        basename = violation.split("/")[-1]

        # Rule 1: blanket .exe suffix covers all Go compiled binaries and test executables
        if basename.endswith(".exe"):
            is_allowlisted = True
        # Rule 2: extensionless name -- only allowlisted when a package-main source dir matches
        elif "." not in basename:
            is_allowlisted = _is_go_main_artifact(hub_root, violation)
        # Rule 3: fixed allowlist for other known extension-bearing build artifact types
        else:
            is_allowlisted = (
                basename == "coverage.out"
                or basename.endswith(".test")
                or basename.endswith(".prof")
                or basename.endswith(".cover")
            )

        if is_allowlisted:
            # Try to remove the file from disk, swallowing errors for already-gone files
            file_path = hub_root / violation
            try:
                os.remove(file_path)
                removed_paths.append(violation)
            except FileNotFoundError:
                # Already gone, treat as successfully removed
                removed_paths.append(violation)
            except OSError:
                # Other errors (permissions, etc.) are still reported as blocking
                blocking_paths.append(violation)
        else:
            # Non-allowlisted: report as blocking without touching disk
            blocking_paths.append(violation)

    return (sorted(removed_paths), sorted(blocking_paths))


def revert_out_of_scope_drift(
    worktree: Path, task_dir: Path, parent_branch: str, git_root: Path | None = None
) -> tuple[list[str], list[str] | None]:
    """
    Revert out-of-scope formatter drift and return status.

    Out-of-scope = a tracked modification (status code ` M`, `M `, `MM`) whose path is NOT under
    task_dir AND NOT in the task's parent-diff owned set.
    Such drift is reverted via `git checkout HEAD -- <path>`.
    Untracked files (`??`) and added files (`A `) are NOT reverted.

    In a nested-hub layout (worktree is a subdirectory of git_root), both the porcelain status lines
    and the parent-diff owned paths are git-root-relative, while task_dir is hub-relative -- see
    compute_scope_violations's docstring in this same file for the rebasing rationale.
    Both inputs are rebased onto worktree (the hub root) before the in-scope/out-of-scope partition
    and the `git checkout` subprocess call are performed.

    Args:
        worktree: Path to the task worktree (the mill hub root).
        task_dir: Worktree-relative path to the task directory (e.g., Path("_mill")).
            If absolute, relativized to worktree.
        parent_branch: Name of the parent branch (e.g., "main").
        git_root: Path to the git repository toplevel resolved via _paths.resolve_git_root().
            None means a flat-layout caller that never resolved a git_root, treated identically to
                git_root == worktree (i.e.
            hub_prefix = "").

    Returns:
        A tuple of (reverted_paths, remaining_in_scope_lines) where:
        - reverted_paths: sorted list of hub-relative file paths that were reverted. Always `[]`
        (never None) when the parent diff is unresolvable, since nothing was attempted.
        - remaining_in_scope_lines: sorted list of in-scope porcelain lines (with hub-relative
        paths) still dirty after revert, or None when the parent diff itself is unresolvable --
        distinct from a genuinely empty result.
    """
    # Get current dirt (git-root-relative, regardless of the cwd passed to git)
    lines = _pygit2_util.status_porcelain(worktree, include_untracked=False)

    # Get paths changed by the task (also git-root-relative, same reason)
    parent_diff_names = _parent_diff_names(worktree, parent_branch)
    if parent_diff_names is None:
        # Owned-path set is unknown -- nothing can be safely reverted (would risk
        # reverting genuinely task-owned files), so report unknown scope rather than
        # silently proceeding as if nothing were owned.
        return ([], None)
    owned_paths = set(parent_diff_names)

    # Compute the hub_prefix using the same technique as compute_scope_violations: empty for a flat layout (worktree == git_root) or an unresolved git_root.
    if git_root is None:
        hub_prefix = ""
    else:
        hub_prefix = worktree.relative_to(git_root).as_posix()
        if hub_prefix == ".":
            hub_prefix = ""

    def _rebase_onto_hub(path: str) -> str | None:
        """Rebase a git-root-relative path onto the hub root.

        Returns the hub-relative remainder,
        or None if the path belongs to a different subtree of the git root entirely (outside this
        hub's view).
        """
        if not hub_prefix:
            return path
        if path != hub_prefix and not path.startswith(hub_prefix + "/"):
            return None
        return path[len(hub_prefix) + 1 :] if path != hub_prefix else ""

    # Rebase owned_paths before the membership check below, so a genuine task-owned file outside task_dir is not misclassified as out-of-scope drift and silently reverted.
    owned_paths = {
        rebased
        for path in owned_paths
        for rebased in (_rebase_onto_hub(path),)
        if rebased is not None
    }

    # Ensure task_dir is worktree-relative for path membership checks.
    task_dir_rel = task_dir.relative_to(worktree) if task_dir.is_absolute() else task_dir
    task_dir_str = task_dir_rel.as_posix()

    # Partition lines into in-scope and out-of-scope tracked modifications.
    reverted_paths = []
    remaining_in_scope_lines = []

    for line in lines:
        # Extract status code and path from porcelain format "XY path"
        status_code = line[:2]
        raw_path = line[3:]

        # Rebase the git-root-relative path onto the hub root;
        # drop lines that belong to a different subtree of the git root, not this hub.
        path = _rebase_onto_hub(raw_path)
        if path is None:
            continue

        # Check if this path is in scope
        in_scope = (
            path.startswith(task_dir_str + "/")
            or path == task_dir_str
            or path in owned_paths
        )

        if in_scope:
            # In-scope: keep it, with the hub-relative path substituted back in
            remaining_in_scope_lines.append(f"{status_code} {path}")
        else:
            # Out-of-scope: check if it's a tracked modification that should be reverted Modified status codes: " M" (modified in worktree), "M " (modified in index), "MM" (modified in both)
            if status_code in (" M", "M ", "MM"):
                # Revert the file (checkout runs with cwd=worktree, so the path passed here must be hub-relative)
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
                    # Failed revert: treat as still-dirty in-scope so the gate sees it
                    remaining_in_scope_lines.append(f"{status_code} {path}")
                    print(
                        f"[cleanliness] warning: failed to revert {path}: "
                        f"git checkout exited {result.returncode}",
                        file=sys.stderr,
                    )

    return (sorted(reverted_paths), sorted(remaining_in_scope_lines))
