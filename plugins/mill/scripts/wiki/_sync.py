"""
Git operations layer for wiki clone management.

All operations are subprocess-based, running git commands against the wiki
directory. This module provides atomic write, pull, and commit/push operations
with rebase retry on non-fast-forward conflicts.

Public API:
    path_guard(rel_path)
        Validate a relative path before read/write.
    atomic_write(wiki_path, rel_path, content)
        Write content to a file atomically (via temp + rename).
    pull(wiki_path)
        Fetch + fast-forward the wiki clone. Returns True if updated.
    commit_push(wiki_path, rel_paths, message)
        Stage, commit, and push with one rebase retry on non-fast-forward.

Exceptions:
    WikiPushError -- any unrecoverable git failure.
    WikiPathError -- invalid or traversal-attack path.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from wiki import WikiPathError, WikiPushError


# Bound network git operations so an unreachable remote -- or one waiting on a
# credential prompt the headless daemon can never answer -- fails fast instead
# of blocking every wiki op forever.
_GIT_NETWORK_TIMEOUT_SECONDS = 30.0


def _git_env() -> dict:
    """Environment for git subprocesses that forbids interactive prompts.

    The wiki daemon launches with no console (CREATE_NO_WINDOW), so any git
    credential or host-key prompt would block forever and starve every wiki
    op. These vars make git fail with a non-zero exit instead of prompting.
    """
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "Never"
    return env


def path_guard(rel_path: str) -> None:
    """Validate a relative path before any filesystem access.

    Raises WikiPathError if rel_path is:
    - Empty string
    - Absolute path
    - Contains ".." component

    Args:
        rel_path: Relative path to validate.

    Raises:
        WikiPathError: Path fails validation.
    """
    if not rel_path:
        raise WikiPathError("path cannot be empty")

    p = Path(rel_path)
    if p.is_absolute():
        raise WikiPathError(f"path must be relative, not {rel_path!r}")

    if ".." in p.parts:
        raise WikiPathError(f"path contains .., not allowed: {rel_path!r}")


def atomic_write(wiki_path: Path, rel_path: str, content: str) -> None:
    """Write content to a file atomically via temp file + rename.

    Creates parent directories if needed. Writes content as UTF-8.

    Args:
        wiki_path: Path to wiki clone root.
        rel_path: Relative path within wiki_path (validated by caller).
        content: File content (UTF-8 string).

    Raises:
        OSError: Temp file creation, write, or rename failed.
    """
    full_path = wiki_path / rel_path

    full_path.parent.mkdir(parents=True, exist_ok=True)

    fd, temp_path = tempfile.mkstemp(
        dir=str(full_path.parent),
        prefix=".tmp-",
        text=False,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(temp_path, str(full_path))
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def _run(
    args: list[str],
    cwd: Path,
    *,
    check: bool = True,
    timeout: float | None = None,
) -> subprocess.CompletedProcess:
    """Run a subprocess command with output capture and no interactive prompts.

    Args:
        args: Command arguments (e.g. ["git", "-C", "<path>", "status"]).
        cwd: Working directory (for context only; "-C" args override).
        check: If True, raise WikiPushError on non-zero exit.
        timeout: Seconds to wait before killing the command. None means no
            limit; pass a value for network ops that could hang on a remote.

    Returns:
        subprocess.CompletedProcess with returncode, stdout, stderr.

    Raises:
        WikiPushError: (if check=True) Command exited with non-zero rc, or the
            command exceeded ``timeout``.
    """
    try:
        result = subprocess.run(
            args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=_git_env(),
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise WikiPushError(
            f"git command timed out after {timeout:.0f}s: {' '.join(args)} -- "
            f"the remote may be unreachable or waiting on credentials "
            f"(interactive prompts are disabled for the daemon)."
        ) from exc

    if check and result.returncode != 0:
        raise WikiPushError(result.stderr.strip())

    return result


def pull(wiki_path: Path) -> bool:
    """Fetch + fast-forward the wiki clone.

    Runs "git pull --ff-only" to refresh the wiki. Returns True if the
    working tree was updated (i.e. "Already up to date." was not printed).

    Args:
        wiki_path: Path to wiki clone root.

    Returns:
        True if the working tree was updated, False if already up to date.

    Raises:
        WikiPushError: git pull --ff-only failed or non-fast-forward state.
    """
    result = _run(
        ["git", "-C", str(wiki_path), "pull", "--ff-only"],
        wiki_path,
        timeout=_GIT_NETWORK_TIMEOUT_SECONDS,
    )

    return "Already up to date." not in result.stdout


def commit_push(
    wiki_path: Path,
    rel_paths: list[str],
    message: str,
) -> None:
    """Stage, commit, and push with one rebase retry on non-fast-forward.

    Sequence:
    0. Verify wiki_path is a git repository
    1. git add -- <rel_paths>
    2. git diff --cached --quiet (check if staged)
    3. git commit -m <message>
    4. git push origin HEAD:<branch> (explicit refspec)
       - On non-fast-forward: git pull --rebase, retry push
       - On rebase conflict: git rebase --abort, raise WikiPushError

    A commit with nothing staged returns immediately (idempotent).

    Args:
        wiki_path: Path to wiki clone root.
        rel_paths: Relative paths to stage (already validated).
        message: Commit message.

    Raises:
        WikiPushError: Any unrecoverable git failure.
    """
    # Verify wiki_path is a git repository before attempting operations.
    # Use a subprocess.run call directly to avoid any potential issues with _run.
    try:
        import subprocess as sp
        result = sp.run(
            ["git", "-C", str(wiki_path), "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            timeout=5.0,
        )
        if result.returncode != 0:
            raise WikiPushError(
                f"not a git repository: {wiki_path} -- "
                f"initialize the wiki with 'git clone' or 'git init'"
            )
    except sp.TimeoutExpired:
        raise WikiPushError(f"git directory check timed out for {wiki_path}")
    except Exception as e:
        if isinstance(e, WikiPushError):
            raise
        raise WikiPushError(f"failed to verify git repository: {e}")

    add = _run(
        ["git", "-C", str(wiki_path), "add", "--"] + list(rel_paths),
        wiki_path,
        check=False,
    )
    if add.returncode != 0:
        stderr_msg = (add.stderr.strip() or "(git add failed with no error message)")
        raise WikiPushError(f"git add failed: {stderr_msg}")

    diff = _run(
        ["git", "-C", str(wiki_path), "diff", "--cached", "--quiet"],
        wiki_path,
        check=False,
    )
    if diff.returncode == 0:
        return
    elif diff.returncode != 1:
        raise WikiPushError(f"git diff --cached --quiet failed: {diff.stderr.strip()!r}")

    commit = _run(
        ["git", "-C", str(wiki_path), "commit", "-m", message],
        wiki_path,
        check=False,
    )
    if commit.returncode != 0:
        stderr_msg = (commit.stderr.strip() or "(git commit failed with no error message)")
        raise WikiPushError(f"git commit failed: {stderr_msg}")

    # Test mode: stop after local commit; skip the network push.
    if os.environ.get("WIKI_DAEMON_SKIP_PUSH") == "1":
        return

    # Resolve the current branch to use in the explicit-refspec push.
    branch_result = _run(
        ["git", "-C", str(wiki_path), "rev-parse", "--abbrev-ref", "HEAD"],
        wiki_path,
        check=False,
    )
    if branch_result.returncode != 0:
        raise WikiPushError(f"failed to resolve branch: {branch_result.stderr.strip()!r}")

    branch = branch_result.stdout.strip()
    if not branch or branch == "HEAD":
        raise WikiPushError(
            "cannot push: repository is in detached HEAD state or branch name is empty"
        )

    for attempt in range(2):
        push = _run(
            ["git", "-C", str(wiki_path), "push", "origin", f"HEAD:{branch}"],
            wiki_path,
            check=False,
            timeout=_GIT_NETWORK_TIMEOUT_SECONDS,
        )
        if push.returncode == 0:
            return

        if "non-fast-forward" not in push.stderr and "rejected" not in push.stderr:
            raise WikiPushError(f"git push failed: {push.stderr.strip()!r}")

        rebase = _run(
            ["git", "-C", str(wiki_path), "pull", "--rebase"],
            wiki_path,
            check=False,
            timeout=_GIT_NETWORK_TIMEOUT_SECONDS,
        )
        if rebase.returncode == 0:
            continue

        _run(
            ["git", "-C", str(wiki_path), "rebase", "--abort"],
            wiki_path,
            check=False,
        )
        raise WikiPushError(f"git pull --rebase failed: {rebase.stderr.strip()!r}")

    raise WikiPushError("push still failing after rebase retry")
