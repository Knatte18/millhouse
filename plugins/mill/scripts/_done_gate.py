"""
Opt-in Prepare-phase baseline pre-flight for `pipeline.done_gate`.

Fixes #650: a self-capturing regression/snapshot test suite used as the `done_gate` command captures
its own "baseline" the first time it runs.
If that first run only ever happens at Handoff (the existing "0.
Pre-done gate" block in mill-go SKILL.md), the baseline gets captured from the task's own
just-finished implementation instead of from the pre-implementation parent-branch state -- so the
Handoff-time comparison always passes, providing zero actual regression protection.

`run_preflight` gives mill-go a way to run `done_gate` once, eagerly, before batch 1 is ever
dispatched -- while the task worktree is still at its pre-implementation state -- so a
self-capturing suite's first run (and therefore its baseline) lands on the right commit.
This module only runs the command and reports the result;
it does not parse, move, or persist whatever baseline/snapshot artifacts the project's own test
framework writes as a side effect of that run.

Public API:
    run_preflight(gate_cmd, git_root, *, hub_root=None) -> dict
    Runs `gate_cmd` once through the shared verify runner (native shell,
    bounded by `pipeline.verify_timeout_minutes`) from `git_root` and
    returns a result dict. Never raises to its caller -- every failure
    mode (no command configured, timeout, non-zero exit, invalid timeout
    config, or a launch failure such as a missing binary) degrades to a
    `{"result": ...}` dict. Results of a run carry `"verify_runs"`, the
    run summaries also logged to the task's `## Verify log`.

    run_gate(gate_cmd, git_root, *, hub_root=None) -> dict
    Runs `gate_cmd` once the same way as `run_preflight`, from
    `git_root`, for use at Handoff time instead of a pre-implementation
    baseline pre-flight. Additionally performs the Windows
    dotnet-build-server-shutdown cleanup on success and has no
    `"skipped"` case -- its caller already checks `gate_cmd is None`
    before ever calling this function.

    `hub_root` locates config and status.md; it defaults to the hub
    resolved from `git_root`.
"""

from __future__ import annotations

import platform
import subprocess
from pathlib import Path

import _config
import _paths
import _verify_run
from _implementer_common import _extract_failure_signatures


def _build_truncated_reason(out: str) -> str:
    """
    Build the captured-output `reason` string for a failed gate run.

    Mirrors `_implementer_common._run_verify_gate`'s existing truncation-enrichment shape:
    when `out` fits within the 2000-character tail kept for the human-facing reason, it is returned
    unchanged.
    Otherwise the omitted prefix is scanned for failure-marker lines (via
    `_extract_failure_signatures`) so a failure line pushed out of a blind tail-truncation by later
    passing-noise (e.g. alphabetically-earlier `ok` package lines in a `go test ./...` run) is still
    recoverable, per GitHub #1020.

    Args:
        out: The stripped, combined stdout+stderr of a failed gate run.

    Returns:
        `out` unchanged when its length is at most 2000 characters.
        Otherwise an omitted-content marker -- naming the omitted character count, plus up to 20
        extracted failure-marker lines recovered from the omitted portion when any exist -- followed
        by the last 2000 characters of `out`.
    """
    if len(out) <= 2000:
        return out

    tail = out[-2000:]
    omitted = out[:-2000]
    fail_lines = _extract_failure_signatures(omitted)[:20]
    marker = f"[... {len(omitted)} earlier chars omitted"
    if fail_lines:
        marker += "; earlier failures:\n" + "\n".join(fail_lines)
    marker += " ...]\n"
    return marker + tail


def _run_gate_command(
    gate_cmd: str, git_root: Path, hub_root: Path | None, label: str
) -> dict:
    """
    Run `gate_cmd` through the shared verify runner and map its outcome to a result dict.

    Resolves config, the verify timeout and the status.md path itself, so a bad
    `pipeline.verify_timeout_minutes` or any other failure is reported as `blocked`
    rather than raised.

    Returns:
        {"result": "ok", "verify_runs": [...]} on exit 0;
        {"result": "blocked", "reason": ..., "verify_runs": [...]} on timeout, launch failure or
        non-zero exit;
        {"result": "blocked", "reason": <message>} when the run could not be set up or started.
    """
    try:
        hub = hub_root if hub_root is not None else _paths.resolve_hub_path(git_root)
        cfg = _config.load_config(hub, git_root)
        timeout_s = _verify_run.timeout_seconds(cfg)
        status_path = _verify_run.resolve_status_path(hub, cfg)
        run = _verify_run.run_verify(
            gate_cmd,
            cwd=git_root,
            label=label,
            git_root=git_root,
            timeout_s=timeout_s,
            shell_mode="native",
            status_path=status_path,
        )
    except Exception as exc:
        return {"result": "blocked", "reason": str(exc)}

    verify_runs = [run.summary()]
    if run.timed_out:
        reason = (
            _verify_run.timeout_prefix(run)
            + _build_truncated_reason(run.output.strip())
            + _verify_run.output_suffix(run)
        )
        return {"result": "blocked", "reason": reason, "verify_runs": verify_runs}
    if run.exit_code is None:
        return {"result": "blocked", "reason": run.output, "verify_runs": verify_runs}
    if run.exit_code != 0:
        reason = _build_truncated_reason(run.output.strip()) + _verify_run.output_suffix(run)
        return {"result": "blocked", "reason": reason, "verify_runs": verify_runs}
    return {"result": "ok", "verify_runs": verify_runs}


