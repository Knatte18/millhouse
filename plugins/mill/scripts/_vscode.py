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
    render_settings(color_hex, *, window_title=None, short_name=None, slug=None)
        Return the rendered settings.json content as a string. Title is derived
        from window_title (wins) or from short_name[: slug] (hub/worktree form).
        Raises ValueError when neither window_title nor short_name is supplied.
    write_settings(color_hex, target, *, window_title=None, short_name=None, slug=None)
        Render and write the settings.json to ``target``, creating parent
        directories as needed. Overwrites unconditionally — caller is
        responsible for any backup or skip decisions.
"""
from __future__ import annotations

from pathlib import Path

import _render

_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "vscode-settings.json"


def _derive_window_title(
    window_title: str | None,
    short_name: str | None,
    slug: str | None,
) -> str:
    if window_title is not None:
        return window_title
    if short_name is not None:
        return f"{short_name}: {slug}" if slug is not None else short_name
    raise ValueError(
        "Either window_title or short_name must be provided"
    )


def render_settings(
    color_hex: str,
    *,
    window_title: str | None = None,
    short_name: str | None = None,
    slug: str | None = None,
) -> str:
    """
    Render the vscode-settings.json template with the given values.

    Derives the ``window.title`` value from ``window_title`` (wins when
    present), or from ``short_name`` optionally combined with ``slug``
    (``"short_name: slug"`` for the worktree form; ``"short_name"`` for the
    hub form). Raises ``ValueError`` when neither is supplied.

    Args:
        color_hex: Title-bar colour in CSS hex form, e.g. ``"#2d7d46"``.
        window_title: Explicit ``window.title`` value; wins over short_name.
        short_name: Repository short name for the hub or worktree title.
        slug: Task slug; combined with short_name as ``"short_name: slug"``.

    Returns:
        The rendered settings.json text, ready to write to disk.

    Raises:
        ValueError: Neither ``window_title`` nor ``short_name`` was supplied.
    """
    title = _derive_window_title(window_title, short_name, slug)
    return _render.render(
        _TEMPLATE_PATH,
        {"COLOR_HEX": color_hex, "WINDOW_TITLE": title},
    )


def write_settings(
    color_hex: str,
    target: Path,
    *,
    window_title: str | None = None,
    short_name: str | None = None,
    slug: str | None = None,
) -> None:
    """
    Render the template and write it to ``target``, overwriting any existing file.

    Creates the parent directory chain if missing. Title is derived from
    ``window_title`` or ``short_name`` + optional ``slug`` (see
    ``render_settings``). Does not back up an existing target.

    Args:
        color_hex: Title-bar colour (see ``render_settings``).
        target: Path to write the file to.
        window_title: Explicit ``window.title`` value.
        short_name: Repository short name.
        slug: Task slug (combined with short_name for worktree form).

    Raises:
        ValueError: Neither ``window_title`` nor ``short_name`` was supplied.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        render_settings(color_hex, window_title=window_title, short_name=short_name, slug=slug),
        encoding="utf-8",
    )
