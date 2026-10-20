"""millpy-verify-run.py -- run one verify command through the shared verify runner.

Lets a skill replay a batch's verify command with the same timeout, tree kill, output file and
Verify log row that every scripted verify site gets.
The command runs through bash where available.

Flags (all required):
    --label LABEL   label for the runner's log lines and Verify log row
    --cmd CMD       the verify command to run
    --cwd DIR       directory the command runs in

Exit codes:
    0 -- the command exited 0
    1 -- the command failed, timed out, could not launch, or the configured timeout is invalid

Output: one JSON line on stdout with label, cmd, exit_code, wall_s, first_run, timed_out,
output_path, verify_runs and, when the run did not pass, reason.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import _config
import _paths
import _verify_run
from _implementer_common import _truncate_verify_output


def _failure_reason(run: _verify_run.VerifyRun) -> str:
    """Build the reason text for a run that did not exit 0."""
    if run.timed_out:
        return (
            _verify_run.timeout_prefix(run)
            + _truncate_verify_output(run.output.strip())
            + _verify_run.output_suffix(run)
        )
    if run.exit_code is None:
        return f"verify gate raised: {run.output}"
    return _truncate_verify_output(run.output.strip()) + _verify_run.output_suffix(run)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Run one verify command through the shared verify runner."
    )
    parser.add_argument("--label", required=True, help="Label for log lines and the Verify log row.")
    parser.add_argument("--cmd", required=True, help="The verify command to run.")
    parser.add_argument("--cwd", required=True, help="Directory the command runs in.")
    args = parser.parse_args(argv)

    git_root = _paths.resolve_git_root()
    hub_root = _paths.resolve_hub_path()
    cfg = _config.load_config(hub_root, git_root)

    try:
        timeout_s = _verify_run.timeout_seconds(cfg)
    except ValueError as exc:
        print(json.dumps({"label": args.label, "cmd": args.cmd, "reason": str(exc)}))
        return 1
    status_path = _verify_run.resolve_status_path(hub_root, cfg)

    run = _verify_run.run_verify(
        args.cmd,
        cwd=Path(args.cwd),
        label=args.label,
        git_root=git_root,
        timeout_s=timeout_s,
        shell_mode="posix",
        status_path=status_path,
    )

    report = {
        "label": args.label,
        "cmd": args.cmd,
        "exit_code": run.exit_code,
        "wall_s": round(run.wall_s, 1),
        "first_run": run.first_run,
        "timed_out": run.timed_out,
        "output_path": str(run.output_path) if run.output_path is not None else None,
        "verify_runs": [run.summary()],
    }
    if run.exit_code != 0:
        report["reason"] = _failure_reason(run)
    print(json.dumps(report))
    return 0 if run.exit_code == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
