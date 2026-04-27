"""Unit tests for plugins/mill/scripts/_paths.py.

# resolve_git_root is exercised end-to-end by test-spawn.py and test-merge.py.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS_DIR = HUB / "plugins" / "mill" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import _paths  # noqa: E402
import _sibling  # noqa: E402


def _write_config(repo_root: Path, yaml_text: str) -> None:
    (repo_root / ".millhouse").mkdir(parents=True, exist_ok=True)
    (repo_root / ".millhouse" / "config.local.yaml").write_text(yaml_text, encoding="utf-8")


def main() -> int:
    try:
        assert _paths.resolve_path is _sibling.resolve_path, \
            "resolve_path must be re-exported identity from _sibling, not duplicated"
        print("PASS: _paths.resolve_path is _sibling.resolve_path (no duplication)")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            hub = tmp_path / "hub"
            hub.mkdir()
            got = _paths.resolve_wiki_path(hub)
            assert got == tmp_path / "wiki", f"hub-form default: got {got}"
        print("PASS: resolve_wiki_path hub-form default -> <parent>/wiki")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            foo = tmp_path / "foo"
            foo.mkdir()
            got = _paths.resolve_wiki_path(foo)
            assert got == tmp_path / "foo.wiki", f"prefix-form default: got {got}"
        print("PASS: resolve_wiki_path prefix-form default -> <parent>/<name>.wiki")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            hub = tmp_path / "hub"
            hub.mkdir()
            abs_override = tmp_path / "elsewhere" / "wiki"
            _write_config(hub, f"paths:\n  wiki: {abs_override}\n")
            got = _paths.resolve_wiki_path(hub)
            assert got == abs_override, f"absolute override: got {got}"
        print("PASS: resolve_wiki_path absolute paths.wiki override wins")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            hub = (tmp_path / "hub").resolve()
            hub.mkdir()
            _write_config(hub, "paths:\n  wiki: ../custom-wiki\n")
            got = _paths.resolve_wiki_path(hub)
            assert got == (tmp_path / "custom-wiki").resolve(), \
                f"relative override: got {got}"
        print("PASS: resolve_wiki_path relative paths.wiki override resolves against git-toplevel")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            hub = tmp_path / "hub"
            hub.mkdir()
            _write_config(hub, "paths: {}\n")
            got = _paths.resolve_wiki_path(hub)
            assert got == tmp_path / "wiki", f"empty paths block: got {got}"
        print("PASS: resolve_wiki_path with empty paths: block falls through to sibling default")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            hub = tmp_path / "hub"
            hub.mkdir()
            _write_config(hub, "other_key: value\n")
            got = _paths.resolve_wiki_path(hub)
            assert got == tmp_path / "wiki", f"no paths key: got {got}"
        print("PASS: resolve_wiki_path with no paths: key falls through to sibling default")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            hub = tmp_path / "hub"
            hub.mkdir()
            _write_config(hub, "paths:\n  wiki: [this is not a string\n")
            try:
                _paths.resolve_wiki_path(hub)
                raise AssertionError("malformed YAML should have raised")
            except Exception as exc:
                import yaml
                assert isinstance(exc, yaml.YAMLError), \
                    f"expected yaml.YAMLError, got {type(exc).__name__}: {exc}"
        print("PASS: resolve_wiki_path propagates yaml.YAMLError on malformed config")

        # resolve_short_name
        got = _paths.resolve_short_name({"repo": {"short_name": "MH"}}, "millhouse")
        assert got == "MH", f"configured short_name: got {got!r}"
        print("PASS: resolve_short_name configured value 'MH' returned as-is")

        got = _paths.resolve_short_name({"repo": {"short_name": ""}}, "millhouse")
        assert got == "MI", f"empty short_name fallback: got {got!r}"
        print("PASS: resolve_short_name empty string falls back to repo_name[:2].upper()")

        got = _paths.resolve_short_name({}, "millhouse")
        assert got == "MI", f"missing repo block fallback: got {got!r}"
        print("PASS: resolve_short_name missing repo: block falls back to repo_name[:2].upper()")

        got = _paths.resolve_short_name({"repo": {}}, "millhouse")
        assert got == "MI", f"missing short_name key fallback: got {got!r}"
        print("PASS: resolve_short_name missing short_name key falls back to repo_name[:2].upper()")

        got = _paths.resolve_short_name({}, "foobar")
        assert got == "FO", f"repo_name=foobar fallback: got {got!r}"
        print("PASS: resolve_short_name repo_name='foobar' -> 'FO'")

        got = _paths.resolve_short_name({}, "x")
        assert got == "X", f"repo_name=x fallback: got {got!r}"
        print("PASS: resolve_short_name repo_name='x' -> 'X'")

        print("All _paths unit tests passed.")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
