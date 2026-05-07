"""Shared helpers for millpy-implement.py and millpy-implement-holistic.py."""
import json
import re
import subprocess
from pathlib import Path


def _forward_output(output: str, project_root: Path) -> int:
    """Extract the last JSON object containing a 'status' key from output using regex.

    Returns 0 in both success and fallback cases — the JSON on stdout is how the caller reads state.
    When no valid JSON is found, emits a stuck/logic sentinel.
    """
    matches = re.findall(r'\{[^{}]*"status"[^{}]*\}', output)
    if matches:
        last = matches[-1]
        try:
            parsed = json.loads(last)
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
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
    print(json.dumps({"status": "stuck", "stuck_type": "logic", "reason": "no structured report"}))
    return 0
