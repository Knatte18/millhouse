"""
Detect missing cache helper modules and provide actionable error messages.

When the plugin cache is stale, imported helpers may be missing from the
installed cache (e.g. _archive_tag.py). This module turns cryptic
ModuleNotFoundErrors into actionable "refresh your cache" messages.

Public API:
    missing_helpers(required: list[str], scripts_dir: Path) -> list[str]
        Return the names from ``required`` for which ``<scripts_dir>/<name>.py``
        does not exist.

    check_helpers(required: list[str]) -> int
        Resolve the active scripts dir from ``CLAUDE_PLUGIN_ROOT`` and check for
        missing helpers. Print an ASCII actionable message to stderr if any are
        missing and return non-zero; otherwise return 0.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def missing_helpers(required: list[str], scripts_dir: Path) -> list[str]:
    """Return names from ``required`` where ``<scripts_dir>/<name>.py`` does not exist.

    Args:
        required: List of helper module names (e.g. ["_archive_tag"]).
        scripts_dir: Absolute path to the scripts directory to check.

    Returns:
        List of names from ``required`` for which the corresponding .py file
        is missing. Empty list when all present.
    """
    missing = []
    for name in required:
        if not (scripts_dir / f"{name}.py").exists():
            missing.append(name)
    return missing


def check_helpers(required: list[str]) -> int:
    """Check for missing helper modules and return non-zero + print message if missing.

    Resolves the active scripts dir from ``CLAUDE_PLUGIN_ROOT`` environment
    variable. When unset, falls back to this file's own directory (where
    _preflight.py itself exists). Prints an ASCII actionable error message
    to stderr if any required helper is missing, and returns non-zero.
    Returns 0 when all helpers are present.

    Args:
        required: List of helper module names (e.g. ["_archive_tag"]).

    Returns:
        0 when all helpers present, non-zero when any are missing.
    """
    # Resolve scripts directory
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if plugin_root:
        scripts_dir = Path(plugin_root) / "scripts"
    else:
        # Fallback to this file's own directory
        scripts_dir = Path(__file__).resolve().parent

    missing = missing_helpers(required, scripts_dir)
    if not missing:
        return 0

    # Format message
    missing_str = ", ".join(missing)
    msg = (
        f"[preflight] error -- missing cache helper module(s): {missing_str}\n"
        f"[preflight] action -- reinstall or refresh the plugin cache and retry.\n"
    )
    sys.stderr.write(msg)
    return 1


if __name__ == "__main__":
    # Allow invocation as CLI: python _preflight.py _archive_tag _other_helper
    if len(sys.argv) < 2:
        print("Usage: python _preflight.py HELPER [HELPER ...]", file=sys.stderr)
        sys.exit(1)
    helpers = sys.argv[1:]
    sys.exit(check_helpers(helpers))
