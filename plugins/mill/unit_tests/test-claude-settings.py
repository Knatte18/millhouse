"""Unit tests for plugins/mill/scripts/_claude_settings.py.

Covers:
  - merge_permission_allowlist: settings file absent -> created with permissions.allow containing
  exactly MILL_SUBAGENT_TOOLS
  - merge_permission_allowlist: pre-existing allow/deny/additionalDirectories block survives the
  merge, with new tool names appended and no existing entries removed, duplicated, or reordered
  - merge_permission_allowlist: calling twice in a row is idempotent -- same allow list both times,
  second call skips the write entirely
  - MILL_SUBAGENT_TOOLS: matches the union of mill-implementer.md's and mill-reviewer.md's tools:
  frontmatter, so the two can never drift
  - reconcile_destructive_denylist: retires target-blind rm -rf deny rules while leaving unrelated
  deny entries untouched
  - reconcile_destructive_denylist: settings file absent -> created with every DESTRUCTIVE_DENY
  entry present, no duplicates
  - reconcile_destructive_denylist: pre-existing unrelated deny entries, allow list,
  additionalDirectories, and env block survive the reconciliation unchanged
  - reconcile_destructive_denylist: calling twice in a row is idempotent -- same deny list both
  times, second call skips the write entirely
  - build_wiki_guard_command: output equals the exact command template
  - reconcile_wiki_guard_hook: absent file gets one Bash entry with the command
  - reconcile_wiki_guard_hook: legacy inline hook replaced in place, other matcher entry survives
  - reconcile_wiki_guard_hook: older versioned script path replaced, not duplicated
  - reconcile_wiki_guard_hook: second identical call is a write no-op
  - reconcile_wiki_guard_hook: unrelated hook sharing the entry's hooks list survives
  - reconcile_wiki_guard_hook: entry whose only hook was the legacy one is not left empty
  - reconcile_wiki_guard_hook: unrelated keys and hook events survive unchanged
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS_DIR = HUB / "plugins" / "mill" / "scripts"
AGENTS_DIR = HUB / "plugins" / "mill" / "agents"
sys.path.insert(0, str(SCRIPTS_DIR))

import _claude_settings  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_tools_frontmatter(agent_path: Path) -> list[str]:
    """Parse the `tools:` line out of an agent definition's YAML frontmatter."""
    text = agent_path.read_text(encoding="utf-8")
    match = re.search(r"^tools:\s*(.+)$", text, flags=re.MULTILINE)
    assert match, f"No tools: frontmatter found in {agent_path}"
    return [name.strip() for name in match.group(1).split(",")]


# ---------------------------------------------------------------------------
# merge_permission_allowlist
# ---------------------------------------------------------------------------


def test_creates_settings_file_when_absent() -> None:
    """A missing settings file is created with permissions.allow == MILL_SUBAGENT_TOOLS."""
    with tempfile.TemporaryDirectory() as tmp:
        settings_path = Path(tmp) / "settings.json"
        result = _claude_settings.merge_permission_allowlist(
            settings_path, _claude_settings.MILL_SUBAGENT_TOOLS
        )

        assert settings_path.exists(), "settings.json must be created"
        on_disk = json.loads(settings_path.read_text(encoding="utf-8"))
        assert on_disk["permissions"]["allow"] == _claude_settings.MILL_SUBAGENT_TOOLS, (
            f"Expected allow == MILL_SUBAGENT_TOOLS, got {on_disk['permissions']['allow']!r}"
        )
        assert result["permissions"]["allow"] == _claude_settings.MILL_SUBAGENT_TOOLS, (
            f"Returned dict should match written content; got {result!r}"
        )
    print("PASS merge_permission_allowlist -- absent settings file created with exact allowlist")


