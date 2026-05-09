"""Discover and run every ``test-*.py`` in plugins/codeguide/unit_tests/.

Exits 0 when all tests pass, 1 when any fails. Each test is invoked as
a subprocess so a crash in one does not prevent the others from
running; stdout/stderr of each is surfaced inline so failures are easy
to spot in CI output.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> int:
    tests = sorted(HERE.glob("test-*.py"))
    if not tests:
        print("No test-*.py files found.", file=sys.stderr)
        return 1

    # Force UTF-8 I/O so test output containing non-ASCII characters (e.g.
    # the → arrow in pick_task_single_or_multi output) doesn't crash on
    # Windows consoles that default to cp1252.
    child_env = os.environ.copy()
    child_env["PYTHONIOENCODING"] = "utf-8"

    failures: list[str] = []
    for test in tests:
        print(f"--- {test.name} ---", file=sys.stderr)
        result = subprocess.run(
            [sys.executable, str(test)],
            capture_output=False,
            text=True,
            env=child_env,
        )
        if result.returncode != 0:
            failures.append(test.name)

    print("", file=sys.stderr)
    if failures:
        print(f"FAIL -- {len(failures)} of {len(tests)}: {failures}", file=sys.stderr)
        return 1
    print(f"PASS -- all {len(tests)} unit tests", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
