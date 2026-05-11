"""Unit tests for _reviewer_single.run."""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))
sys.path.insert(0, str(HUB / "plugins" / "mill" / "unit_tests"))

import _reviewer_single  # noqa: E402
import _reviewer_test_stub as stub  # noqa: E402
from _reviewers import ReviewerError  # noqa: E402


def test_signature() -> None:
    """run has parameters spec, prompt_text, session_id, resume, timeout and no effort."""
    sig = inspect.signature(_reviewer_single.run)
    params = sig.parameters
    assert "spec" in params
    assert "prompt_text" in params
    assert "session_id" in params
    assert params["session_id"].default is None
    assert "resume" in params
    assert params["resume"].default is False
    assert "timeout" in params
    assert params["timeout"].default is None
    assert "effort" not in params, "run must not expose an effort kwarg — effort lives in the spec"
    print("PASS: _reviewer_single.run signature")


def test_cluster_spec_raises() -> None:
    """spec.type == 'cluster' raises ReviewerError."""
    cluster_spec = {
        "type": "cluster",
        "workers": {"use": "sonnetmax", "count": 3},
        "handler": {"use": "sonnetmax"},
    }
    try:
        _reviewer_single.run(cluster_spec, "prompt")
        raise AssertionError("Expected ReviewerError")
    except ReviewerError as exc:
        assert "cluster" in str(exc).lower()
    print("PASS: cluster spec raises ReviewerError")


def test_test_stub_forwards_prompt() -> None:
    """spec.provider == 'test_stub' forwards to _reviewer_test_stub.run."""
    stub.seed([("# Review\n\n```yaml\nverdict: APPROVE\n```\n", "sid-001")])
    spec = {"type": "single", "provider": "test_stub", "tooluse": False}
    text, session_id = _reviewer_single.run(spec, "hello prompt", session_id="sid-001")
    assert "APPROVE" in text
    captured = stub.captured_prompts()
    assert len(captured) == 1
    assert captured[0][0] == "hello prompt"
    print("PASS: test_stub provider forwards prompt and returns seeded response")


def test_claude_bulk_mode() -> None:
    """spec.provider == 'claude' with tooluse=False calls _llm_claude.run_bulk."""
    import _llm_claude as llm_claude

    calls: list[dict] = []

    def fake_run_bulk(prompt_text: str, **kwargs) -> tuple[str, str]:
        calls.append({"prompt_text": prompt_text, **kwargs})
        return ("bulk response", "sid-bulk")

    original = llm_claude.run_bulk
    llm_claude.run_bulk = fake_run_bulk
    try:
        spec = {
            "type": "single",
            "provider": "claude",
            "model": "claude-sonnet-4-6",
            "effort": "max",
            "tooluse": False,
        }
        text, sid = _reviewer_single.run(spec, "test prompt", session_id="abc")
        assert text == "bulk response"
        assert len(calls) == 1
        assert calls[0]["model"] == "claude-sonnet-4-6"
        assert calls[0]["effort"] == "max"
        assert "timeout" not in calls[0], "timeout must not be forwarded when None"
    finally:
        llm_claude.run_bulk = original

    print("PASS: claude bulk mode calls run_bulk with model and effort")


def test_claude_tool_use_mode() -> None:
    """spec.provider == 'claude' with tooluse=True calls _llm_claude.run_tool_use."""
    import _llm_claude as llm_claude

    calls: list[dict] = []

    def fake_run_tool_use(prompt_text: str, **kwargs) -> tuple[str, str]:
        calls.append({"prompt_text": prompt_text, **kwargs})
        return ("tool response", "sid-tool")

    original = llm_claude.run_tool_use
    llm_claude.run_tool_use = fake_run_tool_use
    try:
        spec = {
            "type": "single",
            "provider": "claude",
            "model": "claude-sonnet-4-6",
            "effort": "max",
            "tooluse": True,
        }
        text, sid = _reviewer_single.run(spec, "test prompt", timeout=300)
        assert text == "tool response"
        assert len(calls) == 1
        assert calls[0]["model"] == "claude-sonnet-4-6"
        assert calls[0]["effort"] == "max"
        assert calls[0].get("timeout") == 300
    finally:
        llm_claude.run_tool_use = original

    print("PASS: claude tool-use mode calls run_tool_use with model, effort, and timeout")


def test_gemini_bulk_mode() -> None:
    """spec.provider == 'gemini' with tooluse=False calls _llm_gemini.run_bulk."""
    import _llm_gemini as llm_gemini

    calls: list[dict] = []

    def fake_run_bulk(prompt_text: str, **kwargs) -> tuple[str, str]:
        calls.append({"prompt_text": prompt_text, **kwargs})
        return ("gemini bulk response", "sid-gemini-bulk")

    original = llm_gemini.run_bulk
    llm_gemini.run_bulk = fake_run_bulk
    try:
        spec = {
            "type": "single",
            "provider": "gemini",
            "model": "gemini-2.5-flash",
            "effort": None,
            "tooluse": False,
        }
        text, sid = _reviewer_single.run(spec, "test prompt", session_id="abc")
        assert text == "gemini bulk response"
        assert len(calls) == 1
        assert calls[0]["model"] == "gemini-2.5-flash"
    finally:
        llm_gemini.run_bulk = original

    print("PASS: gemini bulk mode calls run_bulk with model")


def test_unknown_provider_raises() -> None:
    """A truly unknown provider raises ReviewerError with 'Unknown provider' substring."""
    spec = {
        "type": "single",
        "provider": "unk_provider_xyz",
        "model": "some-model",
        "effort": "medium",
        "tooluse": False,
    }
    try:
        _reviewer_single.run(spec, "test prompt")
        raise AssertionError("Expected ReviewerError")
    except ReviewerError as exc:
        assert "Unknown provider" in str(exc)
        assert "unk_provider_xyz" in str(exc)
    print("PASS: unknown provider raises ReviewerError")


def main() -> int:
    tests = [
        test_signature,
        test_cluster_spec_raises,
        test_test_stub_forwards_prompt,
        test_claude_bulk_mode,
        test_claude_tool_use_mode,
        test_gemini_bulk_mode,
        test_unknown_provider_raises,
    ]
    failures = 0
    for test in tests:
        try:
            test()
        except Exception as exc:
            print(f"FAIL: {test.__name__}: {exc}", file=sys.stderr)
            failures += 1
    if failures:
        print(f"\n{failures} of {len(tests)} tests FAILED", file=sys.stderr)
        return 1
    print(f"\nAll {len(tests)} tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
