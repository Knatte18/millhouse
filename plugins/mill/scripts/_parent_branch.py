"""
Resolve the parent branch of the active task.

mill-merge and mill-merge-in both need to know which branch to merge to / from.
The source of truth is the ``parent:`` field in ``<WIKI_PATH>/active/<slug>/status.md``'s top fenced-yaml block, written by mill-spawn at the moment the task branch was created.
If that field is missing we fall through to an interactive prompt — config-level overrides were considered and dropped (config.yaml is meant to be stable per repo; parent-branch is per-task).

Public API:
    ParentBranchError — raised when no parent can be resolved non-interactively resolve(status_path, *, interactive=True, expected_slug=None) -> str Return the parent branch name.
    Raises ParentBranchError when status.md is missing the ``parent:`` row and ``interactive`` is False (auto-merge path in mill-go).
    When ``expected_slug`` is given and status.md's ``slug:`` row does not match it, the
    ``parent:`` row is treated as absent — protects against reading a stacked-branch worktree's stale status.md by identity.
    resolve_for_codeguide(status_path, *, expected_slug=None) -> str | None Non-interactive wrapper around resolve() that swallows ParentBranchError and returns None instead of raising, for callers (e.g.
    git-commit) that must never block on a missing parent.

The status.md yaml-block parser lives in ``_status`` but is internal;
here we reuse the same ```yaml fence convention and hand-parse the single row we care about. Keeps this module free of yaml dependency.
"""
from __future__ import annotations

from pathlib import Path


class ParentBranchError(Exception):
    """Raised when no parent branch can be resolved without a human."""


_YAML_FENCE = "```yaml"


def _read_parent_from_status(
    status_path: Path, *, expected_slug: str | None = None
) -> str | None:
    """Return the ``parent:`` row value from status.md, or None.

    Scans the first fenced ```yaml``` block.
    Returns the first matching ``parent: <value>`` row with any surrounding quotes stripped.
    Missing file / absent row / malformed block -> None;
    caller decides whether to prompt.

    Args:
        expected_slug: when not None, also scans the same block for a ``slug:`` row.
            If that row is present and its stripped value differs from ``expected_slug``, the function returns None -- identical to the "no parent: row" case -- even though a ``parent:`` row was found.
            This guards against resolving the parent branch from a different task's status.md (stacked worktrees can share a checked-out file layout).
            A ``slug:`` row that is absent,
            or an ``expected_slug`` of None, never triggers this check.
    """
    try:
        text = status_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    lines = text.splitlines()
    in_block = False
    parent_value: str | None = None
    slug_value: str | None = None
    for line in lines:
        if line.strip() == _YAML_FENCE:
            in_block = True
            continue
        if in_block and line.strip() == "```":
            break
        if in_block and line.strip().startswith("parent:"):
            parent_value = line.strip()[len("parent:"):].strip().strip('"').strip("'")
        if in_block and line.strip().startswith("slug:"):
            slug_value = line.strip()[len("slug:"):].strip().strip('"').strip("'")
    if expected_slug is not None and slug_value is not None and slug_value != expected_slug:
        return None
    return parent_value or None


def resolve(
    status_path: Path, *, interactive: bool = True, expected_slug: str | None = None
) -> str:
    """Return the task's parent branch.

    Lookup order:
    1. ``status.md`` ``parent:`` row.
    2. Interactive prompt — only when ``interactive=True``.
        The prompt reads a single line from stdin;
        the caller is responsible for only asking this in a tty-attached context.

    When ``interactive=False`` and no parent is in status.md, raises ``ParentBranchError`` so the auto-merge path in mill-go can halt gracefully and surface the shortfall to the user instead of blocking on stdin.

    Args:
        expected_slug: forwarded to ``_read_parent_from_status``.
        A mismatched ``slug:`` row makes the lookup behave exactly as if ``parent:`` were absent -- falling through to the prompt (or ``ParentBranchError`` when non-interactive) below.
    """
    parent = _read_parent_from_status(status_path, expected_slug=expected_slug)
    if parent:
        return parent
    if not interactive:
        raise ParentBranchError(
            f"No parent: in {status_path} and non-interactive context; "
            "set status.md's parent: row and re-run mill-merge manually."
        )
    prompt = (
        f"[_parent_branch] status.md has no parent: row. "
        f"Enter parent branch name (e.g. main): "
    )
    try:
        response = input(prompt).strip()
    except EOFError:
        raise ParentBranchError(
            f"No parent: in {status_path} and stdin not attached"
        )
    if not response:
        raise ParentBranchError("Empty parent branch name")
    return response


def resolve_for_codeguide(
    status_path: Path, *, expected_slug: str | None = None
) -> str | None:
    """Return the task's parent branch for codeguide-update, or None.

    A non-interactive, exception-swallowing wrapper around ``resolve()`` for callers (e.g. ``git-commit``) that must degrade silently rather than block a commit over a missing or unreadable parent branch.
    Calls ``resolve(status_path, interactive=False, expected_slug=expected_slug)``;
    on ``ParentBranchError`` (missing ``parent:`` row, unreadable status.md, or a mismatched ``slug:`` row) returns ``None`` instead of raising or prompting.
    """
    try:
        return resolve(status_path, interactive=False, expected_slug=expected_slug)
    except ParentBranchError:
        return None
