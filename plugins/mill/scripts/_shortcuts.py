"""
Shortcut-wrapper writer for mill-setup Phase 4.7.

Renders ``plugins/mill/templates/shortcut-wrapper.ps1`` once per user-callable
script and writes the result to ``.millhouse/<script>.ps1``.  Idempotent: a
file that already contains identical content is not rewritten.

After writing PS1 wrappers, any legacy ``.py`` wrappers for the same scripts
that still exist in ``mill_dir`` are deleted (idempotent cleanup).

Public API:
    write_all(mill_dir)
        Render and write every shortcut wrapper under ``mill_dir``.
        Returns the list of PS1 paths that were created or overwritten
        (legacy .py deletion is a side effect, not part of the return).

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
    "millpy-status",
    "millpy-inspect",
    "millpy-spawn",
    "millpy-claim",
    "millpy-cleanup",
    "millpy-abandon",
    "millpy-color",
    "millpy-terminal",
    "millpy-vscode",
    "millpy-wikipush",
]

# Template path relative to this file's package root.
_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "shortcut-wrapper.ps1"


def write_all(mill_dir: Path) -> list[Path]:
    """
    Render and write all shortcut wrappers under ``mill_dir``.

    For each script in ``SHORTCUT_SCRIPTS``, the template is rendered with
    ``{"SCRIPT": script_stem}`` and written to ``mill_dir / f"{script}.ps1"``.
    A file is skipped when its on-disk content is already byte-equal to the
    rendered output; only created or overwritten PS1 paths are returned.

    After the write loop, any legacy ``.py`` wrapper in ``mill_dir`` whose
    stem matches a ``SHORTCUT_SCRIPTS`` entry is deleted
    (``Path.unlink(missing_ok=True)``).  Deletion is a side effect and is
    not reflected in the return value.

    Args:
        mill_dir: Directory in which to write the wrappers (typically
            ``.millhouse/`` at the repo root). The directory must already
            exist; this function does not create it.

    Returns:
        List of ``Path`` objects for every PS1 file that was created or
        rewritten. Empty list if all wrappers were already up-to-date.
    """
    written: list[Path] = []
    for script in SHORTCUT_SCRIPTS:
        rendered = _render.render(_TEMPLATE_PATH, {"SCRIPT": script})
        target = mill_dir / f"{script}.ps1"
        if target.exists() and target.read_text(encoding="utf-8") == rendered:
            continue
        target.write_text(rendered, encoding="utf-8")
        written.append(target)
    for script in SHORTCUT_SCRIPTS:
        (mill_dir / f"{script}.py").unlink(missing_ok=True)
    return written
