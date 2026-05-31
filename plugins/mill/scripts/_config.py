"""
_config — shared config-loading helpers for mill entrypoints.

Exports
-------
load_config(hub_root, worktree_root) -> dict
    Load mill config deep-merged from plugin template, hub-root layer,
    local-stub layer, real config, and environment overrides. Merge order
    (lowest to highest precedence): plugin template -> hub overlay (if
    present) -> local stub -> real config -> env overrides. Returns the
    merged dict. Each layer is optional except the plugin template which
    is always present.

deep_merge(base, overlay) -> dict
    Shallow-recursive deep merge; overlay wins on scalar conflicts.

set_local_wiki_overrides(cfg_path, repo_url, branch) -> bool
    Write or update the ``wiki:`` block in a
    ``.millhouse/config.local.yaml`` file. Returns True if the file
    was created or modified, False if it was already up-to-date or
    both arguments were None.
"""
from __future__ import annotations

import copy
import os
import re
import sys
from pathlib import Path

import yaml
import _paths

__all__ = [
    "load_config",
    "deep_merge",
    "set_local_wiki_overrides",
    "ENV_REGISTRY",
    "apply_env_overrides",
    "walk_unknown_keys",
    "warn_unknown_keys",
    "resolve_plugin_template_path",
]

ENV_REGISTRY = {
    "MILL_DISCUSSION_REVIEWER": ("roles", "discussion-review", "holistic", "reviewer"),
    "MILL_PLAN_REVIEWER":       ("roles", "plan-review",       "holistic", "reviewer"),
    "MILL_PLAN_BATCH_REVIEWER": ("roles", "plan-review",       "batch",    "reviewer"),
    "MILL_CODE_REVIEWER":       ("roles", "code-review",       "holistic", "reviewer"),
    "MILL_CODE_BATCH_REVIEWER": ("roles", "code-review",       "batch",    "reviewer"),
    "MILL_IMPLEMENTER":         ("roles", "implementer",       "model"),
}


class ConfigError(ValueError):
    pass


# POSIX env-var convention: uppercase only; lowercase patterns are literal.
_ENV_INTERP_RE = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)(:-(.*?))?\}")


def apply_env_overrides(cfg: dict) -> dict:
    """Apply environment variable overrides to a config dict.

    For each entry in ENV_REGISTRY, reads the corresponding environment variable.
    If the value is non-empty, walks the key tuple in the config and sets the final
    segment to the env value. Empty-string env values are treated as unset.

    Args:
        cfg: Base configuration dict.

    Returns:
        New dict with env overrides applied.
    """
    result = copy.deepcopy(cfg)
    for env_var, key_tuple in ENV_REGISTRY.items():
        env_val = os.environ.get(env_var, "")
        if not env_val:
            continue
        current = result
        for seg in key_tuple[:-1]:
            current = current.setdefault(seg, {})
        current[key_tuple[-1]] = env_val
    return result


def walk_unknown_keys(actual: dict, template: dict, prefix: str = "") -> list[str]:
    """Find keys present in actual but not in template.

    Recurses into nested dicts only when both actual[key] and template[key] are
    dicts. Lists are treated as leaves (not descended).

    Args:
        actual:  The actual configuration dict.
        template: The template configuration dict.
        prefix:  Current key path prefix (for recursion).

    Returns:
        List of dotted key paths (e.g., ["a.b.c", "x.y"]).
    """
    unknown = []
    for key, actual_val in actual.items():
        current_path = f"{prefix}.{key}" if prefix else key
        if key not in template:
            unknown.append(current_path)
        elif isinstance(actual_val, dict) and isinstance(template.get(key), dict):
            unknown.extend(walk_unknown_keys(actual_val, template[key], current_path))
    return unknown


def warn_unknown_keys(actual: dict, template: dict, source_label: str) -> None:
    """Emit warnings to stderr for unknown keys in actual config.

    Args:
        actual: The actual configuration dict.
        template: The template configuration dict.
        source_label: Label for the source (e.g., "mill-config.yaml").
    """
    unknown = walk_unknown_keys(actual, template)
    for path in unknown:
        print(f"[config] unknown key: {path} (in {source_label})", file=sys.stderr)


