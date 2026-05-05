"""
_config — shared config-loading helpers for mill entrypoints.

Exports
-------
load_config(wiki_path, worktree_root) -> dict
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


def load_config(wiki_path: Path, worktree_root: Path) -> dict:
    """Load ``wiki/config.yaml`` deep-merged with ``.millhouse/config.local.yaml``.

    Uses a two-step stub-aware read: first reads the stub at
    ``worktree_root / .millhouse / config.local.yaml`` (which may contain
    only ``hub_relative_path:``); if the stub declares a non-root
    ``hub_relative_path``, reads the real config from
    ``worktree_root / hub_subpath / .millhouse / config.local.yaml`` and
    deep-merges it on top.  Both layers are merged into the wiki config so
    ``hub_relative_path`` from the stub is available alongside all
    operational keys from the real config.

    Returns an empty dict when ``wiki/config.yaml`` does not exist.
    Callers that require the file to be present should add their own
    guard after calling this function.

    Args:
        wiki_path:     Absolute path to the wiki repository root.
        worktree_root: Absolute path to the worktree git repository root.

    Returns:
        Merged configuration dict (may be empty).
    """
    shared_path = wiki_path / "config.yaml"
    cfg: dict = {}
    if shared_path.exists():
        cfg = yaml.safe_load(shared_path.read_text(encoding="utf-8")) or {}

    stub_path = worktree_root / ".millhouse" / "config.local.yaml"
    hub_subpath = "."
    if stub_path.exists():
        stub_data = yaml.safe_load(stub_path.read_text(encoding="utf-8")) or {}
        cfg = deep_merge(cfg, stub_data)
        hub_subpath = stub_data.get("hub_relative_path", ".")

    if hub_subpath != ".":
        real_path = worktree_root / hub_subpath / ".millhouse" / "config.local.yaml"
        if real_path.exists():
            real_cfg = yaml.safe_load(real_path.read_text(encoding="utf-8")) or {}
            cfg = deep_merge(cfg, real_cfg)
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
