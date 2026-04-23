"""
Read and write ``.millhouse/active.slug.md``.

Each spawned worktree carries a per-worktree marker file at
``.millhouse/active.slug.md`` identifying which task the worktree is
working on. mill-spawn writes it at spawn time; every downstream
skill/script (mill-start, mill-plan, mill-go, mill-merge, mill-cleanup)
reads it to locate the wiki state for "this" task.

The file is markdown with a fenced-yaml block — plain enough for a human
to read in VS Code but structured enough for scripts to parse.

Format written by mill-spawn:

    # Active task

    ```yaml
    slug: <slug>
    task_title: <title>
    branch: <branch-name>
    spawned_at: <iso-8601-utc>
    ```

Public API:
    write(mill_dir, slug, task_title, branch, spawned_at) -> None
        Write the marker file under ``mill_dir / "active.slug.md"``.
    read_slug(mill_dir) -> str
        Return the ``slug:`` value from the marker file. Raises
        ``ActiveError`` if the file is missing or malformed.
    read_all(mill_dir) -> dict[str, str]
        Return every key from the fenced-yaml block. Same error shape.
"""
from __future__ import annotations

from pathlib import Path

import yaml

_MARKER_NAME = "active.slug.md"


class ActiveError(RuntimeError):
    """Raised when the marker file is missing, malformed, or incomplete."""


def _path(mill_dir: Path) -> Path:
    return mill_dir / _MARKER_NAME


def write(
    mill_dir: Path,
    *,
    slug: str,
    task_title: str,
    branch: str,
    spawned_at: str,
) -> None:
    """
    Write the per-worktree marker at ``mill_dir / "active.slug.md"``.

    Overwrites any existing marker — mill-spawn owns a fresh worktree,
    so no existing file is expected. Callers that want to preserve a
    prior marker should check first.

    Args:
        mill_dir: The ``.millhouse/`` directory inside the worktree.
        slug: Task slug from Home.md.
        task_title: Human-readable task title.
        branch: Branch name the worktree is on (prefix + slug).
        spawned_at: ISO-8601 UTC timestamp of when mill-spawn ran.
    """
    mill_dir.mkdir(parents=True, exist_ok=True)
    body = (
        "# Active task\n\n"
        "```yaml\n"
        f"slug: {slug}\n"
        f"task_title: {task_title}\n"
        f"branch: {branch}\n"
        f"spawned_at: {spawned_at}\n"
        "```\n"
    )
    _path(mill_dir).write_text(body, encoding="utf-8")


def read_all(mill_dir: Path) -> dict[str, str]:
    """
    Return every key/value from the fenced-yaml block of the marker file.

    Args:
        mill_dir: The ``.millhouse/`` directory inside the worktree.

    Returns:
        A dict with the yaml keys written by ``write``. Values are
        strings (yaml's scalar parse); numeric timestamps pass through
        as strings because the file writes them that way.

    Raises:
        ActiveError: the marker file is absent, has no fenced-yaml
            block, or the block fails yaml parse.
    """
    path = _path(mill_dir)
    if not path.exists():
        raise ActiveError(
            f"No {_MARKER_NAME} at {path}. Is this a mill-spawned worktree?"
        )
    text = path.read_text(encoding="utf-8")
    # Find the first ```yaml fence and the matching ``` close.
    lines = text.splitlines()
    start: int | None = None
    for i, line in enumerate(lines):
        if line.strip() == "```yaml":
            start = i + 1
            break
    if start is None:
        raise ActiveError(f"{path} has no ```yaml block")
    end = None
    for j in range(start, len(lines)):
        if lines[j].strip() == "```":
            end = j
            break
    if end is None:
        raise ActiveError(f"{path} has an unclosed ```yaml block")
    block = "\n".join(lines[start:end])
    try:
        parsed = yaml.safe_load(block) or {}
    except yaml.YAMLError as exc:
        raise ActiveError(f"{path} yaml parse failed: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ActiveError(f"{path} yaml block is not a mapping")
    return {str(k): str(v) for k, v in parsed.items()}


def read_slug(mill_dir: Path) -> str:
    """
    Return the ``slug:`` value from the marker file.

    Convenience wrapper around ``read_all`` for callers that only need
    the slug (every downstream script / skill).

    Args:
        mill_dir: The ``.millhouse/`` directory inside the worktree.

    Raises:
        ActiveError: missing/malformed marker, or ``slug:`` key absent.
    """
    data = read_all(mill_dir)
    if "slug" not in data:
        raise ActiveError(
            f"{_path(mill_dir)} has no slug: key"
        )
    return data["slug"]
