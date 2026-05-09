"""Test helper: writes minimal reviewers.yaml and config.yaml to wiki_root.

test_stub is special-cased in _reviewers.resolve and does not need an entry
in reviewers.yaml. config.yaml must exist for load_config (called internally
by resolve_path) to succeed.
"""
from __future__ import annotations

from pathlib import Path


def write_to(wiki_root: Path) -> None:
    """Write reviewers.yaml and config.yaml to wiki_root for test fixtures."""
    wiki_root.mkdir(parents=True, exist_ok=True)
    (wiki_root / "reviewers.yaml").write_text("{}\n", encoding="utf-8")
    (wiki_root / "config.yaml").write_text("roles: {}\n", encoding="utf-8")
