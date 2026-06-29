"""Shared helpers for millpy-implement.py and millpy-fix.py."""

import json
import os
import re
import shutil
import subprocess
import sys
import _agent_dispatch
import _cleanliness
import _status
import _subprocess_util
import _timestamp
from pathlib import Path


def _is_only_start_batch_commit(project_root: Path, start_sha: str) -> bool:
    """Return True when the only commit since start_sha is the batch-start housekeeping commit.

    Detects Bug #557: prepare makes a "mill-go: start batch" commit, so HEAD != start_sha
    even when the implementer wrote zero code commits. A single-card retry has start_sha ==
    the start-batch commit, so its real code commit message will NOT start with the prefix.
    Returns False on any subprocess failure so the guard is always safe to skip on error.
    """
    result = _subprocess_util.run(
        ["git", "log", "--pretty=%s", f"{start_sha}..HEAD"],
        cwd=project_root,
    )
    if result.returncode != 0:
        return False
    # Collect non-empty commit subject lines since start_sha.
    msgs = [m.strip() for m in result.stdout.strip().splitlines() if m.strip()]
    return len(msgs) == 1 and msgs[0].startswith("mill-go: start batch")


def _content_commit_count(project_root: Path, start_sha: str | None) -> int | None:
    """
    Count content commits since start_sha, excluding the batch-start housekeeping commit.

    The prepare stage always makes a "mill-go: start batch <name>" commit before the
    implementer runs. Because start_sha is captured BEFORE that commit, a raw
    `git rev-list --count start_sha..HEAD` over-counts by one whenever the housekeeping
    commit is present. This helper subtracts it so that callers see the true number of
    content commits the implementer made.

    Algorithm:
      1. Return None when start_sha is None (gate disabled).
      2. Run `git rev-list --count start_sha..HEAD` to get the raw range count.
         Return None on non-zero exit or non-numeric output.
      3. Run `git log --pretty=%s start_sha..HEAD` to get per-commit subjects.
         Git log returns newest-first, so the last non-empty subject is the oldest commit.
      4. When the oldest subject starts with "mill-go: start batch", subtract 1 from the
         raw count (floored at 0). This is the housekeeping commit that prepare always
         inserts; it is not a content commit.
      5. Return the adjusted count.

    Returns None on any subprocess failure so callers can treat it as a gate no-op.

    Args:
        project_root: Path to the worktree root used as cwd for git subprocesses.
        start_sha: The SHA recorded at batch start. None disables the count (returns None).

    Returns:
        Content commit count (int >= 0), or None when inputs are absent or git fails.
    """
    if start_sha is None:
        return None

    # Get the raw commit count since start_sha.
    result = _subprocess_util.run(
        ["git", "rev-list", "--count", f"{start_sha}..HEAD"],
        cwd=project_root,
    )
    if result.returncode != 0:
        return None

    # Guard the parse: non-numeric stdout must not raise (e.g. mocked sha strings in tests).
    try:
        count = int(result.stdout.strip())
    except ValueError:
        return None

    # Inspect the oldest commit subject to detect the housekeeping commit.
    # git log returns newest-first; the last non-empty line is the oldest commit.
    log_result = _subprocess_util.run(
        ["git", "log", "--pretty=%s", f"{start_sha}..HEAD"],
        cwd=project_root,
    )
    if log_result.returncode == 0:
        subjects = [s.strip() for s in log_result.stdout.strip().splitlines() if s.strip()]
        if subjects:
            oldest_subject = subjects[-1]
            # The housekeeping commit is "mill-go: start batch <name>" -- exclude it.
            if oldest_subject.startswith("mill-go: start batch"):
                count = max(0, count - 1)

    return count


def _batch_completeness_stuck(
    project_root: Path,
    start_sha: str | None,
    card_count: int | None,
    session_id: str | None,
    *,
    verify_cmd: str | None = None,
) -> dict | None:
    """
    Check whether enough commits exist since start_sha for the declared card_count.

    Returns None (gate disabled) when verify_cmd is not None — a passing verify
    command is conclusive evidence of batch completeness, so the heuristic commit-
    count check is unnecessary. Also returns None when start_sha is None,
    card_count is None, or card_count <= 0.

    Otherwise counts commits via `git rev-list --count start_sha..HEAD`. If the
    subprocess fails or returns a non-numeric string, returns None rather than
    crashing (callers such as test-millpy-implement.py mock _subprocess_util.run
    to return non-numeric strings for all git calls). Only when a numeric count
    is obtained and count < card_count is a stuck dict returned; otherwise returns None.

    Args:
        project_root: Path to the worktree root.
        start_sha: The SHA recorded at batch start; None disables the gate.
        card_count: Number of Card headings in the batch file; None or 0 disables the gate.
        session_id: Session identifier included in the returned dict when non-None.
        verify_cmd: When not None, the gate is disabled entirely (verify is conclusive).

    Returns:
        A stuck dict with stuck_type="transient" and commits_made when incomplete, or None otherwise.
    """
    # When a verify command is present, a passing verify is conclusive; skip the heuristic gate.
    if verify_cmd is not None:
        return None

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
            "commits_made": count,
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