def test_preserves_existing_permissions_block() -> None:
    """A pre-existing allow/deny/additionalDirectories block survives the merge intact."""
    with tempfile.TemporaryDirectory() as tmp:
        settings_path = Path(tmp) / "settings.json"
        initial = {
            "permissions": {
                "allow": ["Read", "WebSearch"],
                "deny": ["Bash(git push --force:*)", "Bash(git reset --hard:*)"],
                "additionalDirectories": ["/home/user/other-project"],
            },
            "env": {"MILL_PYTHON": "/some/venv/bin/python"},
        }
        settings_path.write_text(json.dumps(initial, indent=2), encoding="utf-8")

        result = _claude_settings.merge_permission_allowlist(
            settings_path, _claude_settings.MILL_SUBAGENT_TOOLS
        )

        # Existing allow entries are preserved, in order, with new names appended.
        allow = result["permissions"]["allow"]
        assert allow[:2] == ["Read", "WebSearch"], f"Existing allow entries reordered: {allow!r}"
        for name in _claude_settings.MILL_SUBAGENT_TOOLS:
            assert allow.count(name) == 1, f"Expected exactly one {name!r} in allow; got {allow!r}"
        # "Read" is in both the pre-existing allow list and MILL_SUBAGENT_TOOLS -- must not duplicate.
        assert allow.count("Read") == 1, f"Read must not be duplicated; got {allow!r}"

        # deny, additionalDirectories, and other top-level keys are untouched.
        assert result["permissions"]["deny"] == initial["permissions"]["deny"], (
            "deny block must be untouched"
        )
        assert result["permissions"]["additionalDirectories"] == initial["permissions"]["additionalDirectories"], (
            "additionalDirectories block must be untouched"
        )
        assert result["env"] == initial["env"], "env block must be untouched"
    print("PASS merge_permission_allowlist -- existing allow/deny/additionalDirectories/env survive merge")


def test_idempotent_second_call_skips_write() -> None:
    """Calling merge_permission_allowlist twice produces the same allow list and skips the second write."""
    with tempfile.TemporaryDirectory() as tmp:
        settings_path = Path(tmp) / "settings.json"

        first = _claude_settings.merge_permission_allowlist(
            settings_path, _claude_settings.MILL_SUBAGENT_TOOLS
        )
        before_mtime = settings_path.stat().st_mtime_ns
        before_text = settings_path.read_text(encoding="utf-8")

        second = _claude_settings.merge_permission_allowlist(
            settings_path, _claude_settings.MILL_SUBAGENT_TOOLS
        )
        after_mtime = settings_path.stat().st_mtime_ns
        after_text = settings_path.read_text(encoding="utf-8")

        assert second["permissions"]["allow"] == first["permissions"]["allow"], (
            f"Second call's allow list must match first; got {second!r} vs {first!r}"
        )
        assert after_mtime == before_mtime, "Second call must not rewrite the file (no-op write-skip)"
        assert after_text == before_text, "File content must be unchanged after the second call"
    print("PASS merge_permission_allowlist -- idempotent, second call is a write no-op")


def test_mill_subagent_tools_matches_agent_frontmatter() -> None:
    """MILL_SUBAGENT_TOOLS is exactly the union of the two agents' tools: frontmatter."""
    implementer_tools = _parse_tools_frontmatter(AGENTS_DIR / "mill-implementer.md")
    reviewer_tools = _parse_tools_frontmatter(AGENTS_DIR / "mill-reviewer.md")

    expected_union = sorted(set(implementer_tools) | set(reviewer_tools))
    actual = sorted(set(_claude_settings.MILL_SUBAGENT_TOOLS))

    assert actual == expected_union, (
        f"MILL_SUBAGENT_TOOLS {actual!r} must match the union of agent tools: "
        f"frontmatter {expected_union!r} (implementer={implementer_tools!r}, reviewer={reviewer_tools!r})"
    )
    # No duplicates within MILL_SUBAGENT_TOOLS itself.
    assert len(_claude_settings.MILL_SUBAGENT_TOOLS) == len(set(_claude_settings.MILL_SUBAGENT_TOOLS)), (
        f"MILL_SUBAGENT_TOOLS must not contain duplicates; got {_claude_settings.MILL_SUBAGENT_TOOLS!r}"
    )
    print("PASS MILL_SUBAGENT_TOOLS -- matches union of mill-implementer.md and mill-reviewer.md tools: frontmatter")


