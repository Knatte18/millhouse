"""
Baseline reviewer registry builder for unit tests.

Provides:
    make_minimal_registry(**overrides) -> dict
        Returns a baseline registry dict with sonnetmax (tool-use) and sonnetmax_bulk (bulk) entries.
    _write_registry_file(mill_dir: Path, registry: dict) -> Path
        Shared low-level writer: writes registry as YAML to mill_dir/agents.local.yaml.
    write_to(mill_dir: Path, **overrides) -> Path
        Builds a baseline-merged registry via make_minimal_registry() and writes it to
        mill_dir/agents.local.yaml -- the local-overlay layer _reviewers.load(hub_dir) merges
        from hub_dir/.millhouse/agents.local.yaml.

Tests that need _reviewers.load(hub_dir) to succeed should call write_to() from their
fixture to create the file on disk, passing the hub's .millhouse directory as mill_dir --
not the wiki root.
"""
from __future__ import annotations

from pathlib import Path

import yaml


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base. override wins on conflict."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def make_minimal_registry(**overrides) -> dict:
    """Return a baseline reviewer registry dict.

    Contains sonnetmax (tool-use) and sonnetmax_bulk (bulk) single-specs.
    The **overrides kwargs are deep-merged into the baseline.
    """
    baseline: dict = {
        "sonnetmax": {
            "type": "single",
            "provider": "claude",
            "model": "claude-sonnet-4-6",
            "effort": "max",
            "tooluse": True,
        },
        "sonnetmax_bulk": {
            "type": "single",
            "provider": "claude",
            "model": "claude-sonnet-4-6",
            "effort": "max",
            "tooluse": False,
        },
    }
    if overrides:
        return _deep_merge(baseline, overrides)
    return baseline


def _write_registry_file(mill_dir: Path, registry: dict) -> Path:
    """Write registry as YAML to mill_dir/agents.local.yaml and return the path.

    Creates mill_dir (and parents) if absent — fixture code typically assigns
    mill_dir = tmp_path / "hub" / ".millhouse" without creating the directory first.
    Shared by write_to() (baseline-merged content) and
    _test_helpers.write_local_overlay() (raw verbatim content).
    """
    mill_dir.mkdir(parents=True, exist_ok=True)
    out_path = mill_dir / "agents.local.yaml"
    out_path.write_text(yaml.safe_dump(registry, default_flow_style=False), encoding="utf-8")
    return out_path


def write_to(mill_dir: Path, **overrides) -> Path:
    """Write the registry to mill_dir/agents.local.yaml and return the path.

    Builds the registry from make_minimal_registry(**overrides) -- the baseline
    sonnetmax/sonnetmax_bulk entries plus any overrides -- then delegates the actual
    file write to _write_registry_file(). Callers must pass the hub's .millhouse
    directory as mill_dir, not the wiki root: _reviewers.load(hub_dir) merges the
    local-overlay layer from hub_dir/.millhouse/agents.local.yaml.
    """
    registry = make_minimal_registry(**overrides)
    return _write_registry_file(mill_dir, registry)
