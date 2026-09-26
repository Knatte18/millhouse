"""Unit tests for plugins/mill/scripts/millpy-merge.py (thin CLI over _merge.run_merge)."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS = HUB / "plugins" / "mill" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _merge

_spec = importlib.util.spec_from_file_location("millpy_merge", SCRIPTS / "millpy-merge.py")
millpy_merge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(millpy_merge)

HALT_RESULT = {"status": "halt", "reason": "parent is not merged in", "action": "merge-in"}


def run_main_capturing_stdout(argv: list[str], fake_run_merge) -> tuple[int, str]:
    buffer = io.StringIO()
    with patch.object(_merge, "run_merge", fake_run_merge), contextlib.redirect_stdout(buffer):
        code = millpy_merge.main(argv)
    return code, buffer.getvalue()


def test_import_smoke():
    assert callable(millpy_merge.main)


def test_flags_map_onto_merge_options():
    captured = []

    def fake_run_merge(opts, ops=None):
        captured.append(opts)
        return HALT_RESULT

    run_main_capturing_stdout(
        ["--merged-in", "--confirm-parent", "X", "--parent", "Y"], fake_run_merge
    )
    assert captured == [_merge.MergeOptions(merged_in=True, confirm_parent="X", parent="Y")]


def test_no_flags_yield_default_options():
    captured = []

    def fake_run_merge(opts, ops=None):
        captured.append(opts)
        return HALT_RESULT

    run_main_capturing_stdout([], fake_run_merge)
    assert captured == [_merge.MergeOptions()]


def test_stdout_is_one_json_line_and_exit_zero_for_halt():
    code, stdout = run_main_capturing_stdout([], lambda opts, ops=None: HALT_RESULT)
    assert code == 0
    assert stdout.count("\n") == 1
    assert json.loads(stdout) == HALT_RESULT


def test_crash_propagates_without_stdout():
    def crashing_run_merge(opts, ops=None):
        raise RuntimeError("boom")

    buffer = io.StringIO()
    raised = False
    with patch.object(_merge, "run_merge", crashing_run_merge), contextlib.redirect_stdout(buffer):
        try:
            millpy_merge.main([])
        except RuntimeError:
            raised = True
    assert raised
    assert buffer.getvalue() == ""


def main() -> int:
    tests = [(name, fn) for name, fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    failures = []
    for name, fn in tests:
        try:
            fn()
            print(f"PASS {name}")
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL {name}: {exc!r}", file=sys.stderr)
            failures.append(name)
    print()
    if failures:
        print(f"FAIL -- {len(failures)} of {len(tests)} tests: {failures}", file=sys.stderr)
        return 1
    print(f"All {len(tests)} millpy-merge unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