def resolve_plugin_template_path(filename: str) -> Path:
    """Resolve a plugin template path.

    Uses ${CLAUDE_PLUGIN_ROOT}/templates/<filename> when the env var is set,
    otherwise falls back to the source-tree path relative to this file.

    Args:
        filename: The template filename (e.g., "mill-config.yaml").

    Returns:
        Absolute Path to the template file.
    """
    plugin_root_env = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
    if plugin_root_env:
        candidate = Path(plugin_root_env).resolve() / "templates" / filename
        if not candidate.exists():
            print(f"[config] CLAUDE_PLUGIN_ROOT={plugin_root_env!r}: {candidate} not found, falling back to source tree", file=sys.stderr)
            return Path(__file__).resolve().parent.parent / "templates" / filename
        return candidate
    return Path(__file__).resolve().parent.parent / "templates" / filename


def load_config(hub_root: Path, worktree_root: Path) -> dict:
    """Load mill config with overlay from plugin template, repo layer, and local layer.

    Merge order (lowest to highest precedence):
    1. Plugin template (mill-config.yaml)
    2. Repo layer (mill-config.yaml at hub root, or absent if not present)
    3. Local stub (worktree_root / .millhouse / config.local.yaml)
    4. Local real (when hub_relative_path is set)
    5. Environment variable overrides

    Returns an empty dict when no sources are found.

    Args:
        hub_root:      Absolute path to the hub directory.
        worktree_root: Absolute path to the worktree git repository root.

    Returns:
        Merged configuration dict (may be empty).
    """
    # 1. Load plugin template
    template_path = resolve_plugin_template_path("mill-config.yaml")
    if template_path.exists():
        cfg = yaml.safe_load(template_path.read_text(encoding="utf-8")) or {}
    else:
        cfg = {}
    template_cfg = copy.deepcopy(cfg)

    # Augment template_cfg with the worktree-local template when it exists and
    # differs from the resolved cache template (handles cache-lag in self-modifying repos).
    _worktree_template = worktree_root / "plugins" / "mill" / "templates" / "mill-config.yaml"
    if _worktree_template.exists() and _worktree_template.resolve() != template_path.resolve():
        _wt_cfg = yaml.safe_load(_worktree_template.read_text(encoding="utf-8")) or {}
        template_cfg = deep_merge(template_cfg, _wt_cfg)

    # 2. Resolve repo-layer sources
    mill_cfg_path = _paths.resolve_mill_config_path(hub_root)

    # 3. Apply repo-layer merge logic
    source_label = ""
    if mill_cfg_path.exists():
        repo_cfg = yaml.safe_load(mill_cfg_path.read_text(encoding="utf-8")) or {}
        cfg = deep_merge(cfg, repo_cfg)
        source_label = "mill-config.yaml"

    # 4. Apply stub-aware local config logic (preserved from existing code)
    stub_path = worktree_root / ".millhouse" / "config.local.yaml"
    hub_subpath = "."
    if stub_path.exists():
        stub_data = yaml.safe_load(stub_path.read_text(encoding="utf-8")) or {}
        cfg = deep_merge(cfg, stub_data)
        source_label = "config.local.yaml"
        hub_subpath = stub_data.get("hub_relative_path", ".")

    if hub_subpath != ".":
        real_path = worktree_root / hub_subpath / ".millhouse" / "config.local.yaml"
        if real_path.exists():
            real_cfg = yaml.safe_load(real_path.read_text(encoding="utf-8")) or {}
            cfg = deep_merge(cfg, real_cfg)

    # 5. Validate unknown keys
    check_cfg = {k: v for k, v in cfg.items() if k != "hub_relative_path"}
    warn_unknown_keys(check_cfg, template_cfg, source_label or "merged config")

    # 6. Apply environment variable overrides
    cfg = apply_env_overrides(cfg)

    # 7. Apply environment variable interpolation
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
        elif val is None and isinstance(out.get(key), dict):
            continue
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