# ---------------------------------------------------------------------------
# reconcile_destructive_denylist
# ---------------------------------------------------------------------------


def test_reconcile_retires_target_blind_rm_rf() -> None:
    """A target-blind rm -rf deny rule is removed; unrelated deny entries survive."""
    with tempfile.TemporaryDirectory() as tmp:
        settings_path = Path(tmp) / "settings.json"
        initial = {
            "permissions": {
                "deny": ["Bash(rm -rf:*)", "Bash(git push --force:*)"],
            },
        }
        settings_path.write_text(json.dumps(initial, indent=2), encoding="utf-8")

        result = _claude_settings.reconcile_destructive_denylist(settings_path)

        deny = result["permissions"]["deny"]
        assert "Bash(rm -rf:*)" not in deny, f"Retired rule must be removed; got {deny!r}"
        assert "Bash(git push --force:*)" in deny, f"Unrelated deny entry must survive; got {deny!r}"
    print("PASS reconcile_destructive_denylist -- target-blind rm -rf rule retired, unrelated entry survives")


def test_reconcile_adds_destructive_deny_entries() -> None:
    """A missing settings file is created with every DESTRUCTIVE_DENY entry present, no duplicates."""
    with tempfile.TemporaryDirectory() as tmp:
        settings_path = Path(tmp) / "settings.json"
        result = _claude_settings.reconcile_destructive_denylist(settings_path)

        deny = result["permissions"]["deny"]
        for entry in _claude_settings.DESTRUCTIVE_DENY:
            assert deny.count(entry) == 1, f"Expected exactly one {entry!r} in deny; got {deny!r}"
    print("PASS reconcile_destructive_denylist -- absent settings file created with exact DESTRUCTIVE_DENY set")


def test_reconcile_preserves_unrelated_deny_and_other_keys() -> None:
    """Unrelated deny entries, allow list, additionalDirectories, and env block survive untouched."""
    with tempfile.TemporaryDirectory() as tmp:
        settings_path = Path(tmp) / "settings.json"
        initial = {
            "permissions": {
                "allow": ["Read", "WebSearch"],
                "deny": ["Bash(git push --force:*)", "Bash(git reset --hard:*)"],
                "additionalDirectories": ["/home/user/other-project"],
            },
            "env": {"MILL_PYTHON": "/some/venv/bin/python"},
        }
        settings_path.write_text(json.dumps(initial, indent=2), encoding="utf-8")

        result = _claude_settings.reconcile_destructive_denylist(settings_path)

        deny = result["permissions"]["deny"]
        for entry in initial["permissions"]["deny"]:
            assert entry in deny, f"Unrelated deny entry must survive; got {deny!r}"
        assert result["permissions"]["allow"] == initial["permissions"]["allow"], (
            "allow list must be untouched"
        )
        assert result["permissions"]["additionalDirectories"] == initial["permissions"]["additionalDirectories"], (
            "additionalDirectories block must be untouched"
        )
        assert result["env"] == initial["env"], "env block must be untouched"
    print("PASS reconcile_destructive_denylist -- unrelated deny/allow/additionalDirectories/env survive reconciliation")


