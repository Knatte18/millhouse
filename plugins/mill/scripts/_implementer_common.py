"""Shared helpers for millpy-implement.py and millpy-fix.py."""

import json
import os
import shutil
import subprocess
import _agent_dispatch
import _cleanliness
import _subprocess_util
from pathlib import Path


def _batch_completeness_stuck(
    project_root: Path,
    start_sha: str | None,
    card_count: int | None,
    session_id: str | None,
) -> dict | None:
    """
    Check whether enough commits exist since start_sha for the declared card_count.

    Returns None (gate disabled) when start_sha is None, card_count is None,
    or card_count <= 0. Otherwise counts commits via `git rev-list --count
    start_sha..HEAD`. If the subprocess fails or returns a non-numeric string,
    returns None rather than crashing (callers such as test-millpy-implement.py
    mock _subprocess_util.run to return non-numeric strings for all git calls).
    Only when a numeric count is obtained and count < card_count is a stuck
    dict returned; otherwise returns None.

    Args:
        project_root: Path to the worktree root.
        start_sha: The SHA recorded at batch start; None disables the gate.
        card_count: Number of Card headings in the batch file; None or 0 disables the gate.
        session_id: Session identifier included in the returned dict when non-None.

    Returns:
        A stuck dict with stuck_type="transient" when incomplete, or None otherwise.
    """
    # Gate is a no-op when any required input is absent or card_count is zero/negative.
    if start_sha is None or card_count is None or card_count <= 0:
        return None

    # Count commits made since the batch start SHA.
    result = _subprocess_util.run(
        ["git", "rev-list", "--count", f"{start_sha}..HEAD"],
        cwd=project_root,
    )
    if result.returncode != 0:
        # Git failure -- treat as no-op rather than crashing finalize.
        return None

    # Guard the parse: non-numeric stdout (e.g. a mocked sha string) must not raise.
    try:
        count = int(result.stdout.strip())
    except ValueError:
        return None

    if count < card_count:
        return {
            "status": "stuck",
            "stuck_type": "transient",
            "reason": (
                f"batch incomplete: {count} commit(s) since start but"
                f" {card_count} card(s) in batch -- implementer stopped before finishing all cards"
            ),
            "session_id": session_id or "unknown",
        }
    return None


def _in_scope_dirty_stuck(
    project_root: Path,
    task_dir: Path | None,
    parent_branch: str | None,
    session_id: str | None,
) -> dict | None:
    """
    Check whether any in-scope files are dirty at finalize time.

    Returns None when task_dir or parent_branch is None (gate disabled).
    Otherwise calls _cleanliness.compute_terminal_dirt; if the returned list
    is non-empty, returns a stuck dict. Any exception from compute_terminal_dirt
    (including GitOpsError when project_root is not a real git repo) is caught
    and treated as a no-op -- the authoritative mill-go 2b cleanliness gate
    still runs afterward.

    Args:
        project_root: Path to the worktree root.
        task_dir: Worktree-relative path to the task directory (_mill/); None disables the gate.
        parent_branch: Name of the parent branch (e.g. "main"); None disables the gate.
        session_id: Session identifier included in the returned dict when non-None.

    Returns:
        A stuck dict with stuck_type="logic" when dirty, or None otherwise.
    """
    # Gate is a no-op when required inputs are absent.
    if task_dir is None or parent_branch is None:
        return None

    try:
        dirt = _cleanliness.compute_terminal_dirt(project_root, task_dir, parent_branch)
    except Exception:
        # compute_terminal_dirt raises GitOpsError on non-git paths (e.g. test fixtures).
        # Treat any failure as a safe no-op; the mill-go gate is authoritative.
        return None

    if dirt:
        return {
            "status": "stuck",
            "stuck_type": "logic",
            "reason": f"success reported but in-scope working tree dirty: {dirt}",
            "session_id": session_id or "unknown",
        }
    return None


def _posix_shell_run_args(cmd: str) -> tuple:
    """
    Build subprocess.run args to route POSIX shell commands through bash on Windows.

    On Windows (os.name == "nt"), when bash is available, returns args to invoke
    bash -c explicitly. On other platforms or when bash is unavailable, returns
    the command string with shell=True so the native shell processes it.

    POSIX verify commands often start with "PYTHONPATH= " (env-prefix syntax) that
    cmd.exe cannot parse. Running through bash honours this syntax cross-platform.

    Args:
        cmd: The command string (e.g., "PYTHONPATH= pytest tests/ -q").

    Returns:
        A tuple (run_args, run_kwargs) where run_args is either a list
        ([bash, "-c", cmd]) or a string (cmd), and run_kwargs is either {}
        or {"shell": True} to be unpacked into subprocess.run.
    """
    bash = shutil.which("bash") if os.name == "nt" else None
    if bash:
        return [bash, "-c", cmd], {}
    return cmd, {"shell": True}