def _has_windows_lock_error_signature(text: str) -> bool:
    """
    Check if text contains a Windows file-locking error signature (case-insensitive).

    Detects file-locking error patterns: winerror 32, process cannot access,
    being used by another process.

    Args:
        text: A string to check (e.g., exception message).

    Returns:
        True if any lock-error signature is present; False otherwise.
    """
    text_lower = text.lower()
    lock_error_patterns = [
        "winerror 32",
        "process cannot access",
        "being used by another process",
    ]
    return any(pattern in text_lower for pattern in lock_error_patterns)


def _has_windows_cleanup_race_signature(text: str) -> bool:
    """
    Check if text contains a Windows cleanup-race signature (case-insensitive).

    Detects cleanup-race patterns from tempdir cleanup: unlinkat, access is denied,
    winerror 5, winerror 32.

    Args:
        text: A string to check (e.g., exception message or command output).

    Returns:
        True if any cleanup-race signature is present; False otherwise.
    """
    text_lower = text.lower()
    cleanup_signatures = [
        "unlinkat",
        "access is denied",
        "winerror 5",
        "winerror 32",
    ]
    return any(sig in text_lower for sig in cleanup_signatures)


def _is_benign_windows_cleanup(output: str) -> bool:
    """
    Check if the combined output contains only a Windows cleanup-race signature with no test failures.

    Returns True only when both conditions hold:
    1. The output contains a Windows cleanup-race signature (case-insensitive any of:
       unlinkat, access is denied, winerror 5, winerror 32)
    2. The output contains NO test-failure markers. Markers are matched
       case-insensitively against the lowercased output using line-anchored
       patterns to avoid false positives on benign package paths containing
       "fail" as a substring (e.g. "ok  \\tpkg/failover\\t0.1s"):
       - "--- fail" (Go per-test failure prefix; safe as a substring because
         the leading "--- " makes it unambiguous)
       - re pattern (?m)^fail[\\t ] (Go package-summary line "FAIL\\tpkg"
         or "FAIL " at the start of a line -- a real TAB or space after fail)
       - "panic:" (Go runtime panic)
       - "build failed" (compiler/linker failure)

    This is used to distinguish benign file-cleanup races from real test failures on Windows.

    Args:
        output: Combined stdout and stderr from a verify command.

    Returns:
        True if output contains cleanup signature with no failure markers; False otherwise.
    """
    output_lower = output.lower()

    # Check for cleanup-race signatures.
    has_cleanup_signature = _has_windows_cleanup_race_signature(output)

    # Check for test-failure markers using line-anchored patterns.
    # The bare substring "fail" is intentionally NOT used here because Go test
    # output includes lines like "ok  \tpkg/failover\t0.1s" whose path contains
    # "fail" as a substring but represents a passing package.
    has_failure_marker = (
        # Go per-test failure line (e.g. "--- FAIL: TestFoo (0.00s)")
        "--- fail" in output_lower
        # Go package-summary failure line (e.g. "FAIL\tgithub.com/pkg" or "FAIL pkg")
        # anchored to line-start so a path like "pkg/failover" does not match.
        or bool(re.search(r"(?m)^fail[\t ]", output_lower))
        # Go runtime panic
        or "panic:" in output_lower
        # Compiler / linker failure
        or "build failed" in output_lower
    )

    return has_cleanup_signature and not has_failure_marker


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

        # Check if tracked files have changes. --ignore-cr-at-eol ensures that a
        # pure CRLF-vs-LF delta (e.g. from text-mode CRLF translation on Windows)
        # is treated the same as whitespace and does not prevent drift detection.
        result_diff = _subprocess_util.run(
            ["git", "-C", str(project_root), "diff", "--ignore-cr-at-eol"],
            check=False,
        )
        if result_diff.returncode != 0:
            return False
        if not result_diff.stdout.strip():
            # No tracked-file changes at all
            return False

        # Check if those changes are purely whitespace. --ignore-cr-at-eol is
        # added here too because git diff -w does not suppress CR-at-EOL diffs
        # on its own; a CRLF-only delta would still appear as content under -w
        # without this flag, causing a false "not formatter drift" result.
        result_diff_w = _subprocess_util.run(
            ["git", "-C", str(project_root), "diff", "-w", "--ignore-cr-at-eol"],
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


def _run_verify_gate(
    project_root: Path,
    verify_cmd: str | None,
    *,
    git_root: Path | None = None,
) -> dict | None:
    """
    Run a verify command and return a stuck dict on failure, None on success or when verify_cmd is None.

    When verify_cmd is not None, runs the command via bash on Windows (so the
    POSIX env-prefix syntax is honoured) and via subprocess.run with shell=True
    elsewhere, capturing output as text. On non-zero return code, returns a stuck
    dict with stuck_type="verify" and reason set to the last 2000 characters of
    stdout+stderr. On success (rc 0) or when verify_cmd is None, returns None.

    On Windows (sys.platform == "win32"), applies an additional gate: if the output
    contains a benign cleanup-race signature and no test failures (per
    _is_benign_windows_cleanup), treats the non-zero exit as success and returns None.

    After the verify subprocess completes (regardless of exit code), if the platform
    is win32 and the command contains "dotnet", runs `dotnet build-server shutdown`
    to release VBCSCompiler/MSBuild locks that prevent re-runs. This call is wrapped
    in try/except so a TimeoutExpired or FileNotFoundError here never poisons the
    verify verdict -- it is best-effort, non-fatal cleanup.

    Args:
        project_root: Path to the worktree root.
        verify_cmd: Verify command to run (e.g., "pytest tests/ -q"), or None.
        git_root: Optional git root directory used as cwd for the verify subprocess.
            When None, falls back to project_root.

    Returns:
        A stuck dict {"status": "stuck", "stuck_type": "verify", "reason": <tail>} on
        non-zero return (unless win32 benign cleanup), or None on success or when verify_cmd is None.
    """
    if verify_cmd is None:
        return None

    # Use git_root as the subprocess cwd when provided; fall back to project_root
    # for flat layouts where the two paths are identical.
    effective_cwd = git_root if git_root is not None else project_root

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
            cwd=effective_cwd,
            **run_kwargs,
        )
        # dotnet cleanup: release testhost/MSBuild locks before caller retries.
        # Wrapped in try/except so a TimeoutExpired or FileNotFoundError here
        # never poisons the verify verdict (best-effort, non-fatal).
        if (
            sys.platform == "win32"
            and verify_cmd is not None
            and "dotnet" in verify_cmd.lower()
        ):
            try:
                subprocess.run(
                    ["dotnet", "build-server", "shutdown"],
                    capture_output=True,
                    timeout=30,
                )
            except Exception:
                pass
        if result.returncode != 0:
            output = result.stdout + result.stderr
            # On Windows, check if this is a benign cleanup-race with no test failure
            if sys.platform == "win32" and _is_benign_windows_cleanup(output):
                return None
            # Use last 2000 characters of the output
            output_stripped = output.strip()
            reason = (
                output_stripped[-2000:]
                if len(output_stripped) > 2000
                else output_stripped
            )
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