def test_reconcile_idempotent_second_call_skips_write() -> None:
    """Calling reconcile_destructive_denylist twice produces the same deny list and skips the second write."""
    with tempfile.TemporaryDirectory() as tmp:
        settings_path = Path(tmp) / "settings.json"

        first = _claude_settings.reconcile_destructive_denylist(settings_path)
        before_mtime = settings_path.stat().st_mtime_ns
        before_text = settings_path.read_text(encoding="utf-8")

        second = _claude_settings.reconcile_destructive_denylist(settings_path)
        after_mtime = settings_path.stat().st_mtime_ns
        after_text = settings_path.read_text(encoding="utf-8")

        assert second["permissions"]["deny"] == first["permissions"]["deny"], (
            f"Second call's deny list must match first; got {second!r} vs {first!r}"
        )
        assert after_mtime == before_mtime, "Second call must not rewrite the file (no-op write-skip)"
        assert after_text == before_text, "File content must be unchanged after the second call"
    print("PASS reconcile_destructive_denylist -- idempotent, second call is a write no-op")


# ---------------------------------------------------------------------------
# reconcile_wiki_guard_hook
# ---------------------------------------------------------------------------

NEW_COMMAND = _claude_settings.build_wiki_guard_command(Path("/plug/2.0.1"))
LEGACY_COMMAND = "grep -qE 'daemon-owned|\\.wiki\\b' && echo blocked"
OTHER_MATCHER_ENTRY = {
    "matcher": "Read|Edit|Write|Grep|Glob",
    "hooks": [{"type": "command", "command": "echo other"}],
}


def _write_and_reconcile(initial: dict | None) -> tuple[dict, str]:
    """Write initial settings (or none), reconcile, and return (result, file text)."""
    with tempfile.TemporaryDirectory() as tmp:
        settings_path = Path(tmp) / "settings.json"
        if initial is not None:
            settings_path.write_text(json.dumps(initial, indent=2), encoding="utf-8")
        result = _claude_settings.reconcile_wiki_guard_hook(settings_path, NEW_COMMAND)
        return result, settings_path.read_text(encoding="utf-8")


def test_build_wiki_guard_command_exact_template() -> None:
    """The command matches the documented template exactly."""
    expected = (
        'PYTHONPATH="/plug/2.0.1/scripts" "$MILL_PYTHON" "/plug/2.0.1/scripts/millpy-wiki-guard.py"'
    )
    assert NEW_COMMAND == expected, f"Got {NEW_COMMAND!r}"
    print("PASS build_wiki_guard_command -- exact template")


def test_wiki_guard_absent_file_gets_bash_entry() -> None:
    """A missing settings file is created with one Bash entry carrying the command."""
    result, _ = _write_and_reconcile(None)
    assert result["hooks"]["PreToolUse"] == [
        {"matcher": "Bash", "hooks": [{"type": "command", "command": NEW_COMMAND}]}
    ], f"Got {result!r}"
    print("PASS reconcile_wiki_guard_hook -- absent file gets Bash entry")


def test_wiki_guard_replaces_legacy_in_place() -> None:
    """The legacy inline hook is replaced in place; the other matcher entry is untouched."""
    initial = {"hooks": {"PreToolUse": [
        {"matcher": "Bash", "hooks": [{"type": "command", "command": LEGACY_COMMAND}]},
        OTHER_MATCHER_ENTRY,
    ]}}
    result, _ = _write_and_reconcile(initial)
    assert result["hooks"]["PreToolUse"] == [
        {"matcher": "Bash", "hooks": [{"type": "command", "command": NEW_COMMAND}]},
        OTHER_MATCHER_ENTRY,
    ], f"Got {result!r}"
    print("PASS reconcile_wiki_guard_hook -- legacy hook replaced in place")


def test_wiki_guard_replaces_older_versioned_path() -> None:
    """An older installed script path is replaced, not duplicated."""
    old_command = _claude_settings.build_wiki_guard_command(Path("/plug/1.0.0"))
    initial = {"hooks": {"PreToolUse": [
        {"matcher": "Bash", "hooks": [{"type": "command", "command": old_command}]},
    ]}}
    result, _ = _write_and_reconcile(initial)
    assert result["hooks"]["PreToolUse"] == [
        {"matcher": "Bash", "hooks": [{"type": "command", "command": NEW_COMMAND}]}
    ], f"Got {result!r}"
    print("PASS reconcile_wiki_guard_hook -- older versioned path replaced")


