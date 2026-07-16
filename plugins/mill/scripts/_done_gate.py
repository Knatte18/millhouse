"""
Opt-in Prepare-phase baseline pre-flight for `pipeline.done_gate`.

Fixes #650: a self-capturing regression/snapshot test suite used as the
`done_gate` command captures its own "baseline" the first time it runs. If
that first run only ever happens at Handoff (the existing "0. Pre-done
gate" block in mill-go SKILL.md), the baseline gets captured from the
task's own just-finished implementation instead of from the pre-implementation
parent-branch state -- so the Handoff-time comparison always passes,
providing zero actual regression protection.

`run_preflight` gives mill-go a way to run `done_gate` once, eagerly, before
batch 1 is ever dispatched -- while the task worktree is still at its
pre-implementation state -- so a self-capturing suite's first run (and
therefore its baseline) lands on the right commit. This module only runs
the command and reports the result; it does not parse, move, or persist
whatever baseline/snapshot artifacts the project's own test framework
writes as a side effect of that run.

Public API:
    run_preflight(gate_cmd, git_root) -> dict
        Runs `gate_cmd` once via `subprocess.run(..., shell=True)` from
        `git_root` and returns a result dict. Never raises to its caller --
        every failure mode (no command configured, non-zero exit, or an
        unexpected subprocess-launch failure such as a missing binary)
        degrades to a `{"result": ...}` dict.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def run_preflight(gate_cmd: str | None, git_root: Path) -> dict:
    """
    Run the configured `done_gate` command once as a pre-implementation
    baseline pre-flight.

    Mirrors the exact subprocess-invocation shape already used inline in
    mill-go SKILL.md's Handoff-time "0. Pre-done gate" block --
    `subprocess.run(gate_cmd, cwd=git_root, shell=True, capture_output=True,
    text=True)` -- including that block's stdout+stderr concatenation and
    2000-character tail truncation of the captured output, so both call
    sites (this pre-flight and the Handoff-time gate) treat the same
    `gate_cmd` identically.

    This function never raises. `gate_cmd is None` is reported as
    `skipped` rather than run at all; a non-zero exit is reported as
    `blocked` with the captured output; and an unexpected failure to even
    launch the subprocess (e.g. `gate_cmd` invokes a missing binary) is
    also degraded to `blocked` rather than propagating the exception, per
    this plan's "never raise from a new gate/check function" Shared
    Decision.

    Args:
        gate_cmd: The `pipeline.done_gate` command string, or None if no
            done_gate is configured for this task.
        git_root: Absolute path to the repo root the command runs from --
            identical cwd to the Handoff-time "0. Pre-done gate" invocation.

    Returns:
        One of:
            {"result": "skipped", "reason": "no done_gate configured"}
            {"result": "ok"}
            {"result": "blocked", "reason": <captured output, tail-truncated to 2000 chars>}
    """
    # No done_gate configured for this task -- nothing to pre-flight.
    if gate_cmd is None:
        return {"result": "skipped", "reason": "no done_gate configured"}

    try:
        result = subprocess.run(
            gate_cmd, cwd=git_root, shell=True, capture_output=True, text=True
        )
    except Exception as exc:
        # Any unexpected failure during subprocess launch (e.g. missing binary,
        # invalid cwd, or other OS/runtime errors) degrades to "blocked" rather
        # than raising -- the never-raise contract applies to all failure modes.
        return {"result": "blocked", "reason": str(exc)}

    if result.returncode != 0:
        # Same stdout+stderr concatenation and 2000-char tail truncation as
        # the Handoff-time "0. Pre-done gate" block, so a caller reading
        # either result's "reason" sees output shaped the same way.
        out = (result.stdout + result.stderr).strip()
        reason = out[-2000:] if len(out) > 2000 else out
        return {"result": "blocked", "reason": reason}

    return {"result": "ok"}
