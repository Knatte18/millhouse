"""
Baseline reviewer registry builder for unit tests.

Provides:
    make_minimal_registry(**overrides) -> dict
        Returns a baseline registry dict with sonnetmax and sonnetmax_tool entries.
    write_to(wiki_root: Path, **overrides) -> Path
        Writes the registry to wiki_root/reviewers.yaml and returns the path.

Tests that need _reviewers.load(wiki_root) to succeed should call write_to()
from their fixture to create the file on disk.
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

    Contains sonnetmax (bulk) and sonnetmax_tool (tool-use) single-specs.
    The **overrides kwargs are deep-merged into the baseline.
    """
    baseline: dict = {
        "sonnetmax": {
            "type": "single",
            "provider": "claude",
            "model": "claude-sonnet-4-6",
            "effort": "max",
        },
        "sonnetmax_tool": {
            "type": "single",
            "provider": "claude",
            "model": "claude-sonnet-4-6",
            "effort": "max",
            "tooluse": True,
        },
    }
    if overrides:
        return _deep_merge(baseline, overrides)
    return baseline


def write_to(wiki_root: Path, **overrides) -> Path:
    """Write the registry to wiki_root/reviewers.yaml and return the path.

    Creates wiki_root (and parents) if absent — fixture code typically assigns
    wiki_root = tmp_path / "wiki" without creating the directory first.
    """
    wiki_root.mkdir(parents=True, exist_ok=True)
    registry = make_minimal_registry(**overrides)
    out_path = wiki_root / "reviewers.yaml"
    out_path.write_text(yaml.safe_dump(registry, default_flow_style=False), encoding="utf-8")
    return out_path