def _is_formatter_drift_only(project_root: Path) -> bool:
    """Check if the only remaining dirt is whitespace-only formatter drift.

    Heuristic (deterministic): residual dirt is formatter drift ONLY when:
      - git diff (tracked files) is non-empty
      - git diff -w (ignore-all-space) is empty
      - no untracked files exist

    If either git diff subprocess returns non-zero or raises, treat as
    "not formatter drift" (skip auto-commit, proceed normally).

    Args:
        project_root: Path to the worktree root.

    Returns:
        True if all remaining changes are pure whitespace; False otherwise.
    """
    try:
        # Check if there are any untracked files
        result_untracked = _subprocess_util.run(
            [
                "git",
                "-C",
                str(project_root),
                "status",
                "--porcelain",
                "--untracked-files=all",
            ],
            check=False,
        )
        if result_untracked.returncode != 0:
            return False
        # Any line starting with ?? means untracked files exist
        for line in result_untracked.stdout.strip().split("\n"):
            if line.startswith("??"):
                return False

        # Check if tracked files have changes
        result_diff = _subprocess_util.run(
            ["git", "-C", str(project_root), "diff"],
            check=False,
        )
        if result_diff.returncode != 0:
            return False
        if not result_diff.stdout.strip():
            # No tracked-file changes at all
            return False

        # Check if those changes are purely whitespace
        result_diff_w = _subprocess_util.run(
            ["git", "-C", str(project_root), "diff", "-w"],
            check=False,
        )
        if result_diff_w.returncode != 0:
            return False
        if result_diff_w.stdout.strip():
            # -w still shows changes, so there's non-whitespace content
            return False

        # All conditions met: it's formatter drift
        return True
    except Exception:
        # On any error, treat as "not formatter drift"
        return False


def _commit_formatter_drift(project_root: Path) -> bool:
    """Auto-commit formatter drift changes.

    Stages all changes and commits with message "chore(format): commit formatter drift".
    Returns True if commit succeeded; False on any error.

    Args:
        project_root: Path to the worktree root.

    Returns:
        True if the commit succeeded; False otherwise.
    """
    try:
        # Stage all changes
        result_add = _subprocess_util.run(
            ["git", "-C", str(project_root), "add", "-A"],
            check=False,
        )
        if result_add.returncode != 0:
            return False

        # Commit with ASCII-only message
        result_commit = _subprocess_util.run(
            [
                "git",
                "-C",
                str(project_root),
                "commit",
                "-m",
                "chore(format): commit formatter drift",
            ],
            check=False,
        )
        return result_commit.returncode == 0
    except Exception:
        return False


def _run_verify_gate(project_root: Path, verify_cmd: str | None) -> dict | None:
    """
    Run a verify command and return a stuck dict on failure, None on success or when verify_cmd is None.

    When verify_cmd is not None, runs the command via bash on Windows (so the
    POSIX env-prefix syntax is honoured) and via subprocess.run with shell=True
    elsewhere, capturing output as text. On non-zero return code, returns a stuck
    dict with stuck_type="verify" and reason set to the last 2000 characters of
    stdout+stderr. On success (rc 0) or when verify_cmd is None, returns None.

    Args:
        project_root: Path to the worktree root.
        verify_cmd: Verify command to run (e.g., "pytest tests/ -q"), or None.

    Returns:
        A stuck dict {"status": "stuck", "stuck_type": "verify", "reason": <tail>} on
        non-zero return, or None on success or when verify_cmd is None.
    """
    if verify_cmd is None:
        return None

    try:
        # Plan verify commands use POSIX syntax (e.g. the mandated "PYTHONPATH= "
        # env-prefix). subprocess shell=True routes through cmd.exe on Windows,
        # which cannot parse a leading VAR= env-prefix and fails with
        # "'PYTHONPATH' is not recognized". Run through bash when available so the
        # POSIX verify command is honoured cross-platform; fall back to shell=True
        # only when bash is absent.
        run_args, run_kwargs = _posix_shell_run_args(verify_cmd)
        result = subprocess.run(
            run_args,
            capture_output=True,
            text=True,
            cwd=project_root,
            **run_kwargs,
        )
        if result.returncode != 0:
            output = (result.stdout + result.stderr).strip()
            # Use last 2000 characters of the output
            reason = output[-2000:] if len(output) > 2000 else output
            return {
                "status": "stuck",
                "stuck_type": "verify",
                "reason": reason,
            }
    except Exception as e:
        # On any exception (e.g., missing binary), return stuck dict so caller
        # can distinguish this from a genuine pass
        return {
            "status": "stuck",
            "stuck_type": "verify",
            "reason": f"verify gate raised: {e}",
        }

    return None


