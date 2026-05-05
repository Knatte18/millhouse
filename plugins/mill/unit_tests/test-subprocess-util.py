"""Unit test for plugins/mill/scripts/_subprocess_util.py.

Covers: happy-path, timeout-kill path, breadcrumb format, check= behaviour.
Deeper kill verification (parent + children both gone) lives in integration_tests/.
"""
from __future__ import annotations

import contextlib
import io
import subprocess
import sys
import time
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _subprocess_util import _GRACE_SECONDS, run  # noqa: E402

# Tests (d) and (e) use a small_delta for timeout wall-time budget
_SMALL_DELTA = 5


def main() -> int:
    failures: list[str] = []

    # (c) normal-completion regression
    try:
        result = run(["git", "--version"])
        assert result.returncode == 0, f"git --version exit {result.returncode}"
        assert "git version" in result.stdout, f"unexpected stdout: {result.stdout!r}"
        assert isinstance(result.stdout, str), "stdout must be str"
        print(f"PASS (c): _subprocess_util.run('git --version') -> {result.stdout.strip()}")
    except AssertionError as exc:
        failures.append(f"FAIL (c) normal-completion: {exc}")

    # (a) timeout fires + (b) breadcrumb format
    # Deep tree-kill verification is deferred to integration_tests/
    try:
        buf = io.StringIO()
        deadline = time.monotonic() + 2.0 + _GRACE_SECONDS + _SMALL_DELTA
        with contextlib.redirect_stderr(buf):
            try:
                run(
                    [sys.executable, "-c", "import time; time.sleep(60)"],
                    timeout=2.0,
                )
                failures.append("FAIL (a) timeout-fires: expected TimeoutExpired, got nothing")
            except subprocess.TimeoutExpired:
                pass
        assert time.monotonic() < deadline, (
            f"timeout + kill exceeded wall-time budget of {2.0 + _GRACE_SECONDS + _SMALL_DELTA}s"
        )
        print("PASS (a): TimeoutExpired raised within wall-time budget")

        # (b) breadcrumb format check using the stderr captured above
        stderr_out = buf.getvalue()
        assert "[subprocess] spawn argv=" in stderr_out, (
            f"spawn breadcrumb missing from stderr:\n{stderr_out!r}"
        )
        assert "[subprocess] exit code=timeout duration=" in stderr_out, (
            f"timeout exit breadcrumb missing from stderr:\n{stderr_out!r}"
        )
        print("PASS (b): breadcrumb format correct")
    except AssertionError as exc:
        failures.append(f"FAIL (a)/(b) timeout/breadcrumb: {exc}")

    # (d) check=True raises CalledProcessError
    try:
        run(
            [sys.executable, "-c", "import sys; sys.exit(7)"],
            check=True,
        )
        failures.append("FAIL (d) check=True: expected CalledProcessError, got nothing")
    except subprocess.CalledProcessError as exc:
        assert exc.returncode == 7, f"expected returncode 7, got {exc.returncode}"
        print("PASS (d): check=True raises CalledProcessError with returncode=7")
    except AssertionError as exc:
        failures.append(f"FAIL (d) check=True: {exc}")

    # (e) check=False returns CompletedProcess with non-zero returncode
    try:
        result = run(
            [sys.executable, "-c", "import sys; sys.exit(7)"],
            check=False,
        )
        assert result.returncode == 7, f"expected returncode 7, got {result.returncode}"
        print("PASS (e): check=False returns CompletedProcess with returncode=7")
    except AssertionError as exc:
        failures.append(f"FAIL (e) check=False: {exc}")

    if failures:
        for msg in failures:
            print(msg, file=sys.stderr)
        return 1

    print("All _subprocess_util unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
