"""Unit tests for the MODE-typed reviewer/implementer wrapper modules.

Covers ``_implementer_sonnet``, ``_reviewer_sonnetmax``, and
``_reviewer_sonnetmax_tool``. Each exposes a module-level ``MODE``
constant and a callable ``run``. These tests check the declared shape
without invoking the live LLM.
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _implementer_sonnet  # noqa: E402
import _reviewer_sonnetmax  # noqa: E402
import _reviewer_sonnetmax_tool  # noqa: E402
import _reviewer_test_stub as stub  # noqa: E402


def main() -> int:
    try:
        assert _implementer_sonnet.MODE == "implementer"
        assert callable(_implementer_sonnet.run)
        sig = inspect.signature(_implementer_sonnet.run)
        assert "session_id" in sig.parameters
        assert "resume" in sig.parameters
        assert "cwd" in sig.parameters
        print("PASS: _implementer_sonnet MODE + signature")

        assert _reviewer_sonnetmax.MODE == "bulk"
        assert callable(_reviewer_sonnetmax.run)
        sig = inspect.signature(_reviewer_sonnetmax.run)
        assert "prompt_text" in sig.parameters
        assert "session_id" in sig.parameters
        assert sig.parameters["session_id"].default is None
        assert "resume" in sig.parameters
        assert sig.parameters["resume"].default is False
        assert "timeout" in sig.parameters, "timeout missing from _reviewer_sonnetmax.run"
        assert sig.parameters["timeout"].default is None, "_reviewer_sonnetmax timeout default should be None"
        assert str(sig.return_annotation) == "tuple[str, str]"
        print("PASS: _reviewer_sonnetmax signature with session_id/resume/timeout")

        assert _reviewer_sonnetmax_tool.MODE == "tool-use"
        assert callable(_reviewer_sonnetmax_tool.run)
        sig = inspect.signature(_reviewer_sonnetmax_tool.run)
        assert "prompt_text" in sig.parameters
        assert "session_id" in sig.parameters
        assert sig.parameters["session_id"].default is None
        assert "resume" in sig.parameters
        assert sig.parameters["resume"].default is False
        assert "timeout" in sig.parameters, "timeout missing from _reviewer_sonnetmax_tool.run"
        assert sig.parameters["timeout"].default is None, "_reviewer_sonnetmax_tool timeout default should be None"
        assert str(sig.return_annotation) == "tuple[str, str]"
        print("PASS: _reviewer_sonnetmax_tool signature with session_id/resume/timeout")

        # _reviewer_test_stub also exposes timeout
        sig_stub = inspect.signature(stub.run)
        assert "timeout" in sig_stub.parameters, "timeout missing from _reviewer_test_stub.run"
        assert sig_stub.parameters["timeout"].default is None, "stub timeout default should be None"
        print("PASS: _reviewer_test_stub.run exposes timeout kwarg with default None")

        # Calling stub with timeout=900 -> captured_prompts()[0][1]["timeout"] == 900
        stub.seed([("# Review\n\n```yaml\nverdict: APPROVE\n```\n", "sid-t")])
        stub.run("probe prompt", timeout=900)
        captured = stub.captured_prompts()
        assert len(captured) == 1, f"expected 1 captured prompt, got {len(captured)}"
        assert captured[0][1]["timeout"] == 900, (
            f"expected timeout=900 in kwargs, got {captured[0][1]!r}"
        )
        print("PASS: stub captures timeout=900 in kwargs dict")

        print("All reviewer-module unit tests passed.")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
