"""Unit test for plugins/mill/scripts/_subprocess_util.py.

Runs ``git --version`` through the wrapper as the minimal live-invocation
check — git has to be available (it is: the whole repo depends on it).
"""
from __future__ import annotations

import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _subprocess_util import run  # noqa: E402


def main() -> int:
    try:
        result = run(["git", "--version"])
        assert result.returncode == 0, f"git --version exit {result.returncode}"
        assert "git version" in result.stdout, f"unexpected stdout: {result.stdout!r}"
        print(f"PASS: _subprocess_util.run('git --version') -> {result.stdout.strip()}")

        print("All _subprocess_util unit tests passed.")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
