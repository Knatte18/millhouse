"""Unit tests for plugins/mill/scripts/_machine.py.

Covers:
  - machine_config_path: uses home_dir arg and Path.home() fallback
  - load_layer: returns {} when file is absent
  - load_layer: returns parsed dict when file is present
  - probe: returns correct (status, detail) for all three states
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS_DIR = HUB / "plugins" / "mill" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import _machine  # noqa: E402


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_machine_config_path_uses_home_arg() -> None:
    """machine_config_path uses the home_dir arg and falls back to Path.home()."""
    result = _machine.machine_config_path(home_dir=Path("/fake"))
    assert result == Path("/fake") / ".millhouse" / "config.machine.yaml", (
        f"Unexpected path with home_dir arg: {result!r}"
    )

    result_default = _machine.machine_config_path()
    assert result_default == Path.home() / ".millhouse" / "config.machine.yaml", (
        f"Unexpected path with no arg: {result_default!r}"
    )
    print("PASS test_machine_config_path_uses_home_arg")


def test_load_layer_missing_returns_empty() -> None:
    """load_layer returns {} when the config file does not exist."""
    with tempfile.TemporaryDirectory() as tmp:
        result = _machine.load_layer(home_dir=Path(tmp))
        assert result == {}, f"Expected {{}}, got {result!r}"
    print("PASS test_load_layer_missing_returns_empty")


def test_load_layer_present_returns_dict() -> None:
    """load_layer returns the parsed dict when the config file is present."""
    with tempfile.TemporaryDirectory() as tmp:
        config_path = Path(tmp) / ".millhouse" / "config.machine.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            "roles:\n  discussion-review:\n    holistic:\n      reviewer: g25flash\n",
            encoding="utf-8",
        )
        result = _machine.load_layer(home_dir=Path(tmp))
        assert result["roles"]["discussion-review"]["holistic"]["reviewer"] == "g25flash", (
            f"Unexpected result: {result!r}"
        )
    print("PASS test_load_layer_present_returns_dict")


def test_probe_three_states() -> None:
    """probe returns (MISSING, None), (PRESENT, dict), (MALFORMED, str) correctly."""
    # Sub-case: missing
    with tempfile.TemporaryDirectory() as tmp:
        status, detail = _machine.probe(home_dir=Path(tmp))
        assert status == _machine.MISSING, f"Expected MISSING, got {status!r}"
        assert detail is None, f"Expected None, got {detail!r}"

    # Sub-case: present
    with tempfile.TemporaryDirectory() as tmp:
        config_path = Path(tmp) / ".millhouse" / "config.machine.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            "roles:\n  discussion-review:\n    holistic:\n      reviewer: sonnet\n",
            encoding="utf-8",
        )
        status, detail = _machine.probe(home_dir=Path(tmp))
        assert status == _machine.PRESENT, f"Expected PRESENT, got {status!r}"
        assert isinstance(detail, dict), f"Expected dict, got {type(detail)!r}"
        assert detail["roles"]["discussion-review"]["holistic"]["reviewer"] == "sonnet", (
            f"Unexpected detail: {detail!r}"
        )

    # Sub-case: malformed
    with tempfile.TemporaryDirectory() as tmp:
        config_path = Path(tmp) / ".millhouse" / "config.machine.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(": : :\n", encoding="utf-8")
        status, detail = _machine.probe(home_dir=Path(tmp))
        assert status == _machine.MALFORMED, f"Expected MALFORMED, got {status!r}"
        assert isinstance(detail, str) and detail, (
            f"Expected non-empty str, got {detail!r}"
        )

    print("PASS test_probe_three_states")


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------


def main() -> int:
    tests = [
        test_machine_config_path_uses_home_arg,
        test_load_layer_missing_returns_empty,
        test_load_layer_present_returns_dict,
        test_probe_three_states,
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
