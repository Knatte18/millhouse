"""
Integration test for _subprocess_util.run watchdog cross-process kill-tree.

Spawns a Python parent that itself spawns a long-sleeping grandchild, runs
both under _subprocess_util.run with a short timeout, then asserts that the
watchdog's taskkill /T /F killed the grandchild as well as the parent.

Windows-only. Run from hub root:
    python plugins/mill/integration_tests/test-subprocess-tree-kill.py

Exits 0 on PASS, 1 on any assertion failure.
"""
import os
import sys

if os.name != "nt":
    print("SKIP test-subprocess-tree-kill: Windows-only")
    sys.exit(0)

import subprocess
import time
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _subprocess_util  # noqa: E402


def main() -> int:
    grandchild_argv = [sys.executable, "-c", "import time; time.sleep(120)"]
    grandchild_argv_repr = repr(grandchild_argv)
    parent_script = (
        f"import subprocess, sys, time; "
        f"p = subprocess.Popen({grandchild_argv_repr}); "
        f"print(p.pid, flush=True); "
        f"time.sleep(120)"
    )
    argv = [sys.executable, "-c", parent_script]

    grandchild_pid = None
    try:
        _subprocess_util.run(argv, timeout=2.0)
        print("FAIL: expected TimeoutExpired, got normal return", file=sys.stderr)
        return 1
    except subprocess.TimeoutExpired as exc:
        if exc.stdout:
            for line in exc.stdout.splitlines():
                line = line.strip()
                if line.isdigit():
                    grandchild_pid = int(line)
                    break

    if grandchild_pid is None:
        print(
            "FAIL: could not parse grandchild PID from exc.stdout",
            file=sys.stderr,
        )
        return 1

    # Give Windows time to finish reaping killed processes.
    time.sleep(1)

    tasklist_result = subprocess.run(
        ["tasklist", "/FI", f"PID eq {grandchild_pid}"],
        capture_output=True,
        text=True,
    )
    if "No tasks are running which match the specified criteria." not in tasklist_result.stdout:
        print(
            f"FAIL: grandchild PID {grandchild_pid} still alive after watchdog kill:\n"
            f"{tasklist_result.stdout}",
            file=sys.stderr,
        )
        return 1

    print(f"PASS: grandchild PID {grandchild_pid} gone after watchdog kill")
    return 0


if __name__ == "__main__":
    sys.exit(main())
