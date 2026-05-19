"""Shared helpers for millpy-implement.py and millpy-fix.py."""
import json
import re
import _cleanliness
import _subprocess_util
from pathlib import Path


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
                    print(json.dumps({"status": "success", "commit_sha": head, "session_id": session_id or "unknown", "inferred": True}))
                    return 0
    except Exception:
        pass
    print(json.dumps({"status": "stuck", "stuck_type": "logic", "reason": "no structured report"}))
    return 0
