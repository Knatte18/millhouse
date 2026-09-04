"""
Unit test for `plugins/mill/scripts/_done_gate.py`.

Regresses #650: `pipeline.done_gate` had no pre-implementation baseline pre-flight, so a
self-capturing regression/snapshot test suite used as the done_gate silently captured its "baseline"
from the task's own just-finished implementation at Handoff.
This test covers `_done_gate.run_preflight`'s result shapes directly and confirms its never-raise
contract, mocking `subprocess.run` throughout -- no real shell command is ever executed.
It also covers `_done_gate.run_gate` -- the Handoff-time gate call --
including its success, Windows-only dotnet-build-server-shutdown cleanup, and failure paths,
mocking `subprocess.run` and `platform.system` throughout.

Follows `test-verify-baseline.py`'s style: a single `main() -> int` function with inline numbered
cases, `PASS`/`FAIL` prints, an accumulated error count, and `sys.exit(main())` at the bottom.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _done_gate import run_gate, run_preflight  # noqa: E402


def main() -> int:
    errors = 0
    git_root = Path("/fake/git-root")

    # Case 1: gate_cmd is None -- nothing configured, run_preflight never touches subprocess at all.
    try:
        with patch("_done_gate.subprocess.run") as mock_run:
            result = run_preflight(None, git_root)
        assert result == {"result": "skipped", "reason": "no done_gate configured"}, (
            f"expected skipped/no done_gate configured, got {result!r}"
        )
        mock_run.assert_not_called()
        print("PASS: gate_cmd=None -> skipped, subprocess never invoked")
    except AssertionError as exc:
        print(f"FAIL: case 1 ({exc})", file=sys.stderr)
        errors += 1

    # Case 2: mocked exit 0 -- gate command passes.
    try:
        with patch(
            "_done_gate.subprocess.run",
            return_value=MagicMock(returncode=0, stdout="ok\n", stderr=""),
        ):
            result = run_preflight("echo ok", git_root)
        assert result == {"result": "ok"}, f"expected result=ok, got {result!r}"
        print("PASS: mocked exit 0 -> ok")
    except AssertionError as exc:
        print(f"FAIL: case 2 ({exc})", file=sys.stderr)
        errors += 1

    # Case 3: mocked exit 1 with captured stdout/stderr -- gate command fails, reason must match the concatenated captured output.
    try:
        with patch(
            "_done_gate.subprocess.run",
            return_value=MagicMock(
                returncode=1, stdout="some stdout\n", stderr="some stderr\n"
            ),
        ):
            result = run_preflight("false", git_root)
        assert result["result"] == "blocked", f"expected result=blocked, got {result!r}"
        assert result["reason"] == "some stdout\nsome stderr", (
            f"expected reason to match concatenated captured output, got {result['reason']!r}"
        )
        print("PASS: mocked exit 1 -> blocked, reason matches captured output")
    except AssertionError as exc:
        print(f"FAIL: case 3 ({exc})", file=sys.stderr)
        errors += 1

    # Case 4: mocked exit 1 with output longer than 2000 chars -- reason is tail-truncated to exactly 2000 chars, same truncation shape as the existing Handoff-time "0.
    # Pre-done gate" block.
    try:
        long_output = "x" * 3000
        with patch(
            "_done_gate.subprocess.run",
            return_value=MagicMock(returncode=1, stdout=long_output, stderr=""),
        ):
            result = run_preflight("false", git_root)
        assert result["result"] == "blocked", f"expected result=blocked, got {result!r}"
        assert len(result["reason"]) == 2000, (
            f"expected reason truncated to 2000 chars, got {len(result['reason'])}"
        )
        assert result["reason"] == long_output[-2000:], (
            "expected reason to be the tail (last 2000 chars) of the captured output"
        )
        print(
            "PASS: mocked exit 1 with long output -> reason tail-truncated to 2000 chars"
        )
    except AssertionError as exc:
        print(f"FAIL: case 4 ({exc})", file=sys.stderr)
        errors += 1

    # Case 5: subprocess.run itself raises (e.g.
    # missing binary) -- confirms the never-raise contract: run_preflight still returns a result dict instead of propagating the exception.
    try:
        with patch(
            "_done_gate.subprocess.run",
            side_effect=OSError(
                "[Errno 2] No such file or directory: 'nonexistent-binary'"
            ),
        ):
            result = run_preflight("nonexistent-binary", git_root)
        assert result["result"] == "blocked", (
            f"expected a blocked result dict rather than a raised exception, got {result!r}"
        )
        assert "reason" in result, (
            f"expected a reason in the degraded result, got {result!r}"
        )
        print(
            "PASS: subprocess.run raises -> run_preflight still returns a dict, never raises"
        )
    except AssertionError as exc:
        print(f"FAIL: case 5 ({exc})", file=sys.stderr)
        errors += 1

    # Case 6: run_gate success, gate_cmd has no 'dotnet' in it -- the dotnet-shutdown branch must
    # not fire regardless of platform, and subprocess.run must be called exactly once.
    try:
        with patch(
            "_done_gate.subprocess.run",
            return_value=MagicMock(returncode=0, stdout="ok\n", stderr=""),
        ) as mock_run:
            result = run_gate("pytest", git_root)
        assert result == {"result": "ok"}, f"expected result=ok, got {result!r}"
        assert mock_run.call_count == 1, (
            f"expected subprocess.run called exactly once (no dotnet-shutdown branch), got {mock_run.call_count}"
        )
        print(
            "PASS: run_gate exit 0, no dotnet in gate_cmd -> ok, subprocess.run called once"
        )
    except AssertionError as exc:
        print(f"FAIL: case 6 ({exc})", file=sys.stderr)
        errors += 1

    # Case 7: run_gate success, gate_cmd contains 'dotnet', platform is Windows -- the
    # dotnet-shutdown branch must fire as a second subprocess.run call with the expected args.
    try:
        with (
            patch(
                "_done_gate.subprocess.run",
                return_value=MagicMock(returncode=0, stdout="ok\n", stderr=""),
            ) as mock_run,
            patch("_done_gate.platform.system", return_value="Windows"),
        ):
            result = run_gate("dotnet test foo.csproj", git_root)
        assert result == {"result": "ok"}, f"expected result=ok, got {result!r}"
        assert mock_run.call_count == 2, (
            f"expected subprocess.run called twice (gate + dotnet-shutdown), got {mock_run.call_count}"
        )
        second_call = mock_run.call_args_list[1]
        assert second_call.args == (["dotnet", "build-server", "shutdown"],), (
            f"expected dotnet-shutdown args, got {second_call.args!r}"
        )
        assert second_call.kwargs == {"capture_output": True, "timeout": 30}, (
            f"expected dotnet-shutdown kwargs, got {second_call.kwargs!r}"
        )
        print(
            "PASS: run_gate exit 0, dotnet in gate_cmd, Windows -> ok, dotnet-shutdown called"
        )
    except AssertionError as exc:
        print(f"FAIL: case 7 ({exc})", file=sys.stderr)
        errors += 1

    # Case 8: identical setup to Case 7 except platform is Linux -- the dotnet-shutdown branch
    # must not fire on a non-Windows platform even when 'dotnet' is present in gate_cmd.
    try:
        with (
            patch(
                "_done_gate.subprocess.run",
                return_value=MagicMock(returncode=0, stdout="ok\n", stderr=""),
            ) as mock_run,
            patch("_done_gate.platform.system", return_value="Linux"),
        ):
            result = run_gate("dotnet test foo.csproj", git_root)
        assert result == {"result": "ok"}, f"expected result=ok, got {result!r}"
        assert mock_run.call_count == 1, (
            f"expected subprocess.run called exactly once (no dotnet-shutdown branch on non-Windows), got {mock_run.call_count}"
        )
        print(
            "PASS: run_gate exit 0, dotnet in gate_cmd, Linux -> ok, subprocess.run called once"
        )
    except AssertionError as exc:
        print(f"FAIL: case 8 ({exc})", file=sys.stderr)
        errors += 1

    # Case 9: run_gate failure with output longer than 2000 chars -- reason is tail-truncated to
    # exactly 2000 chars, the same truncation shape as run_preflight's own Case 4.
    try:
        long_output = "x" * 3000
        with patch(
            "_done_gate.subprocess.run",
            return_value=MagicMock(returncode=1, stdout=long_output, stderr=""),
        ):
            result = run_gate("false", git_root)
        assert result["result"] == "blocked", f"expected result=blocked, got {result!r}"
        assert len(result["reason"]) == 2000, (
            f"expected reason truncated to 2000 chars, got {len(result['reason'])}"
        )
        assert result["reason"] == long_output[-2000:], (
            "expected reason to be the tail (last 2000 chars) of the captured output"
        )
        print(
            "PASS: run_gate exit 1 with long output -> reason tail-truncated to 2000 chars"
        )
    except AssertionError as exc:
        print(f"FAIL: case 9 ({exc})", file=sys.stderr)
        errors += 1

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All _done_gate unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
