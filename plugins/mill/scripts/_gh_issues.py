"""
GitHub issues helper — library for the mill-ghissues-to-tasks skill.

Thin wrapper around the ``gh`` CLI. Skills invoke these via ``python -c``
(see the mill-setup skill for the pattern). Requires the ``gh`` CLI to be
authenticated via ``gh auth login``.

Public API:
    fetch(repo=None, limit=100, label_filter=None, git_root=None) -> list[dict]
        Open issues for the current repo (or an override). Each dict has
        number, title, body, labels, createdAt. When an issue has comments,
        body includes rendered comments appended after the original body.
        When label_filter is a list of label names, only issues carrying at
        least one of those labels are returned.
    close_with_comment(number, comment, repo=None, git_root=None) -> None
        Close an issue after posting a single comment. Used by mill-revise-
        tasks when an issue has been turned into (or folded into) a task.
    detect_repo(git_root=None) -> str
        owner/repo string for the current worktree. "" on failure.
        Parses ``git remote get-url origin`` (``-C git_root`` when given).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import _paths
import _subprocess_util


class GhError(RuntimeError):
    """Raised when a gh CLI call fails. Carries stderr for diagnostics."""


def detect_repo(git_root: Path | None = None) -> str:
    if git_root is None:
        git_root = _paths.resolve_git_root()
    result = _subprocess_util.run(["git", "-C", str(git_root), "remote", "get-url", "origin"])
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


def _render_body_with_comments(body: str, comments: list[dict]) -> str:
    """Return ``body`` with rendered comment blocks appended.

    Sorts ``comments`` by ``createdAt`` ascending, caps at 10, renders each
    as a Markdown block after a horizontal rule. Returns ``body`` unchanged
    when ``comments`` is empty.
    """
    if not comments:
        return body

    sorted_comments = sorted(comments, key=lambda c: c["createdAt"])
    truncated = len(sorted_comments) - 10
    rendered = sorted_comments[:10]

    blocks = []
    for c in rendered:
        author_node = c["author"]
        if author_node and isinstance(author_node, dict):
            author = author_node["login"]
        else:
            author = "[deleted]"
        blocks.append(f"**Comment by {author} ({c['createdAt']}):**\n{c['body']}")

    result = body + "\n\n---\n\n" + "\n\n".join(blocks)
    if truncated > 0:
        result += f"\n\n*[{truncated} more comments truncated]*"
    return result


def fetch(
    repo: str | None = None,
    limit: int = 100,
    label_filter: list[str] | None = None,
    git_root: Path | None = None,
) -> list[dict[str, Any]]:
    """Return a list of open issues for the given repo.

    Each entry has number, title, body, labels, createdAt (per the gh
    ``--json`` fields requested). When an issue has comments, body includes
    rendered comments appended after the original body. When ``label_filter``
    is provided, only issues carrying at least one of the named labels are
    returned. Raises ``GhError`` on any non-zero gh exit or unparseable output.
    """
    repo_name = repo or detect_repo(git_root=git_root)
    if not repo_name:
        raise GhError(
            "Could not detect the repository (not in a git repo with a GitHub remote)."
        )

    result = _subprocess_util.run(
        [
            "gh", "issue", "list",
            "--repo", repo_name,
            "--state", "open",
            "--json", "number,title,body,labels,createdAt,comments",
            "--limit", str(limit),
        ]
    )
    if result.returncode != 0:
        raise GhError(
            f"gh issue list failed: {(result.stderr or '').strip()}"
        )
    try:
        issues = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise GhError(f"Failed to parse gh output: {exc}") from exc
    for issue in issues:
        issue["body"] = _render_body_with_comments(issue["body"], issue.pop("comments", []))
    if label_filter is not None:
        issues = [
            i for i in issues
            if any(label["name"] in label_filter for label in i.get("labels", []))
        ]
    return issues


def close_with_comment(
    number: int,
    comment: str,
    repo: str | None = None,
    git_root: Path | None = None,
) -> None:
    """Post ``comment`` on issue ``number``, then close it.

    Used by mill-ghissues-to-tasks when an issue has been turned into — or
    folded into — a wiki task. Leaving claimed-but-still-open issues on
    GitHub is a forgetting hazard; closing with a pointer comment makes
    the pipeline state explicit.

    Raises ``GhError`` on any non-zero gh exit.
    """
    repo_name = repo or detect_repo(git_root=git_root)
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
