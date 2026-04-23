"""
VS Code workspace-settings rendering helper.

Both `mill-setup` (the bootstrap skill, M1.2) and `mill-spawn` (the worktree
creation script, M3.1) need to write a `.vscode/settings.json` that controls
the title-bar colour and window title for the workspace. The hub gets a
canonical green; each worktree gets a deterministic non-green colour from a
fixed palette (logic for that lives in `mill-spawn` itself).

Both callers share the *rendering and writing* of the JSON. They do **not**
share the *decision* of when to write — that is judgment-heavy for the
skill (existing user content, GitHub-default vs custom) and trivial for
the worktree script (fresh directory, always write). This module handles
only the shared mechanical part: substitute placeholders into the
canonical template, optionally write to a target path.

Public API:
    render_settings(color_hex, window_title)
        Return the rendered settings.json content as a string. Useful when
        the caller wants to inspect or further-process the rendered text
        before writing.
    write_settings(color_hex, window_title, target)
        Render and write the settings.json to ``target``, creating parent
        directories as needed. Overwrites unconditionally — caller is
        responsible for any backup or skip decisions.
"""
from __future__ import annotations

import sys
from pathlib import Path

import _render

_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "vscode-settings.json"


def render_settings(color_hex: str, window_title: str) -> str:
    """
    Render the vscode-settings.json template with the given values.

    Substitutes ``<COLOR_HEX>`` and ``<WINDOW_TITLE>`` into the canonical
    template at ``plugins/mill/templates/vscode-settings.json``. Raises
    ``KeyError`` if the template gains additional placeholders without
    callers being updated to supply them.

    Args:
        color_hex: Title-bar colour in CSS hex form, e.g. ``"#2d7d46"``.
            Used for both ``titleBar.activeBackground`` and
            ``titleBar.inactiveBackground`` so the colour is visible
            whether the window is focused or not.
        window_title: The literal value for VS Code's ``window.title``
            setting. May contain VS Code variables like
            ``${activeEditorShort}`` — they pass through unevaluated and
            VS Code expands them at runtime.

    Returns:
        The rendered settings.json text, ready to write to disk.
    """
    return _render.render(
        _TEMPLATE_PATH,
        {"COLOR_HEX": color_hex, "WINDOW_TITLE": window_title},
    )


def write_settings(color_hex: str, window_title: str, target: Path) -> None:
    """
    Render the template and write it to ``target``, overwriting any existing file.

    Creates the parent directory chain if missing. Does not back up an
    existing target — backup or skip decisions are the caller's
    responsibility (see `mill-setup` Phase 7 for the judgment logic).

    Args:
        color_hex: Title-bar colour (see ``render_settings``).
        window_title: VS Code ``window.title`` value (see ``render_settings``).
        target: Path to write the file to, typically
            ``<workspace>/.vscode/settings.json``.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_settings(color_hex, window_title), encoding="utf-8")