def run_preflight(
    gate_cmd: str | None, git_root: Path, *, hub_root: Path | None = None
) -> dict:
    """
    Run the configured `done_gate` command once as a pre-implementation baseline pre-flight.

    The command runs through the shared verify runner (label `done-gate-preflight`, native shell)
    from `git_root`, bounded by `pipeline.verify_timeout_minutes`, and the run is recorded in the
    task's `## Verify log`.
    Failure reasons carry the truncated output, the saved-output path, and a timeout prefix when
    the run timed out.

    This function never raises. `gate_cmd is None` is reported as `skipped` rather than run at all;
    a timeout, launch failure, non-zero exit, or invalid timeout config is reported as `blocked`.

    Args:
        gate_cmd: The `pipeline.done_gate` command string,
            or None if no done_gate is configured for this task.
        git_root: Absolute path to the repo root the command runs from.
        hub_root: The task hub, used to load config and locate status.md.
            Defaults to the hub resolved from `git_root`.

    Returns:
        One of:
            {"result": "skipped", "reason": "no done_gate configured"}
            {"result": "ok", "verify_runs": [<run summary>]}
            {"result": "blocked", "reason": <failure reason>, "verify_runs": [<run summary>]}
            {"result": "blocked", "reason": <message>} when the run could not be set up
    """
    # No done_gate configured for this task -- nothing to pre-flight.
    if gate_cmd is None:
        return {"result": "skipped", "reason": "no done_gate configured"}

    return _run_gate_command(gate_cmd, git_root, hub_root, "done-gate-preflight")


def run_gate(gate_cmd: str, git_root: Path, *, hub_root: Path | None = None) -> dict:
    """
    Run the configured `done_gate` command once as the Handoff-time gate.

    Runs through the shared verify runner (label `done-gate`, native shell) with the same
    timeout, logging and never-raise contract as a pre-flight run.
    `gate_cmd` is assumed to already be a non-null string -- the caller checks
    `gate_cmd is None` itself before calling, so there is no `"skipped"` result case.

    On a successful run, this also performs a best-effort Windows-only cleanup:
    if `gate_cmd` mentions `dotnet` and the host platform is Windows,
    it shuts down any lingering dotnet build server processes so they don't hold file locks that
    would block mill-finalize.
    A failure in that best-effort cleanup is swallowed and never turns a successful gate result into
    a raised exception.

    Callers needing an exit-code-based halt contract (as Handoff does) must branch on the returned
    `result["result"] == "blocked"` themselves -- `run_gate` itself never calls `sys.exit`.

    Args:
        gate_cmd: The `pipeline.done_gate` command string. Must not be None.
        git_root: Absolute path to the repo root the command runs from.
        hub_root: The task hub, used to load config and locate status.md.
            Defaults to the hub resolved from `git_root`.

    Returns:
        One of:
            {"result": "ok", "verify_runs": [<run summary>]}
            {"result": "blocked", "reason": <failure reason>, "verify_runs": [<run summary>]}
            {"result": "blocked", "reason": <message>} when the run could not be set up
    """
    gate_result = _run_gate_command(gate_cmd, git_root, hub_root, "done-gate")
    if gate_result["result"] != "ok":
        return gate_result

    # Best-effort Windows-only cleanup: release dotnet build-server process locks before
    # mill-finalize runs. A failure here must never turn a successful gate result into a raised
    # exception.
    if "dotnet" in gate_cmd.lower() and platform.system() == "Windows":
        try:
            subprocess.run(
                ["dotnet", "build-server", "shutdown"], capture_output=True, timeout=30
            )
        except Exception:
            pass

    return gate_result
