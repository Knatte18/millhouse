"""
_config — shared config-loading helpers for mill entrypoints.

Exports
-------
load_config(wiki_path, worktree_root) -> dict
    Load ``wiki/config.yaml`` deep-merged with
    ``~/.millhouse/config.machine.yaml`` and
    ``.millhouse/config.local.yaml``.  Machine layer (read via
    ``_machine.load_layer``) lands between wiki and worktree layers;
    later layers win on key conflicts.  Returns an empty dict when
    ``wiki/config.yaml`` does not exist (lenient form used by
    mill-color, mill-terminal, mill-vscode, and mill-spawn).

deep_merge(base, overlay) -> dict
    Shallow-recursive deep merge; overlay wins on scalar conflicts.

set_local_wiki_overrides(cfg_path, repo_url, branch) -> bool
    Write or update the ``wiki:`` block in a
    ``.millhouse/config.local.yaml`` file. Returns True if the file
    was created or modified, False if it was already up-to-date or
    both arguments were None.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import yaml
import _machine


class ConfigError(ValueError):
    pass


# POSIX env-var convention: uppercase only; lowercase patterns are literal.
_ENV_INTERP_RE = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)(:-(.*?))?\}")


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

    The machine layer at ``~/.millhouse/config.machine.yaml`` is read
    between the wiki and worktree-stub layers via ``_machine.load_layer()``.
    Missing machine file → ``_machine.load_layer`` returns ``{}`` and the
    merge is a no-op.

    Returns an empty dict when ``wiki/config.yaml`` does not exist.
    Callers that require the file to be present should add their own
    guard after calling this function.

    Args:
        wiki_path:     Absolute path to the wiki repository root.
        worktree_root: Absolute path to the worktree git repository root.

    Returns:
        Merged configuration dict (may be empty). Merge order, lowest to
        highest precedence: wiki → machine → worktree-stub → worktree-real.
    """
    shared_path = wiki_path / "config.yaml"
    cfg: dict = {}
    if shared_path.exists():
        cfg = yaml.safe_load(shared_path.read_text(encoding="utf-8")) or {}

    cfg = deep_merge(cfg, _machine.load_layer())

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
    cfg = _interpolate_env(cfg)
    return cfg


def set_local_wiki_overrides(
    cfg_path: Path,
    repo_url: str | None,
    branch: str | None,
) -> bool:
    """Write or update the ``wiki:`` block in a ``.millhouse/config.local.yaml`` file.

    If both ``repo_url`` and ``branch`` are None this is a no-op and returns False
    immediately — the caller passed no overrides to apply.

    Otherwise the file is read (if it exists), the ``wiki:`` sub-dict is created or
    updated with only the non-None arguments (partial-update semantics: a key absent
    from the call is not removed from the file), and the result is written back using
    ``yaml.safe_dump(sort_keys=False)``.  If the resulting text is byte-for-byte
    identical to the existing file the function returns False without touching the file.

    Note: comments in the existing file are lost on rewrite — this is the documented
    trade-off for this gitignored, per-machine file.

    Args:
        cfg_path: Absolute path to the config file (need not exist yet).
        repo_url: URL to store under ``wiki.repo_url``, or None to leave unchanged.
        branch:   Branch name to store under ``wiki.branch``, or None to leave unchanged.

    Returns:
        True if the file was created or modified, False if no-op.
    """
    if repo_url is None and branch is None:
        return False

    if cfg_path.exists():
        existing_text = cfg_path.read_text(encoding="utf-8")
        data = yaml.safe_load(existing_text) or {}
    else:
        existing_text = None
        data = {}

    existing_wiki = data.get("wiki") or {}
    new_wiki = dict(existing_wiki)
    if repo_url is not None:
        new_wiki["repo_url"] = repo_url
    if branch is not None:
        new_wiki["branch"] = branch
    data["wiki"] = new_wiki

    new_text = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)

    if existing_text is not None and existing_text == new_text:
        return False

    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(new_text, encoding="utf-8")
    return True


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


def _substitute_string(value: str, key_path: str) -> str:
    """Substitute ${VAR} and ${VAR:-default} patterns in a string.

    Args:
        value:    The string to process.
        key_path: Dotted key path for error messages.

    Returns:
        String with all env-var patterns substituted.

    Raises:
        ConfigError: If an unset variable has no default.
    """

    def replace_match(match):
        var_name = match.group(1)
        has_default = match.group(2) is not None
        default_value = match.group(3) if has_default else None

        if var_name in os.environ:
            return os.environ[var_name]
        elif has_default:
            return default_value
        else:
            raise ConfigError(
                f"Unset env var '{var_name}' at config key '{key_path}'"
            )

    return _ENV_INTERP_RE.sub(replace_match, value)


def _interpolate_env(cfg, key_path: str = ""):
    """Recursively interpolate env-var patterns in configuration values.

    Args:
        cfg:      Configuration (dict, list, str, or scalar).
        key_path: Current dotted/bracketed key path.

    Returns:
        Configuration with all string values interpolated.

    Raises:
        ConfigError: If an unset variable has no default.
    """
    if isinstance(cfg, dict):
        return {
            k: _interpolate_env(
                v, f"{key_path}.{k}" if key_path else k
            )
            for k, v in cfg.items()
        }
    elif isinstance(cfg, list):
        return [
            _interpolate_env(v, f"{key_path}[{i}]")
            for i, v in enumerate(cfg)
        ]
    elif isinstance(cfg, str):
        return _substitute_string(cfg, key_path)
    else:
        return cfg
