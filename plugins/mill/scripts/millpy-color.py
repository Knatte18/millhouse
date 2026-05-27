"""
mill-color — override the current worktree's VS Code title-bar color.

Rewrites ``.vscode/settings.json`` in the current working directory with
the selected palette color. The window title is preserved from any existing
settings.json; if settings.json is absent the title is derived from the repo
short name (via ``_paths.resolve_short_name``) and the slug derived from the
current git branch (via ``_marker.slug_from_branch``).

Usage:
    python mill-color.py <color-name>
    Valid color names: green, purple, blue, yellow, red, cyan, indigo, orange

Exit codes:
    0 — settings.json written successfully
    1 — any error (not in git repo, cannot load config)
    2 — invalid or missing color-name argument
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import _marker
import _vscode
from _config import load_config as _load_config
from _paths import resolve_git_root, resolve_hub_path, resolve_short_name, resolve_wiki_path
from _spawn_core import WORKTREE_COLOR_NAME_TO_HEX

_EXIT_USAGE = 2


def _read_existing_window_title(settings_path: Path) -> str | None:
    """Return ``window.title`` from an existing settings.json, or None."""
    if not settings_path.exists():
        return None
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        return data.get("window.title") or None
    except (OSError, ValueError):
        return None


def main(argv: list[str] | None = None) -> int:
    """Set the VS Code title-bar color for the current worktree.

    Reads an optional existing ``window.title`` from ``.vscode/settings.json``
    to preserve it. Derives a fallback title from the repo short name and
    active slug when settings.json is absent.

    Args:
        argv: Argument vector. Defaults to ``sys.argv[1:]``.

    Returns:
        Exit code (0 = success, 2 = invalid color name, 1 = other error).
    """
    valid_names = ", ".join(sorted(WORKTREE_COLOR_NAME_TO_HEX))
    parser = argparse.ArgumentParser(
        prog="mill-color",
        description="Override the current worktree's VS Code titleBar color.",
    )
    parser.add_argument(
        "color_name",
        help=f"Palette color name; one of: {valid_names}",
    )
    args = parser.parse_args(argv)

    color_name = args.color_name.strip().lower()
    if color_name not in WORKTREE_COLOR_NAME_TO_HEX:
        print(
            f"[mill-color] {color_name!r} is not a valid color. Valid: {valid_names}",
            file=sys.stderr,
        )
        return _EXIT_USAGE
    color_hex = WORKTREE_COLOR_NAME_TO_HEX[color_name]

    git_root = resolve_git_root()
    settings_path = resolve_hub_path() / ".vscode" / "settings.json"

    # Preserve the existing window title; do NOT clobber it.
    existing_title = _read_existing_window_title(settings_path)

    if existing_title is None:
        # Derive a title from config + active marker.
        wiki_path = None
        try:
            wiki_path = resolve_wiki_path(git_root)
            cfg = _load_config(resolve_hub_path(), resolve_hub_path())
        except SystemExit:
            cfg = {}
        short_name = resolve_short_name(cfg, git_root.name)

        slug: str | None = None
        if wiki_path is not None:
            try:
                slug = _marker.slug_from_branch(git_root, wiki_path, cfg)
            except _marker.MarkerError:
                pass

        window_title = f"{short_name}: {slug}" if slug else short_name
    else:
        window_title = existing_title

    _vscode.write_settings(
        color_hex=color_hex,
        target=settings_path,
        window_title=window_title,
    )
    print(f"color: {color_name} {color_hex}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
