"""
_config — shared config-loading helpers for mill entrypoints.

Exports
-------
load_config(wiki_path, git_root) -> dict
    Load ``wiki/config.yaml`` deep-merged with
    ``.millhouse/config.local.yaml``.  Returns an empty dict when
    ``wiki/config.yaml`` does not exist (lenient form used by
    mill-color, mill-terminal, mill-vscode, mill-worktree, and
    mill-spawn).

deep_merge(base, overlay) -> dict
    Shallow-recursive deep merge; overlay wins on scalar conflicts.
"""
from __future__ import annotations

from pathlib import Path

import yaml


def load_config(wiki_path: Path, git_root: Path) -> dict:
    """Load ``wiki/config.yaml`` deep-merged with ``.millhouse/config.local.yaml``.

    Returns an empty dict when ``wiki/config.yaml`` does not exist.
    Callers that require the file to be present should add their own
    guard after calling this function.

    Args:
        wiki_path: Absolute path to the wiki repository root.
        git_root:  Absolute path to the hub git repository root.

    Returns:
        Merged configuration dict (may be empty).
    """
    shared_path = wiki_path / "config.yaml"
    cfg: dict = {}
    if shared_path.exists():
        cfg = yaml.safe_load(shared_path.read_text(encoding="utf-8")) or {}

    local_path = git_root / ".millhouse" / "config.local.yaml"
    if local_path.exists():
        local_cfg = yaml.safe_load(local_path.read_text(encoding="utf-8")) or {}
        cfg = deep_merge(cfg, local_cfg)
    return cfg


def deep_merge(base: dict, overlay: dict) -> dict:
    """Shallow-recursive deep merge; overlay wins on scalar conflicts.

    Args:
        base:    Base dictionary.
        overlay: Dictionary whose values take precedence.

    Returns:
        New dict containing the merged result.
    """
    out = dict(base)
    for key, val in overlay.items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], val)
        else:
            out[key] = val
    return out