def test_wiki_guard_second_call_is_noop() -> None:
    """A second identical call leaves the file bytes unchanged."""
    with tempfile.TemporaryDirectory() as tmp:
        settings_path = Path(tmp) / "settings.json"
        _claude_settings.reconcile_wiki_guard_hook(settings_path, NEW_COMMAND)
        before_mtime = settings_path.stat().st_mtime_ns
        before_text = settings_path.read_text(encoding="utf-8")
        _claude_settings.reconcile_wiki_guard_hook(settings_path, NEW_COMMAND)
        assert settings_path.stat().st_mtime_ns == before_mtime, "Second call must skip the write"
        assert settings_path.read_text(encoding="utf-8") == before_text
    print("PASS reconcile_wiki_guard_hook -- idempotent write no-op")


def test_wiki_guard_keeps_unrelated_hook_in_shared_entry() -> None:
    """An unrelated hook in the same entry survives while the matching hook is replaced."""
    unrelated = {"type": "command", "command": "echo unrelated"}
    initial = {"hooks": {"PreToolUse": [
        {"matcher": "Bash", "hooks": [
            unrelated, {"type": "command", "command": LEGACY_COMMAND},
        ]},
    ]}}
    result, _ = _write_and_reconcile(initial)
    assert result["hooks"]["PreToolUse"] == [
        {"matcher": "Bash", "hooks": [unrelated, {"type": "command", "command": NEW_COMMAND}]}
    ], f"Got {result!r}"
    print("PASS reconcile_wiki_guard_hook -- unrelated hook in shared entry survives")


def test_wiki_guard_duplicate_matches_leave_no_empty_entry() -> None:
    """A second matching entry is removed entirely, not left with an empty hooks list."""
    initial = {"hooks": {"PreToolUse": [
        {"matcher": "Bash", "hooks": [{"type": "command", "command": LEGACY_COMMAND}]},
        {"matcher": "Bash", "hooks": [{"type": "command", "command": LEGACY_COMMAND}]},
    ]}}
    result, _ = _write_and_reconcile(initial)
    assert result["hooks"]["PreToolUse"] == [
        {"matcher": "Bash", "hooks": [{"type": "command", "command": NEW_COMMAND}]}
    ], f"Got {result!r}"
    print("PASS reconcile_wiki_guard_hook -- no empty entry left behind")


def test_wiki_guard_preserves_unrelated_keys() -> None:
    """permissions, env, and other hook events survive unchanged."""
    initial = {
        "permissions": {"allow": ["Read"]},
        "env": {"MILL_PYTHON": "/py"},
        "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo stop"}]}]},
    }
    result, _ = _write_and_reconcile(initial)
    assert result["permissions"] == initial["permissions"]
    assert result["env"] == initial["env"]
    assert result["hooks"]["Stop"] == initial["hooks"]["Stop"]
    print("PASS reconcile_wiki_guard_hook -- unrelated keys survive")


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------


def main() -> int:
    tests = [
        test_creates_settings_file_when_absent,
        test_preserves_existing_permissions_block,
        test_idempotent_second_call_skips_write,
        test_reconcile_retires_target_blind_rm_rf,
        test_reconcile_adds_destructive_deny_entries,
        test_reconcile_preserves_unrelated_deny_and_other_keys,
        test_reconcile_idempotent_second_call_skips_write,
        test_mill_subagent_tools_matches_agent_frontmatter,
        test_build_wiki_guard_command_exact_template,
        test_wiki_guard_absent_file_gets_bash_entry,
        test_wiki_guard_replaces_legacy_in_place,
        test_wiki_guard_replaces_older_versioned_path,
        test_wiki_guard_second_call_is_noop,
        test_wiki_guard_keeps_unrelated_hook_in_shared_entry,
        test_wiki_guard_duplicate_matches_leave_no_empty_entry,
        test_wiki_guard_preserves_unrelated_keys,
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