def emit_prepare(
    briefs_dir: Path,
    role: str,
    scope: str,
    round_n: int,
    prompt_text: str,
    model_tier: str,
    session_id: str,
    start_sha: str | None = None,
) -> int:
    """Write brief and emit prepare JSON envelope.

    Writes the brief to briefs_dir/<role>-<sanitized_scope>-r<round_n>.md
    (scope is sanitized for Windows filename safety) and prints one JSON line
    with the brief path and metadata. Returns 0.
    """
    brief_path = _agent_dispatch.write_brief(
        briefs_dir, role, scope, round_n, prompt_text
    )
    envelope = {
        "stage": "prepare",
        "brief_path": str(brief_path.resolve()),
        "subagent_type": _agent_dispatch.SUBAGENT_IMPLEMENTER,
        "model": model_tier,
        "session_id": session_id,
        "role": role,
        "scope": scope,
        "round": round_n,
    }
    if start_sha is not None:
        envelope["start_sha"] = start_sha
    print(json.dumps(envelope))
    return 0


def emit_prepare_no_dispatch(
    model_tier: str,
    session_id: str,
    role: str,
    scope: str,
    round_n: int,
    project_root: Path,
) -> int:
    """Emit prepare JSON with dispatch_needed:false for verify-fix pass case.

    When verify passes in prepare, there is nothing to dispatch. This emits
    a special prepare envelope with dispatch_needed:false and an embedded
    success envelope. Returns 0.
    """
    result = _subprocess_util.run(["git", "rev-parse", "HEAD"], cwd=project_root)
    commit_sha = result.stdout.strip() if result.returncode == 0 else ""

    embedded_envelope = {
        "status": "success",
        "commit_sha": commit_sha,
        "session_id": session_id,
    }

    envelope = {
        "stage": "prepare",
        "dispatch_needed": False,
        "subagent_type": _agent_dispatch.SUBAGENT_IMPLEMENTER,
        "model": model_tier,
        "session_id": session_id,
        "role": role,
        "scope": scope,
        "round": round_n,
        "envelope": embedded_envelope,
    }
    print(json.dumps(envelope))
    return 0


def finalize_from_output(
    agent_output_path: Path,
    project_root: Path,
    *,
    start_sha: str | None = None,
    snapshot_path: Path | None = None,
    session_id: str | None = None,
    verify_cmd: str | None = None,
    card_count: int | None = None,
    task_dir: Path | None = None,
    parent_branch: str | None = None,
) -> int:
    """Read sub-agent output and finalize.

    Reads the agent's final text from agent_output_path (utf-8) and delegates
    to _forward_output with the captured output. Returns the code from _forward_output.
    """
    output = Path(agent_output_path).read_text(encoding="utf-8")
    return _forward_output(
        output,
        project_root,
        start_sha=start_sha,
        snapshot_path=snapshot_path,
        session_id=session_id,
        verify_cmd=verify_cmd,
        card_count=card_count,
        task_dir=task_dir,
        parent_branch=parent_branch,
    )


def _extract_status_json(output: str) -> dict | None:
    """Extract the last JSON object containing a 'status' key from output.

    Iterates through balanced-brace spans and attempts json.loads on each.
    Returns the parsed JSON dict if a valid status object is found; None otherwise.
    """
    # Find all potential JSON spans by tracking balanced braces
    candidates = []
    depth = 0
    start = None
    for i, char in enumerate(output):
        if char == "{":
            if depth == 0:
                start = i
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0 and start is not None:
                candidates.append(output[start : i + 1])
                start = None
    # Try to parse candidates in reverse order (last first)
    for candidate in reversed(candidates):
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict) and "status" in parsed:
                return parsed
        except json.JSONDecodeError:
            pass
    return None


