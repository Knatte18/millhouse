"""Unit tests for sub-agent definitions (mill-reviewer and mill-implementer).

Covers:
  - mill-reviewer: tools list is exactly {Read, Grep, Glob} with no mutating tools
  - mill-implementer: tools list includes {Read, Edit, Write, Bash, Grep, Glob, Skill}
  - Both agents: name matches filename stem
  - Both agents: non-empty description
  - Both agents: no model field set (per-call override supplies tier)
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS_DIR = HUB / "plugins" / "mill" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


def _extract_frontmatter(text: str) -> dict | None:
    """Return parsed YAML frontmatter from text, or None if absent/malformed."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            try:
                return yaml.safe_load("\n".join(lines[1:i])) or {}
            except yaml.YAMLError:
                return None
    return None


def test_reviewer_agent_definition() -> None:
    """mill-reviewer must be read-only: tools = {Read, Grep, Glob} only."""
    agent_file = HUB / "plugins" / "mill" / "agents" / "mill-reviewer.md"
    assert agent_file.exists(), f"Agent file not found: {agent_file}"

    text = agent_file.read_text(encoding="utf-8")
    fm = _extract_frontmatter(text)
    assert fm is not None, f"No frontmatter in {agent_file}"

    # Name must match filename stem
    assert fm.get("name") == "mill-reviewer", (
        f"Expected name 'mill-reviewer', got {fm.get('name')!r}"
    )

    # Description must be non-empty
    desc = fm.get("description", "").strip()
    assert desc, "description must be non-empty"

    # Tools list must exist
    tools_raw = fm.get("tools", "")
    assert tools_raw, "tools field is required"

    # Normalize tools: split on comma/whitespace, strip, deduplicate
    tools = {t.strip() for t in tools_raw.replace(",", " ").split() if t.strip()}
    expected_tools = {"Read", "Grep", "Glob"}
    assert tools == expected_tools, (
        f"mill-reviewer tools must be exactly {expected_tools}, got {tools}"
    )

    # Verify NO mutating tools
    mutating = {"Edit", "Write", "Bash", "NotebookEdit"}
    forbidden = tools & mutating
    assert not forbidden, (
        f"mill-reviewer must not have mutating tools; found {forbidden}"
    )

    # No model field
    assert "model" not in fm, (
        f"mill-reviewer must not set model field (per-call override supplies tier)"
    )

    print("PASS test_reviewer_agent_definition")


def test_implementer_agent_definition() -> None:
    """mill-implementer must have full tools: Read, Edit, Write, Bash, Grep, Glob, Skill."""
    agent_file = HUB / "plugins" / "mill" / "agents" / "mill-implementer.md"
    assert agent_file.exists(), f"Agent file not found: {agent_file}"

    text = agent_file.read_text(encoding="utf-8")
    fm = _extract_frontmatter(text)
    assert fm is not None, f"No frontmatter in {agent_file}"

    # Name must match filename stem
    assert fm.get("name") == "mill-implementer", (
        f"Expected name 'mill-implementer', got {fm.get('name')!r}"
    )

    # Description must be non-empty
    desc = fm.get("description", "").strip()
    assert desc, "description must be non-empty"

    # Tools list must exist
    tools_raw = fm.get("tools", "")
    assert tools_raw, "tools field is required"

    # Normalize tools
    tools = {t.strip() for t in tools_raw.replace(",", " ").split() if t.strip()}
    required_tools = {"Read", "Edit", "Write", "Bash", "Grep", "Glob", "Skill"}
    assert required_tools.issubset(tools), (
        f"mill-implementer must include {required_tools}; got {tools}"
    )

    # No model field
    assert "model" not in fm, (
        f"mill-implementer must not set model field (per-call override supplies tier)"
    )

    print("PASS test_implementer_agent_definition")


def main() -> int:
    tests = [
        test_reviewer_agent_definition,
        test_implementer_agent_definition,
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
