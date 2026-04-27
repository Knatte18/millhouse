"""Unit tests for plugins/mill/scripts/_config.py.

Covers:
  - load_config: shared config present → returned as dict
  - load_config: local override wins via deep_merge
  - load_config: wiki config absent → returns empty dict
  - deep_merge: scalar in overlay wins over scalar in base
  - deep_merge: nested dicts are merged recursively
  - deep_merge: empty overlay leaves base unchanged
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS_DIR = HUB / "plugins" / "mill" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import _config  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _git_init(path: Path) -> None:
    """Initialise a minimal git repo so resolve_git_root would accept it."""
    subprocess.run(
        ["git", "init", str(path)],
        check=True,
        capture_output=True,
    )


def _write_yaml(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------


def test_load_config_shared_present() -> None:
    """load_config returns the shared config when wiki/config.yaml exists."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        wiki = tmp_path / "wiki"
        hub = tmp_path / "hub"
        _git_init(hub)
        _write_yaml(wiki / "config.yaml", "spawn:\n  branch_prefix: feat\n")

        cfg = _config.load_config(wiki, hub)

        assert cfg == {"spawn": {"branch_prefix": "feat"}}, f"Unexpected cfg: {cfg!r}"
    print("PASS load_config — shared config present")


def test_load_config_local_override_wins() -> None:
    """load_config deep-merges local override; local values win on conflict."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        wiki = tmp_path / "wiki"
        hub = tmp_path / "hub"
        _git_init(hub)
        _write_yaml(wiki / "config.yaml", "spawn:\n  branch_prefix: feat\n  workers: 2\n")
        _write_yaml(
            hub / ".millhouse" / "config.local.yaml",
            "spawn:\n  branch_prefix: local\n",
        )

        cfg = _config.load_config(wiki, hub)

        assert cfg["spawn"]["branch_prefix"] == "local", (
            f"Local override should win; got {cfg['spawn']['branch_prefix']!r}"
        )
        assert cfg["spawn"]["workers"] == 2, (
            f"Shared key not in local should be preserved; got {cfg['spawn'].get('workers')!r}"
        )
    print("PASS load_config — local override wins; shared-only keys preserved")


def test_load_config_wiki_config_absent() -> None:
    """load_config returns an empty dict when wiki/config.yaml does not exist."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        wiki = tmp_path / "wiki"
        wiki.mkdir()  # dir exists but no config.yaml inside
        hub = tmp_path / "hub"
        _git_init(hub)

        cfg = _config.load_config(wiki, hub)

        assert cfg == {}, f"Expected empty dict for missing config, got {cfg!r}"
    print("PASS load_config — wiki config absent → empty dict")


# ---------------------------------------------------------------------------
# deep_merge
# ---------------------------------------------------------------------------


def test_deep_merge_scalar_wins() -> None:
    """Scalar overlay value wins over scalar base value."""
    result = _config.deep_merge({"a": 1, "b": 2}, {"b": 99})
    assert result == {"a": 1, "b": 99}, f"Unexpected: {result!r}"
    print("PASS deep_merge — scalar overlay wins")


def test_deep_merge_nested_merge() -> None:
    """Nested dicts are merged recursively; disjoint keys from both sides survive."""
    base = {"x": {"p": 1, "q": 2}}
    overlay = {"x": {"q": 99, "r": 3}}
    result = _config.deep_merge(base, overlay)
    assert result == {"x": {"p": 1, "q": 99, "r": 3}}, f"Unexpected: {result!r}"
    print("PASS deep_merge — nested merge, overlay wins on conflict, disjoint keys kept")


def test_deep_merge_empty_overlay() -> None:
    """An empty overlay leaves the base dict unchanged."""
    base = {"a": 1, "b": {"c": 2}}
    result = _config.deep_merge(base, {})
    assert result == base, f"Unexpected: {result!r}"
    # Must be a copy, not the same object.
    assert result is not base, "deep_merge must return a new dict, not the base"
    print("PASS deep_merge — empty overlay returns copy of base")


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------


def main() -> int:
    tests = [
        test_load_config_shared_present,
        test_load_config_local_override_wins,
        test_load_config_wiki_config_absent,
        test_deep_merge_scalar_wins,
        test_deep_merge_nested_merge,
        test_deep_merge_empty_overlay,
    ]
    failures: list[str] = []
    for fn in tests:
        try:
            fn()
        except AssertionError as exc:
            print(f"FAIL [{fn.__name__}]: {exc}", file=sys.stderr)
            failures.append(fn.__name__)
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR [{fn.__name__}]: {exc}", file=sys.stderr)
            failures.append(fn.__name__)
    if failures:
        print(f"\n{len(failures)} test(s) failed: {failures}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
