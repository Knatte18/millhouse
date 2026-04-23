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
        print("PASS: _reviewer_sonnetmax MODE + callable")

        assert _reviewer_sonnetmax_tool.MODE == "tool-use"
        assert callable(_reviewer_sonnetmax_tool.run)
        print("PASS: _reviewer_sonnetmax_tool MODE + callable")

        print("All reviewer-module unit tests passed.")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
