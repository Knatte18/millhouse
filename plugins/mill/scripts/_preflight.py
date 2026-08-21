"""
Detect missing cache helper modules and provide actionable error messages.

When the plugin cache is stale, imported helpers may be missing from the installed cache (e.g.
_archive_tag.py).
This module turns cryptic ModuleNotFoundErrors into actionable "refresh your cache" messages.

Public API:
    missing_helpers(required: list[str], scripts_dir: Path) -> list[str]
    Return the names from ``required`` for which ``<scripts_dir>/<name>.py``
    does not exist, or -- for a ``"module:attr"`` entry -- for which the
    module file exists but does not define ``attr``.

    check_helpers(required: list[str]) -> int
    Resolve the active scripts dir from ``CLAUDE_PLUGIN_ROOT`` and check for
    missing helpers. Print an ASCII actionable message to stderr if any are
    missing and return non-zero; otherwise return 0.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path


def missing_helpers(required: list[str], scripts_dir: Path) -> list[str]:
    """Return names from ``required`` that are missing under ``scripts_dir``.

    Each entry is either a bare module name (e.g. ``"_archive_tag"``), checked
    only for the existence of ``<scripts_dir>/<name>.py``, or a
    ``"module:attr"`` entry (e.g. ``"_parent_branch:check_liveness"``), which
    additionally imports the module and checks that it defines ``attr``.
    Any exception raised while importing a ``"module:attr"`` entry -- not
    just a missing attribute -- is treated as that entry being missing, so an
    unrelated import error (e.g. a syntax error in a stale cached file)
    never propagates out of this function.

    Note: the ``"module:attr"`` form fully imports (executes the top level
    of) the target module to check the attribute, not just a presence check
    -- a cost worth weighing for a heavier module, though harmless for the
    modules this repo currently passes through this form.

    Args:
        required: List of helper module names, each either bare
            (e.g. ["_archive_tag"]) or "module:attr" (e.g.
            ["_parent_branch:check_liveness"]).
        scripts_dir: Absolute path to the scripts directory to check.

    Returns:
        List of entries (verbatim, as passed in ``required``) that are
        missing. Empty list when all present.
    """
    missing = []
    for name in required:
        parts = name.split(":", 1)
        module_name = parts[0]
        attr_name = parts[1] if len(parts) > 1 else ""
        if not (scripts_dir / f"{module_name}.py").exists():
            missing.append(name)
            continue
        if not attr_name:
            continue
        try:
            spec = importlib.util.spec_from_file_location(
                module_name, scripts_dir / f"{module_name}.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception:  # noqa: BLE001
            missing.append(name)
            continue
        if not hasattr(module, attr_name):
            missing.append(name)
    return missing


def check_helpers(required: list[str]) -> int:
    """Check for missing helper modules and return non-zero + print message if missing.

    Resolves the active scripts dir from ``CLAUDE_PLUGIN_ROOT`` environment variable.
    When unset, falls back to this file's own directory (where _preflight.py itself exists).
    Prints an ASCII actionable error message to stderr if any required helper is missing,
    and returns non-zero.
    Returns 0 when all helpers are present.

    Args:
        required: List of helper module names, each either bare
            (e.g. ["_archive_tag"]) or "module:attr" (e.g.
            ["_parent_branch:check_liveness"]) for an attribute-level check
            -- see ``missing_helpers`` for the exact semantics.

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
