"""Unit tests for plugins/mill/scripts/_agent_dispatch.py.

Covers:
  - resolve_dispatch_mode: defaults to subprocess, validates enum values
  - model_to_tier: maps model families, raises on unknown
  - write_brief: writes files, creates parents, overwrites, returns path
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS_DIR = HUB / "plugins" / "mill" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import _agent_dispatch  # noqa: E402


def test_resolve_dispatch_mode_defaults_to_subprocess() -> None:
    """resolve_dispatch_mode defaults to subprocess when dispatch is absent."""
    cfg = {"llm": {"claude": {}}}
    mode = _agent_dispatch.resolve_dispatch_mode(cfg)
    assert mode == "subprocess", f"Expected subprocess, got {mode!r}"
    print("PASS resolve_dispatch_mode -- defaults to subprocess")


def test_resolve_dispatch_mode_returns_configured_value() -> None:
    """resolve_dispatch_mode returns the configured dispatch value."""
    for value in ("subprocess", "psmux", "agent"):
        cfg = {"llm": {"claude": {"dispatch": value}}}
        mode = _agent_dispatch.resolve_dispatch_mode(cfg)
        assert mode == value, f"Expected {value!r}, got {mode!r}"
    print("PASS resolve_dispatch_mode -- returns configured value")


def test_resolve_dispatch_mode_raises_on_unknown() -> None:
    """resolve_dispatch_mode raises ValueError on unknown dispatch value."""
    cfg = {"llm": {"claude": {"dispatch": "unknown"}}}
    try:
        _agent_dispatch.resolve_dispatch_mode(cfg)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "unknown" in str(e).lower(), f"Error message should mention unknown: {e!r}"
    print("PASS resolve_dispatch_mode -- raises on unknown value")


def test_model_to_tier_sonnet() -> None:
    """model_to_tier maps claude-sonnet-* to sonnet."""
    for model in ("claude-sonnet-4-6", "claude-sonnet-4-5", "claude-sonnet"):
        tier = _agent_dispatch.model_to_tier(model)
        assert tier == "sonnet", f"Expected sonnet for {model!r}, got {tier!r}"
    print("PASS model_to_tier -- maps sonnet family")


def test_model_to_tier_opus() -> None:
    """model_to_tier maps claude-opus-* to opus."""
    for model in ("claude-opus-4-8", "claude-opus-4-1", "claude-opus"):
        tier = _agent_dispatch.model_to_tier(model)
        assert tier == "opus", f"Expected opus for {model!r}, got {tier!r}"
    print("PASS model_to_tier -- maps opus family")


def test_model_to_tier_haiku() -> None:
    """model_to_tier maps claude-haiku-* to haiku."""
    for model in ("claude-haiku-4-5", "claude-haiku-3-5", "claude-haiku"):
        tier = _agent_dispatch.model_to_tier(model)
        assert tier == "haiku", f"Expected haiku for {model!r}, got {tier!r}"
    print("PASS model_to_tier -- maps haiku family")


def test_model_to_tier_raises_on_unknown() -> None:
    """model_to_tier raises ValueError on unrecognized model."""
    try:
        _agent_dispatch.model_to_tier("unknown-model-5-0")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "unknown" in str(e).lower(), f"Error message should mention unknown: {e!r}"
    print("PASS model_to_tier -- raises on unknown model")


def test_write_brief_creates_file() -> None:
    """write_brief creates a file with correct content and path."""
    with tempfile.TemporaryDirectory() as tmp:
        briefs_dir = Path(tmp) / "briefs"
        prompt = "Test prompt content"
        path = _agent_dispatch.write_brief(briefs_dir, "test-role", "code-review", 1, prompt)

        assert path == briefs_dir / "test-role-code-review-r1.md"
        assert path.exists(), "File should exist"
        assert path.read_text(encoding="utf-8") == prompt, "Content should match"
    print("PASS write_brief -- creates file with correct content")


def test_write_brief_creates_parent_dirs() -> None:
    """write_brief creates parent directories if they don't exist."""
    with tempfile.TemporaryDirectory() as tmp:
        briefs_dir = Path(tmp) / "deep" / "nested" / "path" / "briefs"
        prompt = "Test"
        path = _agent_dispatch.write_brief(briefs_dir, "role", "scope", 2, prompt)

        assert briefs_dir.exists(), "Parent directories should be created"
        assert path.exists(), "File should exist"
    print("PASS write_brief -- creates parent directories")


def test_write_brief_overwrites_existing_file() -> None:
    """write_brief overwrites an existing file."""
    with tempfile.TemporaryDirectory() as tmp:
        briefs_dir = Path(tmp) / "briefs"
        path1 = _agent_dispatch.write_brief(briefs_dir, "role", "scope", 1, "old content")
        path2 = _agent_dispatch.write_brief(briefs_dir, "role", "scope", 1, "new content")

        assert path1 == path2, "Same path should be returned"
        assert path2.read_text(encoding="utf-8") == "new content", "Content should be updated"
    print("PASS write_brief -- overwrites existing file")


def test_write_brief_returns_path() -> None:
    """write_brief returns the Path object."""
    with tempfile.TemporaryDirectory() as tmp:
        briefs_dir = Path(tmp)
        result = _agent_dispatch.write_brief(briefs_dir, "impl", "test", 5, "content")

        assert isinstance(result, Path), f"Should return Path, got {type(result)!r}"
        assert result.name == "impl-test-r5.md", f"Path name should match format, got {result.name!r}"
    print("PASS write_brief -- returns correct Path")


def test_subagent_constants() -> None:
    """SUBAGENT_* constants are defined correctly."""
    assert _agent_dispatch.SUBAGENT_REVIEWER == "mill:mill-reviewer"
    assert _agent_dispatch.SUBAGENT_IMPLEMENTER == "mill:mill-implementer"
    print("PASS subagent constants")


def main() -> int:
    tests = [
        test_resolve_dispatch_mode_defaults_to_subprocess,
        test_resolve_dispatch_mode_returns_configured_value,
        test_resolve_dispatch_mode_raises_on_unknown,
        test_model_to_tier_sonnet,
        test_model_to_tier_opus,
        test_model_to_tier_haiku,
        test_model_to_tier_raises_on_unknown,
        test_write_brief_creates_file,
        test_write_brief_creates_parent_dirs,
        test_write_brief_overwrites_existing_file,
        test_write_brief_returns_path,
        test_subagent_constants,
    ]
    failures: list[str] = []
    for fn in tests:
        try:
            fn()
        except AssertionError as exc:
            print(f"FAIL [{fn.__name__}]: {exc}", file=sys.stderr)
            failures.append(fn.__name__)
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR [{fn.__name__}]: {exc}", file=sys.stderr)
            failures.append(fn.__name__)
    if failures:
        print(f"\n{len(failures)} test(s) failed: {failures}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
