"""Unit tests for sub-agent definitions (mill-reviewer and mill-implementer).

Covers:
  - mill-reviewer: tools list is exactly {Read, Grep, Glob, Write} -- the reviewer may write, but only its own report;
      it still cannot edit an existing file, run a command, or commit, so {Edit, Bash, NotebookEdit} remain forbidden.
  - mill-implementer: tools list includes {Read, Edit, Write, Bash, Grep, Glob, Skill}
  - Both agents: name matches filename stem
  - Both agents: non-empty description
  - Both agents: no model field set (per-call override supplies tier)
"""

from __future__ import annotations

import json
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


def _check_tier_agent_definition(
    agent_file: Path, base_file: Path, expected_effort: str
) -> None:
    """Assert a per-tier agent-definition file is a faithful tier variant of its base.

    Per the overview's "new agent-definition files are byte-identical to their base except name and effort" Shared Decision, a tier file (e.g.
    mill-reviewer-high.md) must carry the same description and tools as its base file (mill-reviewer.md), differing only in its `name` (matching the tier filename stem) and an added `effort` frontmatter key.

    Args:
        agent_file: path to the tier-suffixed agent-definition file under test.
        base_file: path to the untiered base agent-definition file it was derived from.
        expected_effort: the tier string the file's `effort` frontmatter key must equal (e.g. "medium", "high", "max").
    """
    assert agent_file.exists(), f"Agent file not found: {agent_file}"

    tier_text = agent_file.read_text(encoding="utf-8")
    tier_fm = _extract_frontmatter(tier_text)
    assert tier_fm is not None, f"No frontmatter in {agent_file}"

    base_text = base_file.read_text(encoding="utf-8")
    base_fm = _extract_frontmatter(base_text)
    assert base_fm is not None, f"No frontmatter in {base_file}"

    # Name must match the tier file's own filename stem, e.g. "mill-reviewer-high".
    assert tier_fm.get("name") == agent_file.stem, (
        f"Expected name {agent_file.stem!r}, got {tier_fm.get('name')!r}"
    )

    # Description is copied verbatim from the base file -- read it dynamically so this check tracks the base file's actual text rather than a hardcoded copy.
    base_desc = base_fm.get("description")
    assert tier_fm.get("description") == base_desc, (
        f"{agent_file.name} description must equal base file's description exactly; "
        f"got {tier_fm.get('description')!r}, expected {base_desc!r}"
    )

    # Tools set is copied verbatim from the base file (normalized the same way the base-file tests normalize theirs: split on comma/whitespace, strip, dedupe).
    tier_tools_raw = tier_fm.get("tools", "")
    base_tools_raw = base_fm.get("tools", "")
    tier_tools = {t.strip() for t in tier_tools_raw.replace(",", " ").split() if t.strip()}
    base_tools = {t.strip() for t in base_tools_raw.replace(",", " ").split() if t.strip()}
    assert tier_tools == base_tools, (
        f"{agent_file.name} tools must equal base file's tools exactly; "
        f"got {tier_tools}, expected {base_tools}"
    )

    # The tier is what makes this file dispatchable as a distinct subagent_type.
    assert tier_fm.get("effort") == expected_effort, (
        f"Expected effort {expected_effort!r}, got {tier_fm.get('effort')!r}"
    )

    # No model field -- per-call override supplies the tier, same invariant the base-file tests enforce.
    assert "model" not in tier_fm, (
        f"{agent_file.name} must not set model field (per-call override supplies tier)"
    )

    print(f"PASS _check_tier_agent_definition ({agent_file.name})")


def test_reviewer_low_agent_definition() -> None:
    """mill-reviewer-low.md is a byte-faithful low-tier variant of mill-reviewer.md."""
    agents_dir = HUB / "plugins" / "mill" / "agents"
    _check_tier_agent_definition(
        agents_dir / "mill-reviewer-low.md", agents_dir / "mill-reviewer.md", "low"
    )


def test_reviewer_medium_agent_definition() -> None:
    """mill-reviewer-medium.md is a byte-faithful medium-tier variant of mill-reviewer.md."""
    agents_dir = HUB / "plugins" / "mill" / "agents"
    _check_tier_agent_definition(
        agents_dir / "mill-reviewer-medium.md", agents_dir / "mill-reviewer.md", "medium"
    )


def test_reviewer_high_agent_definition() -> None:
    """mill-reviewer-high.md is a byte-faithful high-tier variant of mill-reviewer.md."""
    agents_dir = HUB / "plugins" / "mill" / "agents"
    _check_tier_agent_definition(
        agents_dir / "mill-reviewer-high.md", agents_dir / "mill-reviewer.md", "high"
    )


def test_reviewer_max_agent_definition() -> None:
    """mill-reviewer-max.md is a byte-faithful max-tier variant of mill-reviewer.md."""
    agents_dir = HUB / "plugins" / "mill" / "agents"
    _check_tier_agent_definition(
        agents_dir / "mill-reviewer-max.md", agents_dir / "mill-reviewer.md", "max"
    )


