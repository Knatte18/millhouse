"""
Shortcut-wrapper writer for mill-setup Phase 4.7.

Renders ``plugins/mill/templates/shortcut-wrapper.cmd`` once per user-callable
script and writes the result to ``.millhouse/<script>.cmd``.  Idempotent: a
file that already contains identical content is not rewritten.

After writing CMD wrappers, any legacy ``.py`` or ``.ps1`` wrappers for the
same scripts that still exist in ``mill_dir`` are deleted (idempotent cleanup).

Public API:
    write_all(mill_dir, latest_path)
        Render and write every shortcut wrapper under ``mill_dir``.
        Returns the list of CMD paths that were created or overwritten.

Constants:
    SHORTCUT_SCRIPTS -- ordered list of script stems to wrap.
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
_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "shortcut-wrapper.cmd"


def write_all(mill_dir: Path, latest_path: Path) -> list[Path]:
    """
    Render and write all shortcut wrappers under ``mill_dir``.

    For each script in ``SHORTCUT_SCRIPTS``, the template is rendered and
    written to ``mill_dir / f"{script}.cmd"``.  A file is skipped when its
    on-disk content is already byte-equal to the rendered output.

    After the write loop, any legacy ``.py`` or ``.ps1`` wrappers whose stem
    matches a ``SHORTCUT_SCRIPTS`` entry are deleted.

    Args:
        mill_dir: Directory in which to write the wrappers (typically
            ``.millhouse/`` at the repo root). Must already exist.
        latest_path: Absolute path to the latest plugin cache entry;
            used to construct SCRIPT_PATH, MILL_PYTHON, and PLUGIN_ROOT tokens.

    Returns:
        List of ``Path`` objects for every .cmd file that was created or
        rewritten. Empty list if all wrappers were already up-to-date.
    """
    tokens = {
        "MILL_PYTHON": str(latest_path / ".venv" / "Scripts" / "python.exe"),
        "PLUGIN_ROOT": str(latest_path),
    }
    written: list[Path] = []
    for script in SHORTCUT_SCRIPTS:
        rendered = _render.render(
            _TEMPLATE_PATH,
            {**tokens, "SCRIPT": script, "SCRIPT_PATH": str(latest_path / "scripts" / f"{script}.py")},
        )
        target = mill_dir / f"{script}.cmd"
        if target.exists() and target.read_text(encoding="utf-8") == rendered:
            continue
        target.write_text(rendered, encoding="utf-8")
        written.append(target)
    for script in SHORTCUT_SCRIPTS:
        (mill_dir / f"{script}.py").unlink(missing_ok=True)
        (mill_dir / f"{script}.ps1").unlink(missing_ok=True)
    return written
