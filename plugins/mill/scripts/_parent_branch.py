"""
Resolve the parent branch of the active task.

mill-merge and mill-merge-in both need to know which branch to merge
to / from. The source of truth is the ``parent:`` field in
``<WIKI_PATH>/active/<slug>/status.md``'s top fenced-yaml block,
written by mill-spawn at the moment the task branch was created. If
that field is missing we fall through to an interactive prompt —
config-level overrides were considered and dropped (config.yaml is
meant to be stable per repo; parent-branch is per-task).

Public API:
    ParentBranchError — raised when no parent can be resolved non-interactively
    resolve(status_path, *, interactive=True) -> str
        Return the parent branch name. Raises ParentBranchError when
        status.md is missing the ``parent:`` row and ``interactive`` is
        False (auto-merge path in mill-go).

The status.md yaml-block parser lives in ``_status`` but is internal;
here we reuse the same ```yaml fence convention and hand-parse the
single row we care about. Keeps this module free of yaml dependency.
"""
from __future__ import annotations

from pathlib import Path


class ParentBranchError(Exception):
    """Raised when no parent branch can be resolved without a human."""


_YAML_FENCE = "```yaml"


def _read_parent_from_status(status_path: Path) -> str | None:
    """Return the ``parent:`` row value from status.md, or None.

    Scans the first fenced ```yaml``` block. Returns the first matching
    ``parent: <value>`` row with any surrounding quotes stripped.
    Missing file / absent row / malformed block → None; caller decides
    whether to prompt.
    """
    try:
        text = status_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    lines = text.splitlines()
    in_block = False
    for line in lines:
        if line.strip() == _YAML_FENCE:
            in_block = True
            continue
        if in_block and line.strip() == "```":
            return None
        if in_block and line.strip().startswith("parent:"):
            value = line.strip()[len("parent:"):].strip().strip('"').strip("'")
            return value or None
    return None


def resolve(status_path: Path, *, interactive: bool = True) -> str:
    """Return the task's parent branch.

    Lookup order:
    1. ``status.md`` ``parent:`` row.
    2. Interactive prompt — only when ``interactive=True``. The prompt
       reads a single line from stdin; the caller is responsible for
       only asking this in a tty-attached context.

    When ``interactive=False`` and no parent is in status.md, raises
    ``ParentBranchError`` so the auto-merge path in mill-go can halt
    gracefully and surface the shortfall to the user instead of
    blocking on stdin.
    """
    parent = _read_parent_from_status(status_path)
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


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        sp = Path(tmp) / "status.md"
        sp.write_text(
            "# Status\n"
            "\n"
            "```yaml\n"
            "phase: done\n"
            "task: Demo\n"
            "parent: main\n"
            "```\n",
            encoding="utf-8",
        )
        assert resolve(sp, interactive=False) == "main"
        print("PASS: resolve reads parent from status.md")

        sp.write_text(
            "# Status\n"
            "\n"
            "```yaml\n"
            "phase: done\n"
            "task: Demo\n"
            "```\n",
            encoding="utf-8",
        )
        try:
            resolve(sp, interactive=False)
        except ParentBranchError as exc:
            assert "No parent:" in str(exc)
            print(f"PASS: resolve raises on missing parent non-interactive -- {exc}")
        else:
            raise AssertionError("expected ParentBranchError")

    print("All _parent_branch smoke tests passed.")
