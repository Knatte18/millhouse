"""Unit tests for plugins/mill/scripts/_autonomous.py."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS_DIR = HUB / "plugins" / "mill" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import _autonomous  # noqa: E402


def main() -> int:
    try:
        # test_is_autonomous_false_when_flag_absent
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            got = _autonomous.is_autonomous(tmp_path)
            assert got is False, f"expected False, got {got}"
        print("PASS: test_is_autonomous_false_when_flag_absent")

        # test_set_autonomous_creates_zero_byte_flag
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _autonomous.set_autonomous(tmp_path)
            flag_path = tmp_path / ".millhouse" / "autonomous.flag"
            assert flag_path.exists(), f"flag not created at {flag_path}"
            assert flag_path.stat().st_size == 0, f"flag size is {flag_path.stat().st_size}, expected 0"
        print("PASS: test_set_autonomous_creates_zero_byte_flag")

        # test_is_autonomous_true_after_set
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _autonomous.set_autonomous(tmp_path)
            got = _autonomous.is_autonomous(tmp_path)
            assert got is True, f"expected True after set, got {got}"
        print("PASS: test_is_autonomous_true_after_set")

        # test_clear_autonomous_deletes_flag
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _autonomous.set_autonomous(tmp_path)
            flag_path = tmp_path / ".millhouse" / "autonomous.flag"
            assert flag_path.exists(), f"flag missing after set"
            _autonomous.clear_autonomous(tmp_path)
            assert not flag_path.exists(), f"flag still exists after clear"
            got = _autonomous.is_autonomous(tmp_path)
            assert got is False, f"is_autonomous should return False after clear, got {got}"
        print("PASS: test_clear_autonomous_deletes_flag")

        # test_clear_autonomous_idempotent_when_absent
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            try:
                _autonomous.clear_autonomous(tmp_path)
            except Exception as exc:
                raise AssertionError(f"clear_autonomous raised on absent flag: {exc}")
        print("PASS: test_clear_autonomous_idempotent_when_absent")

        # test_set_autonomous_idempotent_when_present
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _autonomous.set_autonomous(tmp_path)
            flag_path = tmp_path / ".millhouse" / "autonomous.flag"
            try:
                _autonomous.set_autonomous(tmp_path)
            except Exception as exc:
                raise AssertionError(f"set_autonomous raised on second call: {exc}")
            assert flag_path.exists(), f"flag missing after second set"
        print("PASS: test_set_autonomous_idempotent_when_present")

        print("All _autonomous unit tests passed.")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
