"""
Shortcut-wrapper writer for mill-setup Phase 4.7.

Renders ``plugins/mill/templates/shortcut-wrapper.py`` once per user-callable
script and writes the result to ``.millhouse/<script>.py``.  Idempotent: a
file that already contains identical content is not rewritten.

Public API:
    write_all(mill_dir)
        Render and write every shortcut wrapper under ``mill_dir``.
        Returns the list of paths that were created or overwritten.

Constants:
    SHORTCUT_SCRIPTS — ordered list of script stems to wrap.
"""
from __future__ import annotations

from pathlib import Path

import _render

# User-callable v2 scripts and v1-ported entrypoints that are safe to expose
# as shortcuts.  Excluded: millpy-skills-index, millpy-review-*, mill-merge.
SHORTCUT_SCRIPTS: list[str] = [
    "millpy-add",
    "millpy-list",
    "millpy-status",
    "millpy-inspect",
    "millpy-spawn",
    "millpy-claim",
    "millpy-cleanup",
    "millpy-abandon",
    "millpy-color",
    "millpy-terminal",
    "millpy-vscode",
    "millpy-worktree",
    "millpy-fetch-issues",
]

# Template path relative to this file's package root.
_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "shortcut-wrapper.py"


def write_all(mill_dir: Path) -> list[Path]:
    """
    Render and write all shortcut wrappers under ``mill_dir``.

    For each script in ``SHORTCUT_SCRIPTS``, the template is rendered with
    ``{"SCRIPT": script_stem}`` and written to ``mill_dir / f"{script}.py"``.
    A file is skipped when its on-disk content is already byte-equal to the
    rendered output; only created or overwritten paths are returned.

    Args:
        mill_dir: Directory in which to write the wrappers (typically
            ``.millhouse/`` at the repo root). The directory must already
            exist; this function does not create it.

    Returns:
        List of ``Path`` objects for every file that was created or
        rewritten. Empty list if all wrappers were already up-to-date.
    """
    written: list[Path] = []
    for script in SHORTCUT_SCRIPTS:
        rendered = _render.render(_TEMPLATE_PATH, {"SCRIPT": script})
        target = mill_dir / f"{script}.py"
        if target.exists() and target.read_text(encoding="utf-8") == rendered:
            continue
        target.write_text(rendered, encoding="utf-8")
        written.append(target)
    return written
