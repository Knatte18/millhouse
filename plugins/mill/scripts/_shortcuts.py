"""
Shortcut-wrapper writer for mill-setup Phase 4.7.

Renders ``plugins/mill/templates/shortcut-wrapper.cmd`` (Windows) or ``shortcut-wrapper.sh``
(POSIX) once per user-callable script and writes the result to ``.millhouse/<script>.cmd`` or
``.millhouse/<script>.sh`` respectively.
Idempotent: a file that already contains identical content is not rewritten.

After writing wrappers, any legacy ``.py`` or ``.ps1`` wrappers for the same scripts that still
exist in ``mill_dir`` are deleted (idempotent cleanup).

Public API:
    write_all(mill_dir, latest_path)
    Render and write every CMD wrapper under ``mill_dir`` (Windows).
    write_all_sh(mill_dir, latest_path)
    Render and write every ``.sh`` wrapper under ``mill_dir`` (POSIX), executable bit set.
    Both return the list of paths that were created or overwritten.

Constants:
    SHORTCUT_SCRIPTS -- ordered list of script stems to wrap.
"""
from __future__ import annotations

from pathlib import Path

import _render

# User-callable v2 scripts and v1-ported entrypoints that are safe to expose as shortcuts.
# Excluded: millpy-skills-index, millpy-review-*, mill-merge.
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

# Template paths relative to this file's package root.
_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "shortcut-wrapper.cmd"
_TEMPLATE_PATH_SH = Path(__file__).resolve().parent.parent / "templates" / "shortcut-wrapper.sh"


def _write_wrappers(
    mill_dir: Path,
    latest_path: Path,
    *,
    template_path: Path,
    extension: str,
    mill_python: Path,
    executable: bool,
) -> list[Path]:
    """Render ``template_path`` for every ``SHORTCUT_SCRIPTS`` entry and write to ``mill_dir``.

    Shared by :func:`write_all` (``.cmd``) and :func:`write_all_sh` (``.sh``) -- the two differ only
    in template, extension, the ``MILL_PYTHON`` interpreter path, and whether the executable bit is
    set.
    """
    tokens = {"MILL_PYTHON": str(mill_python)}
    written: list[Path] = []
    for script in SHORTCUT_SCRIPTS:
        rendered = _render.render(
            template_path,
            {**tokens, "SCRIPT": script, "SCRIPT_PATH": str(latest_path / "scripts" / f"{script}.py")},
        )
        target = mill_dir / f"{script}.{extension}"
        if target.exists() and target.read_text(encoding="utf-8") == rendered:
            continue
        target.write_text(rendered, encoding="utf-8")
        if executable:
            target.chmod(target.stat().st_mode | 0o111)
        written.append(target)
    return written


def _clean_legacy_wrappers(mill_dir: Path) -> None:
    for script in SHORTCUT_SCRIPTS:
        (mill_dir / f"{script}.py").unlink(missing_ok=True)
        (mill_dir / f"{script}.ps1").unlink(missing_ok=True)


def write_all(mill_dir: Path, latest_path: Path) -> list[Path]:
    """
    Render and write all Windows ``.cmd`` shortcut wrappers under ``mill_dir``.

    For each script in ``SHORTCUT_SCRIPTS``, the template is rendered and written to ``mill_dir /
    f"{script}.cmd"``.
    A file is skipped when its on-disk content is already byte-equal to the rendered output.

    After the write loop, any legacy ``.py`` or ``.ps1`` wrappers whose stem matches a
    ``SHORTCUT_SCRIPTS`` entry are deleted.

    Args:
        mill_dir: Directory in which to write the wrappers (typically ``.millhouse/`` at the repo
            root).
            Must already exist.
        latest_path: Absolute path to the latest plugin cache entry; used to construct SCRIPT_PATH
            and MILL_PYTHON tokens.

    Returns:
        List of ``Path`` objects for every .cmd file that was created or rewritten.
        Empty list if all wrappers were already up-to-date.
    """
    written = _write_wrappers(
        mill_dir,
        latest_path,
        template_path=_TEMPLATE_PATH,
        extension="cmd",
        mill_python=latest_path / ".venv" / "Scripts" / "python.exe",
        executable=False,
    )
    _clean_legacy_wrappers(mill_dir)
    return written


def write_all_sh(mill_dir: Path, latest_path: Path) -> list[Path]:
    """
    Render and write all POSIX ``.sh`` shortcut wrappers under ``mill_dir``.

    POSIX counterpart of :func:`write_all` -- same idempotency and legacy-cleanup behaviour, but
    targets ``mill_dir / f"{script}.sh"``, resolves ``MILL_PYTHON`` to the venv's ``bin/python``, and
    marks each written file executable (``chmod +x``).

    Args:
        mill_dir: Directory in which to write the wrappers (typically ``.millhouse/`` at the repo
            root).
            Must already exist.
        latest_path: Absolute path to the latest plugin cache entry; used to construct SCRIPT_PATH
            and MILL_PYTHON tokens.

    Returns:
        List of ``Path`` objects for every .sh file that was created or rewritten.
        Empty list if all wrappers were already up-to-date.
    """
    written = _write_wrappers(
        mill_dir,
        latest_path,
        template_path=_TEMPLATE_PATH_SH,
        extension="sh",
        mill_python=latest_path / ".venv" / "bin" / "python",
        executable=True,
    )
    _clean_legacy_wrappers(mill_dir)
    return written