def test_reviewer_xhigh_agent_definition() -> None:
    """mill-reviewer-xhigh.md is a byte-faithful xhigh-tier variant of mill-reviewer.md."""
    agents_dir = HUB / "plugins" / "mill" / "agents"
    _check_tier_agent_definition(
        agents_dir / "mill-reviewer-xhigh.md", agents_dir / "mill-reviewer.md", "xhigh"
    )


def test_implementer_low_agent_definition() -> None:
    """mill-implementer-low.md is a byte-faithful low-tier variant of mill-implementer.md."""
    agents_dir = HUB / "plugins" / "mill" / "agents"
    _check_tier_agent_definition(
        agents_dir / "mill-implementer-low.md",
        agents_dir / "mill-implementer.md",
        "low",
    )


def test_implementer_medium_agent_definition() -> None:
    """mill-implementer-medium.md is a byte-faithful medium-tier variant of mill-implementer.md."""
    agents_dir = HUB / "plugins" / "mill" / "agents"
    _check_tier_agent_definition(
        agents_dir / "mill-implementer-medium.md",
        agents_dir / "mill-implementer.md",
        "medium",
    )


def test_implementer_high_agent_definition() -> None:
    """mill-implementer-high.md is a byte-faithful high-tier variant of mill-implementer.md."""
    agents_dir = HUB / "plugins" / "mill" / "agents"
    _check_tier_agent_definition(
        agents_dir / "mill-implementer-high.md", agents_dir / "mill-implementer.md", "high"
    )


def test_implementer_max_agent_definition() -> None:
    """mill-implementer-max.md is a byte-faithful max-tier variant of mill-implementer.md."""
    agents_dir = HUB / "plugins" / "mill" / "agents"
    _check_tier_agent_definition(
        agents_dir / "mill-implementer-max.md", agents_dir / "mill-implementer.md", "max"
    )


def test_implementer_xhigh_agent_definition() -> None:
    """mill-implementer-xhigh.md is a byte-faithful xhigh-tier variant of mill-implementer.md."""
    agents_dir = HUB / "plugins" / "mill" / "agents"
    _check_tier_agent_definition(
        agents_dir / "mill-implementer-xhigh.md",
        agents_dir / "mill-implementer.md",
        "xhigh",
    )


def test_reviewer_agent_definition() -> None:
    """mill-reviewer may write only its own report: tools = {Read, Grep, Glob, Write}.

    It still cannot edit an existing file, run a command, or commit, so {Edit, Bash, NotebookEdit} remain forbidden.
    """
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
    expected_tools = {"Read", "Grep", "Glob", "Write"}
    assert tools == expected_tools, (
        f"mill-reviewer tools must be exactly {expected_tools}, got {tools}"
    )

    # Verify NO mutating tools beyond the briefs-scoped Write grant above -- Edit, Bash, and NotebookEdit would let the reviewer modify an existing file, run a command, or commit, none of which it is allowed to do.
    mutating = {"Edit", "Bash", "NotebookEdit"}
    forbidden = tools & mutating
    assert not forbidden, (
        f"mill-reviewer must not have mutating tools; found {forbidden}"
    )

    # No model field
    assert "model" not in fm, (
        "mill-reviewer must not set model field (per-call override supplies tier)"
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
        "mill-implementer must not set model field (per-call override supplies tier)"
    )

    print("PASS test_implementer_agent_definition")


def test_plugin_json_registers_all_agent_files() -> None:
    """plugin.json's explicit `agents` array must list every agent-definition file on disk.

    Per Claude Code's plugin manifest reference, an explicit `agents` array *replaces* directory-based auto-discovery -- a file present under `agents/` but missing from this array is never registered as a dispatchable subagent_type.
    This test guards against the exact class of gap Card 4 fixes: a future agent file added to the directory without a matching plugin.json entry,
    or a stale entry left behind after a file is removed.
    """
    manifest_path = HUB / "plugins" / "mill" / ".claude-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # Normalize the manifest's agents array to a set of bare "<name>.md" basenames.
    manifest_agents = {
        Path(entry).name for entry in manifest.get("agents", [])
    }

    # Every agent-definition file actually present on disk.
    agents_dir = HUB / "plugins" / "mill" / "agents"
    disk_agents = {path.name for path in agents_dir.glob("*.md")}

    assert manifest_agents == disk_agents, (
        f"plugin.json agents array must exactly match agents/*.md on disk; "
        f"manifest={manifest_agents}, disk={disk_agents}"
    )

    print("PASS test_plugin_json_registers_all_agent_files")


def main() -> int:
    tests = [
        test_reviewer_agent_definition,
        test_implementer_agent_definition,
        test_reviewer_low_agent_definition,
        test_reviewer_medium_agent_definition,
        test_reviewer_high_agent_definition,
        test_reviewer_max_agent_definition,
        test_reviewer_xhigh_agent_definition,
        test_implementer_low_agent_definition,
        test_implementer_medium_agent_definition,
        test_implementer_high_agent_definition,
        test_implementer_max_agent_definition,
        test_implementer_xhigh_agent_definition,
        test_plugin_json_registers_all_agent_files,
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
