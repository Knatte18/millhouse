"""End-to-end integration test for millpy-claude-sub.py against real psmux + claude.

Local-dev only. Requires psmux, claude, and pwsh in PATH. Skips gracefully if any are missing.

Run from hub root:
    python plugins/mill/integration_tests/test-claude-psmux.py
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS = HUB / "plugins" / "mill" / "scripts"
SCRATCH = HUB / ".scratch"
sys.path.insert(0, str(SCRIPTS))

import _psmux  # noqa: E402


def _check_prerequisites() -> bool:
    """Check if psmux and claude are available. Print skip message if not."""
    missing = []
    if shutil.which("psmux") is None:
        missing.append("psmux")
    if shutil.which("claude") is None:
        missing.append("claude")

    if missing:
        print(f"[skip] missing prerequisites: {', '.join(missing)}", file=sys.stderr)
        return False
    return True


def _assert_cleanup() -> None:
    """Verify no mill-* psmux sessions remain and no wrapper prompt files in SCRATCH."""
    # Check for leftover psmux sessions
    try:
        sessions = _psmux.list_sessions()
        mill_sessions = [s for s in sessions if s.startswith("mill-")]
        if mill_sessions:
            raise AssertionError(f"cleanup failed: leftover psmux sessions {mill_sessions}")
    except _psmux.PsmuxError as exc:
        raise AssertionError(f"failed to list psmux sessions: {exc}") from exc

    # Check for leftover prompt files
    if SCRATCH.exists():
        leftover = list(SCRATCH.glob("wrapper-*-prompt.txt"))
        if leftover:
            raise AssertionError(f"cleanup failed: leftover prompt files {leftover}")


def test_bulk() -> int:
    """Test bulk mode: claude without any tools."""
    prompt = "Reply with the single word PONG and nothing else."
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "millpy-claude-sub.py"),
                "--mode", "bulk",
                "--model", "claude-sonnet-4-6",
            ],
            input=prompt,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=400,
        )

        # Assertion: returncode must be 0
        if result.returncode != 0:
            raise AssertionError(
                f"bulk mode exited with code {result.returncode}\n"
                f"stderr: {result.stderr}"
            )

        # Assertion: response must contain PONG
        if "PONG" not in result.stdout:
            raise AssertionError(f"response does not contain PONG:\n{result.stdout}")

        # Assertion: no marker tokens in stdout (markers are stripped by wrapper)
        if "MILL_BEGIN_" in result.stdout or "MILL_END_" in result.stdout:
            raise AssertionError(f"response contains marker tokens:\n{result.stdout}")

        # Parse JSON envelope from last non-empty line of stderr
        stderr_lines = [line for line in result.stderr.splitlines() if line.strip()]
        if not stderr_lines:
            raise AssertionError("no JSON envelope in stderr")

        last_line = stderr_lines[-1]
        try:
            envelope = json.loads(last_line)
        except json.JSONDecodeError as exc:
            raise AssertionError(f"stderr last line is not valid JSON: {last_line}") from exc

        # Assertion: envelope must have session_id, duration_s, mode
        for key in ["session_id", "duration_s", "mode"]:
            if key not in envelope:
                raise AssertionError(f"envelope missing key '{key}': {envelope}")

        # Assertion: mode must be "bulk"
        if envelope["mode"] != "bulk":
            raise AssertionError(f"envelope mode is {envelope['mode']}, expected bulk")

        # Cleanup assertion
        _assert_cleanup()
        return 0

    except Exception as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1 if isinstance(exc, AssertionError) else 1


def test_tool_use() -> int:
    """Test tool-use mode: claude with Read, Grep, Glob tools."""
    prompt = "List the names of the files in the current directory using the Glob tool, then briefly summarise."
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "millpy-claude-sub.py"),
                "--mode", "tool-use",
                "--model", "claude-sonnet-4-6",
            ],
            input=prompt,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=700,
        )

        # Assertion: returncode must be 0
        if result.returncode != 0:
            raise AssertionError(
                f"tool-use mode exited with code {result.returncode}\n"
                f"stderr: {result.stderr}"
            )

        # Assertion: response must be non-empty
        if not result.stdout.strip():
            raise AssertionError("tool-use response is empty")

        # Assertion: response must mention at least one file in HUB (e.g., "plugins")
        if "plugins" not in result.stdout:
            raise AssertionError(
                f"response does not mention expected files from hub:\n{result.stdout}"
            )

        # Parse JSON envelope from last non-empty line of stderr
        stderr_lines = [line for line in result.stderr.splitlines() if line.strip()]
        if not stderr_lines:
            raise AssertionError("no JSON envelope in stderr")

        last_line = stderr_lines[-1]
        try:
            envelope = json.loads(last_line)
        except json.JSONDecodeError as exc:
            raise AssertionError(f"stderr last line is not valid JSON: {last_line}") from exc

        # Assertion: envelope must have session_id, duration_s, mode
        for key in ["session_id", "duration_s", "mode"]:
            if key not in envelope:
                raise AssertionError(f"envelope missing key '{key}': {envelope}")

        # Assertion: mode must be "tool-use"
        if envelope["mode"] != "tool-use":
            raise AssertionError(f"envelope mode is {envelope['mode']}, expected tool-use")

        # Cleanup assertion
        _assert_cleanup()
        return 0

    except Exception as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1 if isinstance(exc, AssertionError) else 1


def test_implementer() -> int:
    """Test implementer mode: claude with all tools including Bash.

    This also serves as the regression guard for --allowedTools pre-grant semantics.
    A future Claude CLI version that re-introduces per-Bash permission prompts will
    time out here.
    """
    prompt = "Use the Bash tool to run exactly: echo __INTEGRATION_OK__"
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "millpy-claude-sub.py"),
                "--mode", "implementer",
                "--model", "claude-sonnet-4-6",
            ],
            input=prompt,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=1900,
        )

        # Assertion: returncode must be 0
        if result.returncode != 0:
            raise AssertionError(
                f"implementer mode exited with code {result.returncode}\n"
                f"stderr: {result.stderr}"
            )

        # Assertion: response must contain the sentinel
        if "__INTEGRATION_OK__" not in result.stdout:
            raise AssertionError(
                f"response does not contain __INTEGRATION_OK__:\n{result.stdout}"
            )

        # Parse JSON envelope from last non-empty line of stderr
        stderr_lines = [line for line in result.stderr.splitlines() if line.strip()]
        if not stderr_lines:
            raise AssertionError("no JSON envelope in stderr")

        last_line = stderr_lines[-1]
        try:
            envelope = json.loads(last_line)
        except json.JSONDecodeError as exc:
            raise AssertionError(f"stderr last line is not valid JSON: {last_line}") from exc

        # Assertion: envelope must have session_id, duration_s, mode
        for key in ["session_id", "duration_s", "mode"]:
            if key not in envelope:
                raise AssertionError(f"envelope missing key '{key}': {envelope}")

        # Assertion: mode must be "implementer"
        if envelope["mode"] != "implementer":
            raise AssertionError(f"envelope mode is {envelope['mode']}, expected implementer")

        # Cleanup assertion
        _assert_cleanup()
        return 0

    except Exception as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1 if isinstance(exc, AssertionError) else 1


def test_keep_alive_reuse() -> int:
    """Test keep-alive reuse: run with --keep-alive, then reuse the session."""
    try:
        # First call: run with --keep-alive
        result1 = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "millpy-claude-sub.py"),
                "--mode", "bulk",
                "--model", "claude-sonnet-4-6",
                "--psmux-session", "mill-test-reuse",
                "--keep-alive",
            ],
            input="Reply with the single word FIRST and nothing else.",
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=400,
        )

        # Assertion: first call returncode must be 0
        if result1.returncode != 0:
            raise AssertionError(
                f"first call exited with code {result1.returncode}\n"
                f"stderr: {result1.stderr}"
            )

        # Assertion: response must contain FIRST
        if "FIRST" not in result1.stdout:
            raise AssertionError(f"first response does not contain FIRST:\n{result1.stdout}")

        # Second call: reuse the session without --keep-alive
        result2 = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "millpy-claude-sub.py"),
                "--mode", "bulk",
                "--model", "claude-sonnet-4-6",
                "--psmux-session", "mill-test-reuse",
            ],
            input="Reply with the single word SECOND and nothing else.",
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=400,
        )

        # Assertion: second call returncode must be 0
        if result2.returncode != 0:
            raise AssertionError(
                f"second call exited with code {result2.returncode}\n"
                f"stderr: {result2.stderr}"
            )

        # Assertion: second response must contain SECOND
        if "SECOND" not in result2.stdout:
            raise AssertionError(f"second response does not contain SECOND:\n{result2.stdout}")

        # Assertion: FIRST must NOT appear in second response (no bleed-through)
        if "FIRST" in result2.stdout:
            raise AssertionError(
                f"second response contains FIRST (auto-suggest bleed-through):\n{result2.stdout}"
            )

        # Cleanup assertion
        _assert_cleanup()
        return 0

    except Exception as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1 if isinstance(exc, AssertionError) else 1


def main() -> int:
    """Run all tests and report results."""
    # Check prerequisites
    if not _check_prerequisites():
        return 0

    tests = [
        ("test_bulk", test_bulk),
        ("test_tool_use", test_tool_use),
        ("test_implementer", test_implementer),
        ("test_keep_alive_reuse", test_keep_alive_reuse),
    ]

    failures = []
    for name, test_fn in tests:
        try:
            rc = test_fn()
            if rc == 0:
                print(f"[OK] {name}", file=sys.stderr)
            else:
                print(f"[FAIL] {name}: test returned non-zero", file=sys.stderr)
                failures.append(name)
        except Exception as exc:
            print(f"[FAIL] {name}: {type(exc).__name__}: {exc}", file=sys.stderr)
            failures.append(name)

    if not failures:
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