def _run_verify_gates(
    project_root: Path,
    verify_cmd: str | None,
    module_wide_verify_cmd: str | None,
    *,
    git_root: Path | None = None,
) -> dict | None:
    """
    Run the batch-level verify gate and, if it passes, the module-wide verify gate.

    Sequences two calls to _run_verify_gate so that every success-emit path in
    _forward_output passes through both gates with a single call. The batch gate
    runs first; only when it returns None (pass or skipped) does the module-wide
    gate run. This ensures a batch failure is never masked by a module-wide pass
    and that the module-wide gate cannot be accidentally skipped on any code path
    that replaces a bare _run_verify_gate call with this helper.

    When module_wide_verify_cmd is None, behavior is identical to calling
    _run_verify_gate(project_root, verify_cmd) alone -- fully backward-compatible.

    When the module-wide gate fails its stuck dict reason is prefixed with
    "[module-wide verify]" so the operator can distinguish it from a batch-level
    verify failure in the stuck report.

    Args:
        project_root: Path to the worktree root.
        verify_cmd: Batch-level verify command, or None to skip.
        module_wide_verify_cmd: Module-wide verify command run after the batch gate
            passes, or None to skip.
        git_root: Optional git root directory used as cwd for verify subprocesses.
            Threaded to both _run_verify_gate calls. When None, falls back to project_root.

    Returns:
        A stuck dict on the first gate that fails, or None when both pass (or are
        skipped).
    """
    # Run the batch-level gate first; propagate any failure immediately.
    batch_result = _run_verify_gate(project_root, verify_cmd, git_root=git_root)
    if batch_result is not None:
        return batch_result

    # Batch gate passed (or was skipped); run the module-wide gate if configured.
    if module_wide_verify_cmd is None:
        return None

    module_result = _run_verify_gate(
        project_root, module_wide_verify_cmd, git_root=git_root
    )
    if module_result is not None:
        # Prefix the reason so the operator can identify the source of the failure.
        original_reason = module_result.get("reason", "")
        module_result["reason"] = f"[module-wide verify] {original_reason}"
        return module_result

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
    module_wide_verify_cmd: str | None = None,
    card_count: int | None = None,
    task_dir: Path | None = None,
    parent_branch: str | None = None,
    nits_only: bool = False,
    status_path: Path | None = None,
    nits_scope: str | None = None,
    git_root: Path | None = None,
) -> int:
    """Read sub-agent output and finalize.

    Reads the agent's final text from agent_output_path (utf-8) and delegates
    to _forward_output with the captured output. Returns the code from _forward_output.

    Args:
        agent_output_path: Path to the file containing the sub-agent's output text.
        project_root: Path to the worktree root (hub directory).
        start_sha: Git SHA recorded at batch start; used for no-content-commit detection.
        snapshot_path: Path to the cleanliness snapshot file; enables new-dirt detection.
        session_id: Session identifier threaded into the output envelope.
        verify_cmd: Batch-level verify command to run before emitting success.
        module_wide_verify_cmd: Module-wide verify command run after the batch gate passes.
        card_count: Number of Card headings in the batch; enables the completeness gate.
        task_dir: Worktree-relative path to the task directory (_mill/).
        parent_branch: Name of the parent branch for in-scope dirty-tree detection.
        nits_only: When True, writes a nits-fixed marker on success.
        status_path: Path to the status.md file; required when nits_only is True.
        nits_scope: Scope label for the nits-fixed marker; required when nits_only is True.
        git_root: Optional git root directory used as cwd for verify subprocesses.
            When None, falls back to project_root. Pass the actual git root in nested
            layouts so the verify command runs from the repo root rather than the hub
            sub-directory, preventing spurious MSB1009 / path-not-found errors.
    """
    output = Path(agent_output_path).read_text(encoding="utf-8")
    return _forward_output(
        output,
        project_root,
        start_sha=start_sha,
        snapshot_path=snapshot_path,
        session_id=session_id,
        verify_cmd=verify_cmd,
        module_wide_verify_cmd=module_wide_verify_cmd,
        card_count=card_count,
        task_dir=task_dir,
        parent_branch=parent_branch,
        nits_only=nits_only,
        status_path=status_path,
        nits_scope=nits_scope,
        git_root=git_root,
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
    module_wide_verify_cmd: str | None = None,
    card_count: int | None = None,
    task_dir: Path | None = None,
    parent_branch: str | None = None,
    nits_only: bool = False,
    status_path: Path | None = None,
    nits_scope: str | None = None,
    git_root: Path | None = None,
) -> int:
    """Extract the last JSON object containing a 'status' key from output.

    Returns 0 in both success and fallback cases -- the JSON on stdout is how the caller reads state.
    When no valid JSON is found, emits a stuck/logic sentinel.
    When the inferred-success fallback fires, the emitted JSON uses ``session_id`` if supplied,
    falling back to the literal ``"unknown"`` for backwards compatibility with callers that don't pass it.
    When verify_cmd is not None, runs it before emitting any success; if the command fails,
    demotes the success to stuck/verify with the command's output in reason.
    When module_wide_verify_cmd is not None, it is run as a second gate after verify_cmd passes
    (or is skipped); a module-wide failure also demotes to stuck/verify with a
    "[module-wide verify]" prefix in the reason. When module_wide_verify_cmd is None, behavior
    is unchanged (single gate, backward-compatible).
    When card_count is provided, the completeness gate checks that enough commits were made.
    When task_dir and parent_branch are provided, the dirty-tree gate checks in-scope cleanliness.
    When nits_only is True and status_path and nits_scope are not None, on the parsed-success
    emit path (where a fixer's own reported status == "success" is about to be printed),
    adds "nits_applied": True to the dict and writes a nits-fixed-<scope> marker to the status file.
    When git_root is not None, it is used as the cwd for verify subprocesses instead of
    project_root. This corrects verify behavior in nested layouts where the plan's verify
    command must run from the git root rather than the hub sub-directory.
    """
    parsed = _extract_status_json(output)
    if parsed is not None:
        # Apply verify gates ONLY for self-reported success
        if parsed.get("status") == "success":
            gate_result = _run_verify_gates(
                project_root, verify_cmd, module_wide_verify_cmd, git_root=git_root
            )
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

            # Check for no-content-commit success: reject if HEAD == start_sha or if
            # the only commit since start_sha is the batch-start housekeeping commit.
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
                # Guard against the start-batch-commit-only case (Bug #557): prepare makes a
                # "mill-go: start batch" commit, so HEAD != start_sha even when the implementer
                # wrote zero code commits. Detect this and demote to stuck/logic.
                if result.returncode == 0 and _is_only_start_batch_commit(
                    project_root, start_sha
                ):
                    print(
                        json.dumps(
                            {
                                "status": "stuck",
                                "stuck_type": "logic",
                                "reason": "success reported but no content commit (only batch-start commit since start_sha)",
                                "session_id": session_id or parsed.get("session_id"),
                            }
                        )
                    )
                    return 0

            # Resolve session id for the new gates: prefer caller-supplied over parsed.
            _gate_session_id = session_id or parsed.get("session_id")

            # Completeness gate: demote to stuck/transient when fewer commits than cards.
            _completeness_result = _batch_completeness_stuck(
                project_root,
                start_sha,
                card_count,
                _gate_session_id,
                verify_cmd=verify_cmd,
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

            # On the parsed-success emit path, handle nits-only marker and flag
            if nits_only and status_path and nits_scope:
                parsed["nits_applied"] = True
                _status.append_phase(
                    status_path, f"nits-fixed-{nits_scope}", _timestamp.now_utc_iso()
                )

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
                                    # Apply verify gates before emitting success
                                    gate_result = _run_verify_gates(
                                        project_root,
                                        verify_cmd,
                                        module_wide_verify_cmd,
                                        git_root=git_root,
                                    )
                                    if gate_result is not None:
                                        gate_result["commit_sha"] = new_head
                                        print(json.dumps(gate_result))
                                        return 0
                                    # Completeness gate: incomplete batch demotes to stuck/transient.
                                    _comp = _batch_completeness_stuck(
                                        project_root,
                                        start_sha,
                                        card_count,
                                        session_id,
                                        verify_cmd=verify_cmd,
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
                                        # Guard against start-batch-commit-only case on the
                                        # formatter-drift inference path (Bug #557).
                                        if _is_only_start_batch_commit(
                                            project_root, start_sha
                                        ):
                                            print(
                                                json.dumps(
                                                    {
                                                        "status": "stuck",
                                                        "stuck_type": "logic",
                                                        "reason": "inferred success but only batch-start commit since start_sha",
                                                        "session_id": session_id
                                                        or "unknown",
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
                    # Apply verify gates before emitting success
                    gate_result = _run_verify_gates(
                        project_root,
                        verify_cmd,
                        module_wide_verify_cmd,
                        git_root=git_root,
                    )
                    if gate_result is not None:
                        gate_result["commit_sha"] = head
                        print(json.dumps(gate_result))
                        return 0
                    # Completeness gate: incomplete batch demotes to stuck/transient.
                    _comp = _batch_completeness_stuck(
                        project_root,
                        start_sha,
                        card_count,
                        session_id,
                        verify_cmd=verify_cmd,
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
                        # Guard against start-batch-commit-only case on the
                        # snapshot-present clean-tree inference path (Bug #557).
                        if _is_only_start_batch_commit(project_root, start_sha):
                            print(
                                json.dumps(
                                    {
                                        "status": "stuck",
                                        "stuck_type": "logic",
                                        "reason": "inferred success but only batch-start commit since start_sha",
                                        "session_id": session_id or "unknown",
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
                    # Apply verify gates before emitting success
                    gate_result = _run_verify_gates(
                        project_root,
                        verify_cmd,
                        module_wide_verify_cmd,
                        git_root=git_root,
                    )
                    if gate_result is not None:
                        gate_result["commit_sha"] = head
                        print(json.dumps(gate_result))
                        return 0
                    # Completeness gate: incomplete batch demotes to stuck/transient.
                    _comp = _batch_completeness_stuck(
                        project_root,
                        start_sha,
                        card_count,
                        session_id,
                        verify_cmd=verify_cmd,
                    )
                    if _comp is not None:
                        print(json.dumps(_comp))
                        return 0
                    # Guard against start-batch-commit-only case on the
                    # no-snapshot inference path (Bug #557).
                    if _is_only_start_batch_commit(project_root, start_sha):
                        print(
                            json.dumps(
                                {
                                    "status": "stuck",
                                    "stuck_type": "logic",
                                    "reason": "inferred success but only batch-start commit since start_sha",
                                    "session_id": session_id or "unknown",
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
