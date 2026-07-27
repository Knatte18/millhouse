"""Unit tests for plugins/mill/scripts/_agent_dispatch.py.

Covers:
  - resolve_dispatch_mode: defaults to agent, validates enum values
  - model_to_tier: maps model families, raises on unknown
  - write_brief: writes files, creates parents, overwrites, returns path
  - output_path_for: the ".md" -> ".out.md" mapping
  - write_brief output_contract footer, default-off byte-identity, and
    unconditional stale-".out.md" truncation
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS_DIR = HUB / "plugins" / "mill" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import _agent_dispatch  # noqa: E402


def test_resolve_dispatch_mode_defaults_to_agent() -> None:
    """resolve_dispatch_mode defaults to agent when dispatch is absent."""
    cfg = {"llm": {"claude": {}}}
    mode = _agent_dispatch.resolve_dispatch_mode(cfg)
    assert mode == "agent", f"Expected agent, got {mode!r}"
    print("PASS resolve_dispatch_mode -- defaults to agent")


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


def test_resolve_subagent_type_returns_base_when_effort_none() -> None:
    """resolve_subagent_type returns base unchanged when effort is None."""
    assert _agent_dispatch.resolve_subagent_type(_agent_dispatch.SUBAGENT_REVIEWER, None) == "mill:mill-reviewer"
    assert _agent_dispatch.resolve_subagent_type(_agent_dispatch.SUBAGENT_IMPLEMENTER, None) == "mill:mill-implementer"
    print("PASS resolve_subagent_type -- returns base when effort is None")


def test_resolve_subagent_type_appends_known_tier() -> None:
    """resolve_subagent_type appends a recognized effort tier as a suffix."""
    for tier in ("low", "medium", "high", "xhigh", "max"):
        assert _agent_dispatch.resolve_subagent_type(_agent_dispatch.SUBAGENT_REVIEWER, tier) == f"mill:mill-reviewer-{tier}"
        assert _agent_dispatch.resolve_subagent_type(_agent_dispatch.SUBAGENT_IMPLEMENTER, tier) == f"mill:mill-implementer-{tier}"
    print("PASS resolve_subagent_type -- appends known tier")


def test_resolve_subagent_type_falls_back_on_unrecognized_tier() -> None:
    """resolve_subagent_type falls back to base for an unrecognized effort tier."""
    for tier in ("ultra", "bogus"):
        assert _agent_dispatch.resolve_subagent_type(_agent_dispatch.SUBAGENT_REVIEWER, tier) == "mill:mill-reviewer"
    print("PASS resolve_subagent_type -- falls back to base on unrecognized tier")


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


def test_write_brief_sanitizes_colon_in_scope() -> None:
    """write_brief sanitizes colon in scope and creates a real file."""
    with tempfile.TemporaryDirectory() as tmp:
        briefs_dir = Path(tmp) / "briefs"
        scope = "Core fix: emit_prepare"
        prompt = "Test prompt"
        path = _agent_dispatch.write_brief(briefs_dir, "implement", scope, 1, prompt)

        # Filename should not contain colon
        assert ":" not in path.name, f"Filename should not contain colon: {path.name!r}"
        # File should exist and be readable
        assert path.exists(), f"File should exist at {path}"
        content = path.read_text(encoding="utf-8")
        assert content == prompt, "Content should match"
    print("PASS write_brief -- sanitizes colon in scope")


def test_write_brief_sanitizes_slash_in_scope() -> None:
    """write_brief sanitizes slash in scope and creates a flat file."""
    with tempfile.TemporaryDirectory() as tmp:
        briefs_dir = Path(tmp) / "briefs"
        scope = "internal/lock - x"
        prompt = "Test prompt"
        path = _agent_dispatch.write_brief(briefs_dir, "implement", scope, 1, prompt)

        # Should create a single flat file directly under briefs_dir, no nested directories
        assert path.parent == briefs_dir, f"File should be directly under briefs_dir, got {path.parent}"
        # Filename should not contain forward slash (no nested dirs created)
        assert "/" not in path.name, f"Filename should not contain slash: {path.name!r}"
        # File should exist and be readable
        assert path.exists(), f"File should exist at {path}"
        content = path.read_text(encoding="utf-8")
        assert content == prompt, "Content should match"
    print("PASS write_brief -- sanitizes slash in scope")


def test_output_path_for_maps_md_to_out_md() -> None:
    """output_path_for maps foo-r1.md -> foo-r1.out.md, preserving parent and absoluteness."""
    with tempfile.TemporaryDirectory() as tmp:
        # Path(tmp) is guaranteed absolute on both POSIX and Windows (unlike a
        # hand-written "/abs/..." literal, which pathlib treats as relative --
        # drive-less -- on Windows).
        brief_path = Path(tmp) / "briefs" / "foo-r1.md"
        out_path = _agent_dispatch.output_path_for(brief_path)

        assert out_path.name == "foo-r1.out.md", f"Expected foo-r1.out.md, got {out_path.name!r}"
        assert out_path.parent == brief_path.parent, (
            f"Parent directory should be preserved: {out_path.parent} != {brief_path.parent}"
        )
        assert brief_path.is_absolute(), f"Test setup: brief_path must be absolute, got {brief_path}"
        assert out_path.is_absolute(), f"Expected absolute path, got {out_path}"
    print("PASS output_path_for -- maps .md to .out.md, preserves parent and absoluteness")


def test_write_brief_footer_present_when_output_contract_true() -> None:
    """write_brief appends a footer naming the .out.md path and a WROTE ack when output_contract=True."""
    with tempfile.TemporaryDirectory() as tmp:
        briefs_dir = Path(tmp) / "briefs"
        prompt = "Test prompt content"
        brief_path = _agent_dispatch.write_brief(
            briefs_dir, "review-code", "holistic", 1, prompt, output_contract=True
        )
        content = brief_path.read_text(encoding="utf-8")
        out_path = _agent_dispatch.output_path_for(brief_path)

        assert content.startswith(prompt), "Written content must start with prompt_text"
        assert str(out_path) in content, (
            f"Footer must contain the literal absolute output path {out_path}: {content!r}"
        )
        assert "WROTE" in content, f"Footer must instruct a WROTE ack: {content!r}"
    print("PASS write_brief -- footer present with literal path and WROTE ack when output_contract=True")


def test_write_brief_default_off_is_byte_identical_to_prompt() -> None:
    """write_brief without output_contract writes content exactly equal to prompt_text (the descope guarantee)."""
    with tempfile.TemporaryDirectory() as tmp:
        briefs_dir = Path(tmp) / "briefs"
        prompt = "Test prompt content, unchanged."
        brief_path = _agent_dispatch.write_brief(briefs_dir, "review-code", "holistic", 1, prompt)
        content = brief_path.read_text(encoding="utf-8")

        assert content == prompt, (
            f"Default-off write_brief must write prompt_text byte-for-byte, got {content!r}"
        )
    print("PASS write_brief -- default-off content is byte-identical to prompt_text")


def test_write_brief_truncates_stale_out_md() -> None:
    """write_brief unconditionally unlinks a stale .out.md, for both output_contract states."""
    for output_contract in (True, False):
        with tempfile.TemporaryDirectory() as tmp:
            briefs_dir = Path(tmp) / "briefs"
            role, scope, round_n = "review-code", "holistic", 1

            # Pre-create the brief once to learn its path, then plant a stale
            # .out.md next to it as if a prior round's reviewer had run.
            first_brief_path = _agent_dispatch.write_brief(
                briefs_dir, role, scope, round_n, "first prompt"
            )
            stale_out_path = _agent_dispatch.output_path_for(first_brief_path)
            stale_out_path.write_text("verdict: APPROVE", encoding="utf-8")
            assert stale_out_path.exists(), "Test setup: stale .out.md must exist before re-dispatch"

            # Re-dispatch the same role/scope/round, as a transient-retry would.
            _agent_dispatch.write_brief(
                briefs_dir, role, scope, round_n, "second prompt", output_contract=output_contract
            )

            assert not stale_out_path.exists(), (
                f"Stale .out.md must be unlinked (output_contract={output_contract}): {stale_out_path}"
            )
    print("PASS write_brief -- unconditionally truncates stale .out.md for both output_contract states")


def main() -> int:
    tests = [
        test_resolve_dispatch_mode_defaults_to_agent,
        test_resolve_dispatch_mode_returns_configured_value,
        test_resolve_dispatch_mode_raises_on_unknown,
        test_model_to_tier_sonnet,
        test_model_to_tier_opus,
        test_model_to_tier_haiku,
        test_model_to_tier_raises_on_unknown,
        test_resolve_subagent_type_returns_base_when_effort_none,
        test_resolve_subagent_type_appends_known_tier,
        test_resolve_subagent_type_falls_back_on_unrecognized_tier,
        test_write_brief_creates_file,
        test_write_brief_creates_parent_dirs,
        test_write_brief_overwrites_existing_file,
        test_write_brief_returns_path,
        test_subagent_constants,
        test_write_brief_sanitizes_colon_in_scope,
        test_write_brief_sanitizes_slash_in_scope,
        test_output_path_for_maps_md_to_out_md,
        test_write_brief_footer_present_when_output_contract_true,
        test_write_brief_default_off_is_byte_identical_to_prompt,
        test_write_brief_truncates_stale_out_md,
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