def _forward_output(
    output: str,
    project_root: Path,
    *,
    start_sha: str | None = None,
    snapshot_path: Path | None = None,
    session_id: str | None = None,
    verify_cmd: str | None = None,
    card_count: int | None = None,
    task_dir: Path | None = None,
    parent_branch: str | None = None,
) -> int:
    """Extract the last JSON object containing a 'status' key from output.

    Returns 0 in both success and fallback cases — the JSON on stdout is how the caller reads state.
    When no valid JSON is found, emits a stuck/logic sentinel.
    When the inferred-success fallback fires, the emitted JSON uses ``session_id`` if supplied,
    falling back to the literal ``"unknown"`` for backwards compatibility with callers that don't pass it.
    When verify_cmd is not None, runs it before emitting any success; if the command fails,
    demotes the success to stuck/verify with the command's output in reason.
    When card_count is provided, the completeness gate checks that enough commits were made.
    When task_dir and parent_branch are provided, the dirty-tree gate checks in-scope cleanliness.
    """
    parsed = _extract_status_json(output)
    if parsed is not None:
        # Apply verify gate ONLY for self-reported success
        if parsed.get("status") == "success":
            gate_result = _run_verify_gate(project_root, verify_cmd)
            if gate_result is not None:
                # Verify failed; enrich with commit_sha and emit
                result = _subprocess_util.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=project_root,
                )
                if result.returncode == 0:
                    gate_result["commit_sha"] = result.stdout.strip()
                print(json.dumps(gate_result))
                return 0

            # Check for no-content-commit success: reject if HEAD == start_sha
            if start_sha is not None:
                result = _subprocess_util.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=project_root,
                )
                if result.returncode == 0 and result.stdout.strip() == start_sha:
                    # Implementer reported success but no content commit was made
                    print(
                        json.dumps(
                            {
                                "status": "stuck",
                                "stuck_type": "logic",
                                "reason": "success reported but no content commit (HEAD == start_sha)",
                                "session_id": session_id or parsed.get("session_id"),
                            }
                        )
                    )
                    return 0

            # Resolve session id for the new gates: prefer caller-supplied over parsed.
            _gate_session_id = session_id or parsed.get("session_id")

            # Completeness gate: demote to stuck/transient when fewer commits than cards.
            _completeness_result = _batch_completeness_stuck(
                project_root, start_sha, card_count, _gate_session_id
            )
            if _completeness_result is not None:
                print(json.dumps(_completeness_result))
                return 0

            # In-scope dirty-tree gate: demote to stuck/logic when tracked in-scope files remain dirty.
            _dirty_result = _in_scope_dirty_stuck(
                project_root, task_dir, parent_branch, _gate_session_id
            )
            if _dirty_result is not None:
                print(json.dumps(_dirty_result))
                return 0

        result = _subprocess_util.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
        )
        if result.returncode == 0:
            parsed["commit_sha"] = result.stdout.strip()
            violations = _cleanliness.compute_scope_violations(project_root)
            if violations:
                parsed["scope_violations"] = violations
            print(json.dumps(parsed))
        else:
            print(json.dumps(parsed))
        return 0
    try:
        if (
            start_sha is not None
            and snapshot_path is not None
            and snapshot_path.exists()
        ):
            new_dirt = _cleanliness.compute_new_dirt(project_root, snapshot_path)
            if new_dirt == []:
                result = _subprocess_util.run(
                    ["git", "rev-parse", "HEAD"], cwd=project_root
                )
                if result.returncode == 0 and result.stdout.strip() != start_sha:
                    head = result.stdout.strip()
                    result_full = _subprocess_util.run(
                        [
                            "git",
                            "-C",
                            str(project_root),
                            "status",
                            "--porcelain",
                            "--untracked-files=no",
                        ],
                        check=True,
                    )
                    if result_full.stdout.strip():
                        # Check if the remaining dirt is only formatter drift
                        if _is_formatter_drift_only(project_root):
                            # Auto-commit formatter drift
                            if _commit_formatter_drift(project_root):
                                # Re-check that tree is now clean
                                result_check = _subprocess_util.run(
                                    [
                                        "git",
                                        "-C",
                                        str(project_root),
                                        "status",
                                        "--porcelain",
                                        "--untracked-files=no",
                                    ],
                                    check=False,
                                )
                                if (
                                    result_check.returncode == 0
                                    and not result_check.stdout.strip()
                                ):
                                    # Tree is now clean; get the new HEAD after drift commit
                                    result_head = _subprocess_util.run(
                                        ["git", "rev-parse", "HEAD"],
                                        cwd=project_root,
                                    )
                                    if result_head.returncode == 0:
                                        new_head = result_head.stdout.strip()
                                    else:
                                        new_head = head
                                    # Apply verify gate before emitting success
                                    gate_result = _run_verify_gate(
                                        project_root, verify_cmd
                                    )
                                    if gate_result is not None:
                                        gate_result["commit_sha"] = new_head
                                        print(json.dumps(gate_result))
                                        return 0
                                    # Completeness gate: incomplete batch demotes to stuck/transient.
                                    _comp = _batch_completeness_stuck(
                                        project_root, start_sha, card_count, session_id
                                    )
                                    if _comp is not None:
                                        print(json.dumps(_comp))
                                        return 0
                                    # Emit success
                                    violations = _cleanliness.compute_scope_violations(
                                        project_root
                                    )
                                    if violations:
                                        print(
                                            json.dumps(
                                                {
                                                    "status": "stuck",
                                                    "stuck_type": "logic",
                                                    "reason": f"untracked files outside scope: {violations}",
                                                    "scope_violations": violations,
                                                    "inferred": True,
                                                }
                                            )
                                        )
                                    else:
                                        print(
                                            json.dumps(
                                                {
                                                    "status": "success",
                                                    "commit_sha": new_head,
                                                    "session_id": session_id
                                                    or "unknown",
                                                    "inferred": True,
                                                }
                                            )
                                        )
                                    return 0
                        # Not formatter drift, or commit failed
                        print(
                            json.dumps(
                                {
                                    "status": "stuck",
                                    "stuck_type": "logic",
                                    "reason": "inferred success but working tree dirty -- implementer likely skipped git-commit on modified files",
                                }
                            )
                        )
                        return 0
                    # Apply verify gate before emitting success
                    gate_result = _run_verify_gate(project_root, verify_cmd)
                    if gate_result is not None:
                        gate_result["commit_sha"] = head
                        print(json.dumps(gate_result))
                        return 0
                    # Completeness gate: incomplete batch demotes to stuck/transient.
                    _comp = _batch_completeness_stuck(
                        project_root, start_sha, card_count, session_id
                    )
                    if _comp is not None:
                        print(json.dumps(_comp))
                        return 0
                    violations = _cleanliness.compute_scope_violations(project_root)
                    if violations:
                        print(
                            json.dumps(
                                {
                                    "status": "stuck",
                                    "stuck_type": "logic",
                                    "reason": f"untracked files outside scope: {violations}",
                                    "scope_violations": violations,
                                    "inferred": True,
                                }
                            )
                        )
                    else:
                        print(
                            json.dumps(
                                {
                                    "status": "success",
                                    "commit_sha": head,
                                    "session_id": session_id or "unknown",
                                    "inferred": True,
                                }
                            )
                        )
                    return 0
        elif start_sha is not None and snapshot_path is None:
            result = _subprocess_util.run(
                ["git", "rev-parse", "HEAD"], cwd=project_root
            )
            if result.returncode == 0 and result.stdout.strip() != start_sha:
                head = result.stdout.strip()
                result_full = _subprocess_util.run(
                    [
                        "git",
                        "-C",
                        str(project_root),
                        "status",
                        "--porcelain",
                        "--untracked-files=no",
                    ],
                    check=True,
                )
                if not result_full.stdout.strip():
                    # Apply verify gate before emitting success
                    gate_result = _run_verify_gate(project_root, verify_cmd)
                    if gate_result is not None:
                        gate_result["commit_sha"] = head
                        print(json.dumps(gate_result))
                        return 0
                    # Completeness gate: incomplete batch demotes to stuck/transient.
                    _comp = _batch_completeness_stuck(
                        project_root, start_sha, card_count, session_id
                    )
                    if _comp is not None:
                        print(json.dumps(_comp))
                        return 0
                    print(
                        json.dumps(
                            {
                                "status": "success",
                                "commit_sha": head,
                                "session_id": session_id or "unknown",
                                "inferred": True,
                            }
                        )
                    )
                    return 0
    except Exception:
        pass
    # Before emitting the no-JSON fallback, check if the output contains API/infrastructure error markers
    # If so, classify as transient (retriable) rather than logic (ask user)
    api_error_markers = [
        "api error",
        "internal server error",
        "bad gateway",
        "service unavailable",
        "gateway timeout",
        "overloaded",
        "500 internal",
    ]
    output_lower = output.lower()
    for marker in api_error_markers:
        if marker in output_lower:
            # Found an API/infrastructure error marker; classify as transient
            print(
                json.dumps(
                    {
                        "status": "stuck",
                        "stuck_type": "transient",
                        "reason": "agent returned a raw API error before producing a structured report",
                    }
                )
            )
            return 0
    # No API error markers found; emit the default logic sentinel
    violations = _cleanliness.compute_scope_violations(project_root)
    result = {
        "status": "stuck",
        "stuck_type": "logic",
        "reason": "no structured report",
    }
    if violations:
        result["scope_violations"] = violations
    print(json.dumps(result))
    return 0
