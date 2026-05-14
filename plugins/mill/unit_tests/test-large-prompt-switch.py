"""Unit tests for maybe_switch_spec_for_large_prompt and validate_role_refs (large_prompt extension)."""
from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _review_common import maybe_switch_spec_for_large_prompt  # noqa: E402
from _reviewers import ReviewerError, validate_role_refs  # noqa: E402
from _test_cfg import make_minimal_cfg  # noqa: E402
from _test_registry import make_minimal_registry  # noqa: E402


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _make_cfg_with_large_prompt(
    role="code-review",
    scope="holistic",
    threshold_ktok=1,
    reviewer="override-reviewer",
) -> dict:
    cfg = make_minimal_cfg()
    cfg["roles"][role][scope]["large_prompt"] = {
        "threshold_ktok": threshold_ktok,
        "reviewer": reviewer,
    }
    return cfg


def _make_registry_with_cluster() -> dict:
    registry = make_minimal_registry()
    registry["worker_single"] = {
        "type": "single",
        "provider": "claude",
        "model": "claude-sonnet-4-6",
    }
    registry["my_cluster"] = {
        "type": "cluster",
        "workers": {"use": "worker_single", "count": 3},
        "handler": {"use": "worker_single"},
    }
    return registry


def _override_spec() -> dict:
    return {
        "type": "single",
        "provider": "claude",
        "model": "claude-opus-4-7",
        "effort": "max",
        "tooluse": False,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_below_threshold_no_switch() -> None:
    registry = make_minimal_registry()
    registry["override-reviewer"] = _override_spec()
    cfg = _make_cfg_with_large_prompt(threshold_ktok=1)
    original_spec = {"type": "single", "provider": "claude", "model": "claude-sonnet-4-6", "tooluse": False}
    prompt = "x" * 3999
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        result_spec, result_name = maybe_switch_spec_for_large_prompt(
            prompt, original_spec, "sonnetmax", cfg, "code-review", "holistic", registry
        )
    assert result_spec is original_spec
    assert result_name == "sonnetmax"
    assert buf.getvalue() == ""
    print("PASS: below threshold no switch")


def test_above_threshold_switches() -> None:
    registry = make_minimal_registry()
    registry["override-reviewer"] = _override_spec()
    cfg = _make_cfg_with_large_prompt(threshold_ktok=1)
    original_spec = {"type": "single", "provider": "claude", "model": "claude-sonnet-4-6", "tooluse": False}
    prompt = "x" * 4000
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        result_spec, result_name = maybe_switch_spec_for_large_prompt(
            prompt, original_spec, "sonnetmax", cfg, "code-review", "holistic", registry
        )
    assert result_name == "override-reviewer"
    assert result_spec["model"] == "claude-opus-4-7"
    stderr = buf.getvalue()
    assert "large-prompt switch" in stderr
    assert "sonnetmax" in stderr
    assert "override-reviewer" in stderr
    print("PASS: above threshold switches reviewer")


def test_no_large_prompt_config_noop() -> None:
    cfg = make_minimal_cfg()
    registry = make_minimal_registry()
    original_spec = {"type": "single", "provider": "claude", "model": "claude-sonnet-4-6", "tooluse": False}
    prompt = "x" * 100_000
    result_spec, result_name = maybe_switch_spec_for_large_prompt(
        prompt, original_spec, "sonnetmax", cfg, "code-review", "holistic", registry
    )
    assert result_spec is original_spec
    assert result_name == "sonnetmax"
    print("PASS: no large_prompt config is noop")


def test_null_reviewer_noop() -> None:
    cfg = _make_cfg_with_large_prompt(threshold_ktok=1, reviewer=None)
    registry = make_minimal_registry()
    original_spec = {"type": "single", "provider": "claude", "model": "claude-sonnet-4-6", "tooluse": False}
    prompt = "x" * 4000
    result_spec, result_name = maybe_switch_spec_for_large_prompt(
        prompt, original_spec, "sonnetmax", cfg, "code-review", "holistic", registry
    )
    assert result_spec is original_spec
    assert result_name == "sonnetmax"
    print("PASS: null reviewer is noop")


def test_tooluse_coercion_original_true_override_false() -> None:
    registry = make_minimal_registry()
    registry["override-reviewer"] = _override_spec()  # tooluse=False
    cfg = _make_cfg_with_large_prompt(threshold_ktok=1)
    original_spec = {
        "type": "single",
        "provider": "claude",
        "model": "claude-sonnet-4-6",
        "tooluse": True,
    }
    prompt = "x" * 4000
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        result_spec, result_name = maybe_switch_spec_for_large_prompt(
            prompt, original_spec, "sonnetmax", cfg, "code-review", "holistic", registry
        )
    assert result_spec["tooluse"] is True
    assert result_name == "override-reviewer"
    assert "tooluse differs" in buf.getvalue()
    print("PASS: tooluse coercion preserves original tooluse=True")


def test_tooluse_matching_no_notice() -> None:
    registry = make_minimal_registry()
    registry["override-reviewer"] = _override_spec()  # tooluse=False
    cfg = _make_cfg_with_large_prompt(threshold_ktok=1)
    original_spec = {
        "type": "single",
        "provider": "claude",
        "model": "claude-sonnet-4-6",
        "tooluse": False,
    }
    prompt = "x" * 4000
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        result_spec, result_name = maybe_switch_spec_for_large_prompt(
            prompt, original_spec, "sonnetmax", cfg, "code-review", "holistic", registry
        )
    stderr = buf.getvalue()
    assert result_spec["tooluse"] is False
    assert "tooluse differs" not in stderr
    assert "large-prompt switch" in stderr
    print("PASS: matching tooluse produces no notice")


def test_validate_role_refs_bad_large_prompt_reviewer() -> None:
    cfg = make_minimal_cfg()
    cfg["roles"]["code-review"]["holistic"]["large_prompt"] = {
        "threshold_ktok": 100,
        "reviewer": "nonexistent-override",
    }
    registry = make_minimal_registry()
    try:
        validate_role_refs(cfg, registry)
        raise AssertionError("Expected ReviewerError")
    except ReviewerError as exc:
        msg = str(exc)
        assert "nonexistent-override" in msg
        assert "large_prompt" in msg
    print("PASS: validate_role_refs raises on bad large_prompt reviewer")


def test_validate_role_refs_cluster_large_prompt_reviewer() -> None:
    cfg = make_minimal_cfg()
    cfg["roles"]["code-review"]["holistic"]["large_prompt"] = {
        "threshold_ktok": 100,
        "reviewer": "my_cluster",
    }
    registry = _make_registry_with_cluster()
    try:
        validate_role_refs(cfg, registry)
        raise AssertionError("Expected ReviewerError")
    except ReviewerError as exc:
        msg = str(exc)
        assert "my_cluster" in msg
        assert "cluster" in msg.lower()
    print("PASS: validate_role_refs raises on cluster large_prompt reviewer")


def main() -> int:
    tests = [
        test_below_threshold_no_switch,
        test_above_threshold_switches,
        test_no_large_prompt_config_noop,
        test_null_reviewer_noop,
        test_tooluse_coercion_original_true_override_false,
        test_tooluse_matching_no_notice,
        test_validate_role_refs_bad_large_prompt_reviewer,
        test_validate_role_refs_cluster_large_prompt_reviewer,
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
