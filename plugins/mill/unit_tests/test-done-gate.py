"""
Unit test for `plugins/mill/scripts/_done_gate.py`.

Regresses #650: `pipeline.done_gate` had no pre-implementation baseline pre-flight, so a
self-capturing regression/snapshot test suite used as the done_gate silently captured its "baseline"
from the task's own just-finished implementation at Handoff.
This test covers `_done_gate.run_preflight`'s result shapes directly and confirms its never-raise
contract.
It also covers `_done_gate.run_gate` -- the Handoff-time gate call --
including its success, Windows-only dotnet-build-server-shutdown cleanup, and failure paths.
The gate command runs through `_verify_run.run_verify`, patched to return canned `VerifyRun`
records, and config loads are patched too -- no real shell command is ever executed.
`_done_gate.subprocess.run` is patched only to observe the dotnet shutdown call.

Uses the inline-case style: a single `main() -> int` function with inline numbered
cases, `PASS`/`FAIL` prints, an accumulated error count, and `sys.exit(main())` at the bottom.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _verify_run  # noqa: E402
from _done_gate import run_gate, run_preflight  # noqa: E402


def _canned_run(
    output: str = "",
    exit_code: int | None = 0,
    timed_out: bool = False,
    label: str = "done-gate",
    output_path: Path | None = Path("/fake/out.txt"),
) -> _verify_run.VerifyRun:
    """Build a VerifyRun record as the runner would return it."""
    return _verify_run.VerifyRun(
        label=label,
        cmd="gate",
        cwd=Path("/fake/git-root"),
        exit_code=exit_code,
        wall_s=1.5,
        first_run=False,
        timed_out=timed_out,
        output=output,
        output_path=output_path,
        timeout_s=1200.0,
    )


def _suffix(run: _verify_run.VerifyRun) -> str:
    return f"\n[verify output: {run.output_path}]"


def main() -> int:
    errors = 0
    git_root = Path("/fake/git-root")
    hub_root = Path("/fake/hub")
    default_cfg: dict = {}

    def runner(run: _verify_run.VerifyRun):
        """Patch the runner seam and config load; yields nothing, enters both patches."""
        return (
            patch("_verify_run.run_verify", return_value=run),
            patch("_config.load_config", return_value=default_cfg),
        )

    # Case 1: gate_cmd is None -- nothing configured, run_preflight never touches the runner at all.
    try:
        with (
            patch("_verify_run.run_verify") as mock_verify,
            patch("_config.load_config") as mock_load,
            patch("_done_gate.subprocess.run") as mock_run,
        ):
            result = run_preflight(None, git_root)
        assert result == {"result": "skipped", "reason": "no done_gate configured"}, (
            f"expected skipped/no done_gate configured, got {result!r}"
        )
        mock_verify.assert_not_called()
        mock_load.assert_not_called()
        mock_run.assert_not_called()
        print("PASS: gate_cmd=None -> skipped, runner never invoked")
    except AssertionError as exc:
        print(f"FAIL: case 1 ({exc})", file=sys.stderr)
        errors += 1

    # Case 2: exit 0 -- gate command passes, result carries the run summary.
    try:
        run = _canned_run(output="ok\n", label="done-gate-preflight")
        verify_patch, load_patch = runner(run)
        with verify_patch, load_patch:
            result = run_preflight("echo ok", git_root, hub_root=hub_root)
        assert result == {"result": "ok", "verify_runs": [run.summary()]}, (
            f"expected result=ok with verify_runs, got {result!r}"
        )
        print("PASS: exit 0 -> ok with verify_runs")
    except AssertionError as exc:
        print(f"FAIL: case 2 ({exc})", file=sys.stderr)
        errors += 1

    # Case 3: exit 1 with captured output -- reason is the output plus the saved-output suffix.
    try:
        run = _canned_run(output="some stdout\nsome stderr\n", exit_code=1)
        verify_patch, load_patch = runner(run)
        with verify_patch, load_patch:
            result = run_preflight("false", git_root, hub_root=hub_root)
        assert result["result"] == "blocked", f"expected result=blocked, got {result!r}"
        assert result["reason"] == "some stdout\nsome stderr" + _suffix(run), (
            f"expected reason to be the output plus suffix, got {result['reason']!r}"
        )
        assert result["verify_runs"] == [run.summary()], (
            f"expected verify_runs to carry the run summary, got {result['verify_runs']!r}"
        )
        print("PASS: exit 1 -> blocked, reason is output plus saved-output suffix, verify_runs set")
    except AssertionError as exc:
        print(f"FAIL: case 3 ({exc})", file=sys.stderr)
        errors += 1

    # Case 4: exit 1 with output longer than 2000 chars, no failure markers anywhere in it --
    # reason is an omitted-content marker (naming the omitted char count, no "earlier failures"
    # suffix since none exist) followed by the last 2000 chars and the saved-output suffix.
    try:
        long_output = "x" * 3000
        run = _canned_run(output=long_output, exit_code=1)
        verify_patch, load_patch = runner(run)
        with verify_patch, load_patch:
            result = run_preflight("false", git_root, hub_root=hub_root)
        assert result["result"] == "blocked", f"expected result=blocked, got {result!r}"
        assert result["reason"].startswith("[... 1000 earlier chars omitted"), (
            f"expected reason to start with an omitted-content marker, got {result['reason']!r}"
        )
        assert "; earlier failures:" not in result["reason"], (
            "expected no earlier-failures suffix since the omitted portion has no failure markers"
        )
        assert result["reason"].endswith(long_output[-2000:] + _suffix(run)), (
            "expected reason to end with the tail (last 2000 chars) of the output plus the suffix"
        )
        print(
            "PASS: exit 1 with long output, no failure markers -> "
            "reason is omitted-content marker plus tail plus suffix"
        )
    except AssertionError as exc:
        print(f"FAIL: case 4 ({exc})", file=sys.stderr)
        errors += 1

    # Case 5: the runner itself raises (e.g. missing binary) -- confirms the never-raise contract:
    # run_preflight still returns a blocked dict (without verify_runs) instead of propagating.
    try:
        with (
            patch(
                "_verify_run.run_verify",
                side_effect=OSError("[Errno 2] No such file or directory: 'nonexistent-binary'"),
            ),
            patch("_config.load_config", return_value=default_cfg),
        ):
            result = run_preflight("nonexistent-binary", git_root, hub_root=hub_root)
        assert result["result"] == "blocked", (
            f"expected a blocked result dict rather than a raised exception, got {result!r}"
        )
        assert "nonexistent-binary" in result["reason"], (
            f"expected the exception message in the degraded result, got {result!r}"
        )
        assert "verify_runs" not in result, f"expected no verify_runs on the exception path, got {result!r}"
        print("PASS: runner raises -> run_preflight still returns a dict, never raises")
    except AssertionError as exc:
        print(f"FAIL: case 5 ({exc})", file=sys.stderr)
        errors += 1

    # Case 6: run_gate success, gate_cmd has no 'dotnet' in it -- the dotnet-shutdown branch must
    # not fire regardless of platform.
    try:
        run = _canned_run(output="ok\n")
        verify_patch, load_patch = runner(run)
        with verify_patch, load_patch, patch("_done_gate.subprocess.run") as mock_run:
            result = run_gate("pytest", git_root, hub_root=hub_root)
        assert result == {"result": "ok", "verify_runs": [run.summary()]}, (
            f"expected result=ok with verify_runs, got {result!r}"
        )
        mock_run.assert_not_called()
        print("PASS: run_gate exit 0, no dotnet in gate_cmd -> ok, no shutdown call")
    except AssertionError as exc:
        print(f"FAIL: case 6 ({exc})", file=sys.stderr)
        errors += 1

    # Case 7: run_gate success, gate_cmd contains 'dotnet', platform is Windows -- the
    # dotnet-shutdown branch must fire as one plain subprocess.run call with the expected args.
    try:
        run = _canned_run(output="ok\n")
        verify_patch, load_patch = runner(run)
        with (
            verify_patch,
            load_patch,
            patch("_done_gate.subprocess.run") as mock_run,
            patch("_done_gate.platform.system", return_value="Windows"),
        ):
            result = run_gate("dotnet test foo.csproj", git_root, hub_root=hub_root)
        assert result == {"result": "ok", "verify_runs": [run.summary()]}, (
            f"expected result=ok with verify_runs, got {result!r}"
        )
        assert mock_run.call_count == 1, (
            f"expected subprocess.run called once (dotnet-shutdown only), got {mock_run.call_count}"
        )
        call = mock_run.call_args_list[0]
        assert call.args == (["dotnet", "build-server", "shutdown"],), (
            f"expected dotnet-shutdown args, got {call.args!r}"
        )
        assert call.kwargs == {"capture_output": True, "timeout": 30}, (
            f"expected dotnet-shutdown kwargs, got {call.kwargs!r}"
        )
        print("PASS: run_gate exit 0, dotnet in gate_cmd, Windows -> ok, dotnet-shutdown called")
    except AssertionError as exc:
        print(f"FAIL: case 7 ({exc})", file=sys.stderr)
        errors += 1

    # Case 8: identical setup to Case 7 except platform is Linux -- the dotnet-shutdown branch
    # must not fire on a non-Windows platform even when 'dotnet' is present in gate_cmd.
    try:
        run = _canned_run(output="ok\n")
        verify_patch, load_patch = runner(run)
        with (
            verify_patch,
            load_patch,
            patch("_done_gate.subprocess.run") as mock_run,
            patch("_done_gate.platform.system", return_value="Linux"),
        ):
            result = run_gate("dotnet test foo.csproj", git_root, hub_root=hub_root)
        assert result == {"result": "ok", "verify_runs": [run.summary()]}, (
            f"expected result=ok with verify_runs, got {result!r}"
        )
        mock_run.assert_not_called()
        print("PASS: run_gate exit 0, dotnet in gate_cmd, Linux -> ok, no shutdown call")
    except AssertionError as exc:
        print(f"FAIL: case 8 ({exc})", file=sys.stderr)
        errors += 1

    # Case 9: run_gate failure with output longer than 2000 chars, no failure markers anywhere in
    # it -- reason is an omitted-content marker followed by the tail and suffix, the same
    # enrichment shape as run_preflight's own Case 4.
    try:
        long_output = "x" * 3000
        run = _canned_run(output=long_output, exit_code=1)
        verify_patch, load_patch = runner(run)
        with verify_patch, load_patch:
            result = run_gate("false", git_root, hub_root=hub_root)
        assert result["result"] == "blocked", f"expected result=blocked, got {result!r}"
        assert result["reason"].startswith("[... 1000 earlier chars omitted"), (
            f"expected reason to start with an omitted-content marker, got {result['reason']!r}"
        )
        assert "; earlier failures:" not in result["reason"], (
            "expected no earlier-failures suffix since the omitted portion has no failure markers"
        )
        assert result["reason"].endswith(long_output[-2000:] + _suffix(run)), (
            "expected reason to end with the tail (last 2000 chars) of the output plus the suffix"
        )
        print(
            "PASS: run_gate exit 1 with long output, no failure markers -> "
            "reason is omitted-content marker plus tail plus suffix"
        )
    except AssertionError as exc:
        print(f"FAIL: case 9 ({exc})", file=sys.stderr)
        errors += 1

    # Case 10: run_preflight failure whose output puts a Go per-test failure-marker line in the
    # omitted (non-tail) portion -- direct regression case for #1020: a failure line pushed out of a
    # blind tail-truncation by later passing-noise must still surface in `reason`.
    try:
        long_output = "--- FAIL: TestEarly (0.01s)\n" + ("ok  \tpkg/passing\t0.01s\n" * 150)
        assert len(long_output) > 2000 + len("--- FAIL: TestEarly (0.01s)\n"), (
            "fixture too short to push the failure line out of the kept 2000-char tail"
        )
        run = _canned_run(output=long_output, exit_code=1)
        verify_patch, load_patch = runner(run)
        with verify_patch, load_patch:
            result = run_preflight("false", git_root, hub_root=hub_root)
        assert result["result"] == "blocked", f"expected result=blocked, got {result!r}"
        assert "--- FAIL: TestEarly (0.01s)" in result["reason"], (
            f"expected the earlier failure line to survive truncation, got {result['reason']!r}"
        )
        print(
            "PASS: run_preflight surfaces an earlier failure-marker line pushed out of the tail "
            "by later passing noise"
        )
    except AssertionError as exc:
        print(f"FAIL: case 10 ({exc})", file=sys.stderr)
        errors += 1

    # Case 11: identical scenario to Case 10 but via run_gate -- confirms both call sites share the
    # identical enriched-reason shape. gate_cmd has no 'dotnet' in it so the Windows
    # dotnet-build-server-shutdown branch does not interfere.
    try:
        long_output = "--- FAIL: TestEarly (0.01s)\n" + ("ok  \tpkg/passing\t0.01s\n" * 150)
        assert len(long_output) > 2000 + len("--- FAIL: TestEarly (0.01s)\n"), (
            "fixture too short to push the failure line out of the kept 2000-char tail"
        )
        run = _canned_run(output=long_output, exit_code=1)
        verify_patch, load_patch = runner(run)
        with verify_patch, load_patch:
            result = run_gate("false", git_root, hub_root=hub_root)
        assert result["result"] == "blocked", f"expected result=blocked, got {result!r}"
        assert "--- FAIL: TestEarly (0.01s)" in result["reason"], (
            f"expected the earlier failure line to survive truncation, got {result['reason']!r}"
        )
        print(
            "PASS: run_gate surfaces an earlier failure-marker line pushed out of the tail by "
            "later passing noise"
        )
    except AssertionError as exc:
        print(f"FAIL: case 11 ({exc})", file=sys.stderr)
        errors += 1

    # Case 12: timed-out run -- blocked, reason starts with the timeout prefix naming the label.
    try:
        run = _canned_run(output="partial\n", exit_code=None, timed_out=True)
        verify_patch, load_patch = runner(run)
        with verify_patch, load_patch:
            result = run_gate("slow", git_root, hub_root=hub_root)
        assert result["result"] == "blocked", f"expected result=blocked, got {result!r}"
        assert result["reason"] == (
            "[verify timed out after 1200s: done-gate] partial" + _suffix(run)
        ), f"unexpected timeout reason {result['reason']!r}"
        assert result["verify_runs"] == [run.summary()], (
            f"expected verify_runs to carry the run summary, got {result['verify_runs']!r}"
        )
        print("PASS: timed-out run -> blocked with timeout prefix and verify_runs")
    except AssertionError as exc:
        print(f"FAIL: case 12 ({exc})", file=sys.stderr)
        errors += 1

    # Case 13: launch failure (no exit code, not timed out) -- blocked with the bare run output.
    try:
        run = _canned_run(output="cannot launch: boom", exit_code=None)
        verify_patch, load_patch = runner(run)
        with verify_patch, load_patch:
            result = run_preflight("missing", git_root, hub_root=hub_root)
        assert result == {
            "result": "blocked",
            "reason": "cannot launch: boom",
            "verify_runs": [run.summary()],
        }, f"unexpected launch-failure result {result!r}"
        print("PASS: launch failure -> blocked with the run output as reason")
    except AssertionError as exc:
        print(f"FAIL: case 13 ({exc})", file=sys.stderr)
        errors += 1

    # Case 14: invalid pipeline.verify_timeout_minutes -- blocked naming the key, never an
    # exception, and the runner is never invoked.
    try:
        with (
            patch("_verify_run.run_verify") as mock_verify,
            patch("_config.load_config", return_value={"pipeline": {"verify_timeout_minutes": -5}}),
        ):
            gate_result = run_gate("pytest", git_root, hub_root=hub_root)
            preflight_result = run_preflight("pytest", git_root, hub_root=hub_root)
        for result in (gate_result, preflight_result):
            assert result["result"] == "blocked", f"expected result=blocked, got {result!r}"
            assert "pipeline.verify_timeout_minutes" in result["reason"], (
                f"expected the config key in the reason, got {result['reason']!r}"
            )
        mock_verify.assert_not_called()
        print("PASS: invalid verify_timeout_minutes -> blocked naming the key, runner never called")
    except AssertionError as exc:
        print(f"FAIL: case 14 ({exc})", file=sys.stderr)
        errors += 1

    # Case 15: the runner receives native shell mode, the per-function label, the config-derived
    # timeout, and the git root as cwd.
    try:
        with (
            patch("_verify_run.run_verify", return_value=_canned_run()) as mock_verify,
            patch("_config.load_config", return_value={"pipeline": {"verify_timeout_minutes": 2}}),
        ):
            run_preflight("pytest", git_root, hub_root=hub_root)
            run_gate("pytest", git_root, hub_root=hub_root)
        preflight_call, gate_call = mock_verify.call_args_list
        assert preflight_call.kwargs["label"] == "done-gate-preflight", (
            f"unexpected preflight label {preflight_call.kwargs['label']!r}"
        )
        assert gate_call.kwargs["label"] == "done-gate", (
            f"unexpected gate label {gate_call.kwargs['label']!r}"
        )
        for call in (preflight_call, gate_call):
            assert call.args == ("pytest",), f"unexpected positional args {call.args!r}"
            assert call.kwargs["shell_mode"] == "native", (
                f"expected native shell mode, got {call.kwargs['shell_mode']!r}"
            )
            assert call.kwargs["timeout_s"] == 120, (
                f"expected 120s timeout, got {call.kwargs['timeout_s']!r}"
            )
            assert call.kwargs["cwd"] == git_root, f"unexpected cwd {call.kwargs['cwd']!r}"
            assert call.kwargs["git_root"] == git_root, (
                f"unexpected git_root {call.kwargs['git_root']!r}"
            )
        print("PASS: runner gets native shell mode, both labels, config timeout and git root")
    except AssertionError as exc:
        print(f"FAIL: case 15 ({exc})", file=sys.stderr)
        errors += 1

    # Case 16: hub_root is forwarded to config loading when given; otherwise the hub is resolved
    # from git_root.
    try:
        with (
            patch("_verify_run.run_verify", return_value=_canned_run()),
            patch("_config.load_config", return_value=default_cfg) as mock_load,
            patch("_paths.resolve_hub_path", return_value=Path("/resolved/hub")) as mock_resolve,
        ):
            run_gate("pytest", git_root, hub_root=hub_root)
            mock_load.assert_called_once_with(hub_root, git_root)
            mock_resolve.assert_not_called()
            mock_load.reset_mock()
            run_gate("pytest", git_root)
            mock_resolve.assert_called_once_with(git_root)
            mock_load.assert_called_once_with(Path("/resolved/hub"), git_root)
        print("PASS: hub_root forwarded to load_config; resolved from git_root when omitted")
    except AssertionError as exc:
        print(f"FAIL: case 16 ({exc})", file=sys.stderr)
        errors += 1

    # Case 17: a failed run_gate never triggers the dotnet shutdown, even on Windows.
    try:
        run = _canned_run(output="boom", exit_code=1)
        verify_patch, load_patch = runner(run)
        with (
            verify_patch,
            load_patch,
            patch("_done_gate.subprocess.run") as mock_run,
            patch("_done_gate.platform.system", return_value="Windows"),
        ):
            result = run_gate("dotnet test", git_root, hub_root=hub_root)
        assert result["result"] == "blocked", f"expected result=blocked, got {result!r}"
        mock_run.assert_not_called()
        print("PASS: run_gate failure on Windows -> no dotnet-shutdown call")
    except AssertionError as exc:
        print(f"FAIL: case 17 ({exc})", file=sys.stderr)
        errors += 1

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All _done_gate unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
