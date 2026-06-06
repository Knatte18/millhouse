"""Shared helpers for millpy-implement.py and millpy-fix.py."""
import json
import re
import _agent_dispatch
import _cleanliness
import _subprocess_util
from pathlib import Path


def emit_prepare(
    briefs_dir: Path,
    role: str,
    scope: str,
    round_n: int,
    prompt_text: str,
    model_tier: str,
    session_id: str,
) -> int:
    """Write brief and emit prepare JSON envelope.

    Writes the brief to briefs_dir/<role>-<scope>-r<round_n>.md and prints
    one JSON line with the brief path and metadata. Returns 0.
    """
    brief_path = _agent_dispatch.write_brief(briefs_dir, role, scope, round_n, prompt_text)
    envelope = {
        "stage": "prepare",
        "brief_path": str(brief_path.resolve()),
        "subagent_type": "mill-implementer",
        "model": model_tier,
        "session_id": session_id,
        "role": role,
        "scope": scope,
        "round": round_n,
    }
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
        "subagent_type": "mill-implementer",
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
    )


def _forward_output(
    output: str,
    project_root: Path,
    *,
    start_sha: str | None = None,
    snapshot_path: Path | None = None,
    session_id: str | None = None,
) -> int:
    """Extract the last JSON object containing a 'status' key from output using regex.

    Returns 0 in both success and fallback cases — the JSON on stdout is how the caller reads state.
    When no valid JSON is found, emits a stuck/logic sentinel.
    When the inferred-success fallback fires, the emitted JSON uses ``session_id`` if supplied,
    falling back to the literal ``"unknown"`` for backwards compatibility with callers that don't pass it.
    """
    matches = re.findall(r'\{[^{}]*"status"[^{}]*\}', output)
    if matches:
        last = matches[-1]
        try:
            parsed = json.loads(last)
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
                print(last)
            return 0
        except json.JSONDecodeError:
            pass
    try:
        if start_sha is not None and snapshot_path is not None and snapshot_path.exists():
            new_dirt = _cleanliness.compute_new_dirt(project_root, snapshot_path)
            if new_dirt == []:
                result = _subprocess_util.run(["git", "rev-parse", "HEAD"], cwd=project_root)
                if result.returncode == 0 and result.stdout.strip() != start_sha:
                    head = result.stdout.strip()
                    result_full = _subprocess_util.run(
                        ["git", "-C", str(project_root), "status", "--porcelain", "--untracked-files=no"],
                        check=True,
                    )
                    if result_full.stdout.strip():
                        print(json.dumps({"status": "stuck", "stuck_type": "logic", "reason": "inferred success but working tree dirty -- implementer likely skipped git-commit on modified files"}))
                        return 0
                    violations = _cleanliness.compute_scope_violations(project_root)
                    if violations:
                        print(json.dumps({"status": "stuck", "stuck_type": "logic", "reason": f"untracked files outside scope: {violations}", "scope_violations": violations, "inferred": True}))
                    else:
                        print(json.dumps({"status": "success", "commit_sha": head, "session_id": session_id or "unknown", "inferred": True}))
                    return 0
        elif start_sha is not None and snapshot_path is None:
            result = _subprocess_util.run(["git", "rev-parse", "HEAD"], cwd=project_root)
            if result.returncode == 0 and result.stdout.strip() != start_sha:
                head = result.stdout.strip()
                result_full = _subprocess_util.run(
                    ["git", "-C", str(project_root), "status", "--porcelain", "--untracked-files=no"],
                    check=True,
                )
                if not result_full.stdout.strip():
                    print(json.dumps({"status": "success", "commit_sha": head, "session_id": session_id or "unknown", "inferred": True}))
                    return 0
    except Exception:
        pass
    violations = _cleanliness.compute_scope_violations(project_root)
    result = {"status": "stuck", "stuck_type": "logic", "reason": "no structured report"}
    if violations:
        result["scope_violations"] = violations
    print(json.dumps(result))
    return 0
