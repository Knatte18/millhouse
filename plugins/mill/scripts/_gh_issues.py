"""
GitHub issues helper — library for the mill-revise-tasks skill.

Thin wrapper around the ``gh`` CLI. Skills invoke these via ``python -c``
(see the mill-setup skill for the pattern). Requires the ``gh`` CLI to be
authenticated via ``gh auth login``.

Public API:
    fetch(repo=None, limit=100) -> list[dict]
        Open issues for the current repo (or an override). Each dict has
        number, title, body, labels, createdAt.
    close_with_comment(number, comment, repo=None) -> None
        Close an issue after posting a single comment. Used by mill-revise-
        tasks when an issue has been turned into (or folded into) a task.
    detect_repo() -> str
        owner/repo string for the current worktree. "" on failure.
"""
from __future__ import annotations

import json
import re
import sys
from typing import Any

import _subprocess_util


class GhError(RuntimeError):
    """Raised when a gh CLI call fails. Carries stderr for diagnostics."""


def detect_repo() -> str:
    """Return owner/repo for the current worktree, or "" on failure.

    Prefers ``gh repo view`` (respects gh's auth context); falls back to
    parsing ``git remote get-url origin``.
    """
    result = _subprocess_util.run(
        ["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"]
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()

    result = _subprocess_util.run(["git", "remote", "get-url", "origin"])
    if result.returncode != 0:
        return ""
    url = result.stdout.strip()
    m = re.match(r"^https://github\.com/(.+?)(?:\.git)?$", url)
    if m:
        return m.group(1)
    m = re.match(r"^git@github\.com:(.+?)(?:\.git)?$", url)
    if m:
        return m.group(1)
    return ""


def fetch(repo: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    """Return a list of open issues for the given repo.

    Each entry has number, title, body, labels, createdAt (per the gh
    ``--json`` fields requested). Raises ``GhError`` on any non-zero gh
    exit or unparseable output.
    """
    repo_name = repo or detect_repo()
    if not repo_name:
        raise GhError(
            "Could not detect the repository (not in a git repo with a GitHub remote)."
        )

    result = _subprocess_util.run(
        [
            "gh", "issue", "list",
            "--repo", repo_name,
            "--state", "open",
            "--json", "number,title,body,labels,createdAt",
            "--limit", str(limit),
        ]
    )
    if result.returncode != 0:
        raise GhError(
            f"gh issue list failed: {(result.stderr or '').strip()}"
        )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise GhError(f"Failed to parse gh output: {exc}") from exc


def close_with_comment(
    number: int,
    comment: str,
    repo: str | None = None,
) -> None:
    """Post ``comment`` on issue ``number``, then close it.

    Used by mill-revise-tasks when an issue has been turned into — or
    folded into — a wiki task. Leaving claimed-but-still-open issues on
    GitHub is a forgetting hazard; closing with a pointer comment makes
    the pipeline state explicit.

    Raises ``GhError`` on any non-zero gh exit.
    """
    repo_name = repo or detect_repo()
    if not repo_name:
        raise GhError(
            "Could not detect the repository (not in a git repo with a GitHub remote)."
        )

    result = _subprocess_util.run(
        [
            "gh", "issue", "close", str(number),
            "--repo", repo_name,
            "--comment", comment,
        ]
    )
    if result.returncode != 0:
        raise GhError(
            f"gh issue close #{number} failed: {(result.stderr or '').strip()}"
        )
    print(
        f"[_gh_issues] closed #{number} with comment",
        file=sys.stderr,
    )
