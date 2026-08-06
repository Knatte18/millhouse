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
# Main runner
# ---------------------------------------------------------------------------


def main() -> int:
    tests = [
        test_creates_settings_file_when_absent,
        test_preserves_existing_permissions_block,
        test_idempotent_second_call_skips_write,
        test_mill_subagent_tools_matches_agent_frontmatter,
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
