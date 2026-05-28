"""Unit tests for _reviewers.py (load, resolve, resolve_role, validate_role_refs)
plus _reviewer_single.run dispatch (was test-reviewer-single.py, merged 2026-05-28).
"""
from __future__ import annotations

import inspect
import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))
sys.path.insert(0, str(HUB / "plugins" / "mill" / "unit_tests"))

import _paths  # noqa: E402
import _reviewers  # noqa: E402
import _reviewer_single  # noqa: E402
import _reviewer_test_stub as stub  # noqa: E402
from _reviewers import ReviewerError  # noqa: E402
from _test_cfg import make_minimal_cfg  # noqa: E402
from _test_registry import make_minimal_registry, write_to  # noqa: E402
from unittest.mock import patch  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_yaml(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _load_with_overlay(yaml_text: str) -> dict:
    """Load reviewers from a fresh hub with yaml_text as its local overlay.

    Used by the extends/cluster test block. Patches the plugin template path
    to a nonexistent location so the local overlay is the only source.
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        hub = tmp_path / "hub"
        hub.mkdir()
        (hub / ".millhouse").mkdir()
        (hub / ".millhouse" / "agents.local.yaml").write_text(yaml_text, encoding="utf-8")
        with patch.object(
            _reviewers,
            "resolve_plugin_template_path",
            return_value=tmp_path / "nonexistent" / "mill-agents.yaml",
        ):
            return _reviewers.load(hub)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_load_happy_path() -> None:
    """load() round-trips a valid agents.yaml via local overlay."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        hub_dir = tmp_path / "hub"
        hub_dir.mkdir()
        # Write registry to local overlay
        (hub_dir / ".millhouse").mkdir()
        (hub_dir / ".millhouse" / "agents.local.yaml").write_text(
            "sonnetmax:\n  type: single\n  provider: claude\n  model: claude-sonnet-4-6\n"
            "sonnetmax_tool:\n  type: single\n  provider: claude\n  model: claude-sonnet-4-6\n  tooluse: true\n"
        )
        with patch.object(
            _reviewers,
            "resolve_plugin_template_path",
            return_value=tmp_path / "nonexistent" / "mill-agents.yaml"
        ):
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                registry = _reviewers.load(hub_dir)

        assert "sonnetmax" in registry
        assert registry["sonnetmax"]["type"] == "single"
        assert registry["sonnetmax"]["provider"] == "claude"
        assert "sonnetmax_tool" in registry
        assert registry["sonnetmax_tool"]["tooluse"] is True
    print("PASS: load happy path round-trips")


def test_load_raises_on_missing_file() -> None:
    """load() raises ReviewerError when no source is available."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        hub_dir = tmp_path / "hub"
        hub_dir.mkdir()
        with patch.object(
            _reviewers,
            "resolve_plugin_template_path",
            return_value=tmp_path / "nonexistent" / "mill-agents.yaml"
        ):
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                try:
                    _reviewers.load(hub_dir)
                    raise AssertionError("Expected ReviewerError")
                except ReviewerError as exc:
                    assert "Missing registry" in str(exc)
    print("PASS: load raises on missing file")


def test_load_raises_single_missing_provider() -> None:
    """load() raises when a single entry is missing 'provider'."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        hub_dir = tmp_path / "hub"
        hub_dir.mkdir()
        (hub_dir / ".millhouse").mkdir()
        (hub_dir / ".millhouse" / "agents.local.yaml").write_text(
            "bad:\n  type: single\n  model: claude-sonnet-4-6\n"
        )
        with patch.object(
            _reviewers,
            "resolve_plugin_template_path",
            return_value=tmp_path / "nonexistent" / "mill-agents.yaml"
        ):
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                try:
                    _reviewers.load(hub_dir)
                    raise AssertionError("Expected ReviewerError")
                except ReviewerError as exc:
                    assert "provider" in str(exc)
    print("PASS: load raises single missing provider")


def test_load_raises_cluster_missing_workers() -> None:
    """load() raises when a cluster entry is missing 'workers'."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        hub_dir = tmp_path / "hub"
        hub_dir.mkdir()
        (hub_dir / ".millhouse").mkdir()
        (hub_dir / ".millhouse" / "agents.local.yaml").write_text(
            "myworker:\n  type: single\n  provider: claude\n  model: claude-sonnet-4-6\n"
            "mycluster:\n  type: cluster\n  handler:\n    use: myworker\n"
        )
        with patch.object(
            _reviewers,
            "resolve_plugin_template_path",
            return_value=tmp_path / "nonexistent" / "mill-agents.yaml"
        ):
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                try:
                    _reviewers.load(hub_dir)
                    raise AssertionError("Expected ReviewerError")
                except ReviewerError as exc:
                    assert "workers" in str(exc)
    print("PASS: load raises cluster missing workers")


def test_load_raises_cluster_missing_handler() -> None:
    """load() raises when a cluster entry is missing 'handler'."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        hub_dir = tmp_path / "hub"
        hub_dir.mkdir()
        (hub_dir / ".millhouse").mkdir()
        (hub_dir / ".millhouse" / "agents.local.yaml").write_text(
            "myworker:\n  type: single\n  provider: claude\n  model: claude-sonnet-4-6\n"
            "mycluster:\n  type: cluster\n  workers:\n    use: myworker\n    count: 2\n"
        )
        with patch.object(
            _reviewers,
            "resolve_plugin_template_path",
            return_value=tmp_path / "nonexistent" / "mill-agents.yaml"
        ):
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                try:
                    _reviewers.load(hub_dir)
                    raise AssertionError("Expected ReviewerError")
                except ReviewerError as exc:
                    assert "handler" in str(exc)
    print("PASS: load raises cluster missing handler")


def test_load_raises_cluster_workers_count_non_positive() -> None:
    """load() raises when cluster workers.count is not a positive integer."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        hub_dir = tmp_path / "hub"
        hub_dir.mkdir()
        (hub_dir / ".millhouse").mkdir()
        (hub_dir / ".millhouse" / "agents.local.yaml").write_text(
            "myworker:\n  type: single\n  provider: claude\n  model: claude-sonnet-4-6\n"
            "mycluster:\n  type: cluster\n"
            "  workers:\n    use: myworker\n    count: 0\n"
            "  handler:\n    use: myworker\n"
        )
        with patch.object(
            _reviewers,
            "resolve_plugin_template_path",
            return_value=tmp_path / "nonexistent" / "mill-agents.yaml"
        ):
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                try:
                    _reviewers.load(hub_dir)
                    raise AssertionError("Expected ReviewerError")
                except ReviewerError as exc:
                    assert "count" in str(exc)
    print("PASS: load raises cluster workers.count non-positive")


def test_load_raises_unknown_type() -> None:
    """load() raises on unknown type."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        hub_dir = tmp_path / "hub"
        hub_dir.mkdir()
        (hub_dir / ".millhouse").mkdir()
        (hub_dir / ".millhouse" / "agents.local.yaml").write_text(
            "bad:\n  type: unknown\n  provider: claude\n  model: x\n"
        )
        with patch.object(_reviewers, "resolve_plugin_template_path", return_value=tmp_path / "nonexistent" / "mill-agents.yaml"):
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                try:
                    _reviewers.load(hub_dir)
                    raise AssertionError("Expected ReviewerError")
                except ReviewerError as exc:
                    assert "unknown" in str(exc).lower() or "type" in str(exc)
    print("PASS: load raises unknown type")


def test_load_raises_invalid_name_uppercase() -> None:
    """load() raises on names with uppercase letters."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        hub_dir = tmp_path / "hub"
        hub_dir.mkdir()
        (hub_dir / ".millhouse").mkdir()
        (hub_dir / ".millhouse" / "agents.local.yaml").write_text(
            "BadName:\n  type: single\n  provider: claude\n  model: x\n"
        )
        with patch.object(_reviewers, "resolve_plugin_template_path", return_value=tmp_path / "nonexistent" / "mill-agents.yaml"):
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                try:
                    _reviewers.load(hub_dir)
                    raise AssertionError("Expected ReviewerError")
                except ReviewerError as exc:
                    assert "BadName" in str(exc) or "Invalid" in str(exc)
    print("PASS: load raises invalid name (uppercase)")


def test_load_raises_invalid_name_dot() -> None:
    """load() raises on names containing a dot."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        hub_dir = tmp_path / "hub"
        hub_dir.mkdir()
        (hub_dir / ".millhouse").mkdir()
        (hub_dir / ".millhouse" / "agents.local.yaml").write_text(
            "bad.name:\n  type: single\n  provider: claude\n  model: x\n"
        )
        with patch.object(_reviewers, "resolve_plugin_template_path", return_value=tmp_path / "nonexistent" / "mill-agents.yaml"):
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                try:
                    _reviewers.load(hub_dir)
                    raise AssertionError("Expected ReviewerError")
                except ReviewerError as exc:
                    assert "bad.name" in str(exc) or "Invalid" in str(exc)
    print("PASS: load raises invalid name (dot)")


def test_load_raises_duplicate_name() -> None:
    """load() raises when the same name appears twice in the file."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        hub_dir = tmp_path / "hub"
        hub_dir.mkdir()
        (hub_dir / ".millhouse").mkdir()
        (hub_dir / ".millhouse" / "agents.local.yaml").write_text(
            "sonnetmax:\n  type: single\n  provider: claude\n  model: x\n"
            "sonnetmax:\n  type: single\n  provider: claude\n  model: y\n"
        )
        with patch.object(_reviewers, "resolve_plugin_template_path", return_value=tmp_path / "nonexistent" / "mill-agents.yaml"):
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                try:
                    _reviewers.load(hub_dir)
                    raise AssertionError("Expected ReviewerError")
                except ReviewerError as exc:
                    assert "sonnetmax" in str(exc) or "Duplicate" in str(exc)
    print("PASS: load raises duplicate name")


def test_load_raises_cluster_use_nonexistent() -> None:
    """load() raises when a cluster use: references a non-existent name."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        hub_dir = tmp_path / "hub"
        hub_dir.mkdir()
        (hub_dir / ".millhouse").mkdir()
        (hub_dir / ".millhouse" / "agents.local.yaml").write_text(
            "myworker:\n  type: single\n  provider: claude\n  model: x\n"
            "mycluster:\n  type: cluster\n"
            "  workers:\n    use: nonexistent\n    count: 2\n"
            "  handler:\n    use: myworker\n"
        )
        with patch.object(_reviewers, "resolve_plugin_template_path", return_value=tmp_path / "nonexistent" / "mill-agents.yaml"):
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                try:
                    _reviewers.load(hub_dir)
                    raise AssertionError("Expected ReviewerError")
                except ReviewerError as exc:
                    assert "nonexistent" in str(exc)
    print("PASS: load raises cluster use referencing nonexistent name")


def test_load_raises_cluster_use_referencing_cluster() -> None:
    """load() raises when a cluster use: references another cluster."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        hub_dir = tmp_path / "hub"
        hub_dir.mkdir()
        (hub_dir / ".millhouse").mkdir()
        (hub_dir / ".millhouse" / "agents.local.yaml").write_text(
            "myworker:\n  type: single\n  provider: claude\n  model: x\n"
            "clusterb:\n  type: cluster\n"
            "  workers:\n    use: myworker\n    count: 2\n"
            "  handler:\n    use: myworker\n"
            "clustera:\n  type: cluster\n"
            "  workers:\n    use: clusterb\n    count: 3\n"
            "  handler:\n    use: myworker\n"
        )
        with patch.object(_reviewers, "resolve_plugin_template_path", return_value=tmp_path / "nonexistent" / "mill-agents.yaml"):
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                try:
                    _reviewers.load(hub_dir)
                    raise AssertionError("Expected ReviewerError")
                except ReviewerError as exc:
                    assert "single" in str(exc) or "cluster" in str(exc).lower()
    print("PASS: load raises cluster use referencing another cluster")


def test_resolve_single_happy_path() -> None:
    """resolve() returns spec for a known single entry."""
    registry = make_minimal_registry()
    spec = _reviewers.resolve(registry, "sonnetmax")
    assert spec["type"] == "single"
    assert spec["provider"] == "claude"
    assert spec["model"] == "claude-sonnet-4-6"
    assert spec["tooluse"] is False  # defaulted
    print("PASS: resolve single happy path")


def test_resolve_cluster_happy_path() -> None:
    """resolve() returns cluster spec with use: values replaced by fully-resolved single-specs."""
    registry = {
        "myworker": {
            "type": "single",
            "provider": "claude",
            "model": "claude-sonnet-4-6",
            "effort": "max",
        },
        "mycluster": {
            "type": "cluster",
            "workers": {"use": "myworker", "count": 3},
            "handler": {"use": "myworker"},
        },
    }
    spec = _reviewers.resolve(registry, "mycluster")
    assert spec["type"] == "cluster"
    assert isinstance(spec["workers"]["use"], dict)
    assert spec["workers"]["use"]["provider"] == "claude"
    assert isinstance(spec["handler"]["use"], dict)
    assert spec["workers"]["count"] == 3
    print("PASS: resolve cluster flattens use: references")


def test_resolve_raises_missing_name() -> None:
    """resolve() raises ReviewerError on unknown name."""
    registry = make_minimal_registry()
    try:
        _reviewers.resolve(registry, "does-not-exist")
        raise AssertionError("Expected ReviewerError")
    except ReviewerError as exc:
        assert "does-not-exist" in str(exc)
    print("PASS: resolve raises on missing name")


def test_resolve_test_stub_special_case() -> None:
    """resolve(registry, 'test_stub') returns synthetic spec without consulting registry."""
    registry: dict = {}  # empty — test_stub must not need it
    spec = _reviewers.resolve(registry, "test_stub")
    assert spec == {"type": "single", "provider": "test_stub", "tooluse": False}
    print("PASS: resolve test_stub returns synthetic spec")


def test_resolve_role_null_reviewer_returns_none() -> None:
    """resolve_role returns None when reviewer is null."""
    cfg = make_minimal_cfg()
    cfg["roles"]["plan-review"]["batch"]["reviewer"] = None
    registry = make_minimal_registry()
    result = _reviewers.resolve_role(cfg, registry, "plan-review", "batch")
    assert result is None
    print("PASS: resolve_role null reviewer returns None")


def test_resolve_role_rounds_zero_returns_none() -> None:
    """resolve_role returns None when rounds is 0."""
    cfg = make_minimal_cfg()
    cfg["roles"]["plan-review"]["batch"]["rounds"] = 0
    registry = make_minimal_registry()
    result = _reviewers.resolve_role(cfg, registry, "plan-review", "batch")
    assert result is None
    print("PASS: resolve_role rounds==0 returns None")


def test_resolve_role_valid_name_returns_spec() -> None:
    """resolve_role returns resolved spec for a valid reviewer name."""
    cfg = make_minimal_cfg()
    cfg["roles"]["plan-review"]["batch"]["reviewer"] = "sonnetmax"
    registry = make_minimal_registry()
    spec = _reviewers.resolve_role(cfg, registry, "plan-review", "batch")
    assert spec is not None
    assert spec["type"] == "single"
    assert spec["provider"] == "claude"
    print("PASS: resolve_role valid name returns spec")


def test_validate_role_refs_happy_path() -> None:
    """validate_role_refs passes when all reviewer names exist in registry."""
    cfg = make_minimal_cfg()
    cfg["roles"]["plan-review"]["batch"]["reviewer"] = "sonnetmax"
    cfg["roles"]["plan-review"]["holistic"]["reviewer"] = "sonnetmax"
    registry = make_minimal_registry()
    _reviewers.validate_role_refs(cfg, registry)  # must not raise
    print("PASS: validate_role_refs happy path")


def test_validate_role_refs_missing_raises() -> None:
    """validate_role_refs raises listing all missing reviewer names."""
    cfg = make_minimal_cfg()
    cfg["roles"]["plan-review"]["batch"]["reviewer"] = "typo-reviewer"
    cfg["roles"]["code-review"]["holistic"]["reviewer"] = "another-typo"
    registry = make_minimal_registry()
    try:
        _reviewers.validate_role_refs(cfg, registry)
        raise AssertionError("Expected ReviewerError")
    except ReviewerError as exc:
        msg = str(exc)
        assert "typo-reviewer" in msg
        assert "another-typo" in msg
    print("PASS: validate_role_refs lists all missing names")


def test_load_falls_back_to_reviewers_yaml() -> None:
    """load() succeeds when only legacy wiki/reviewers.yaml exists."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        hub_dir = tmp_path / "hub"
        hub_dir.mkdir()
        wiki_path = tmp_path / "wiki"
        wiki_path.mkdir()
        # Write legacy reviewers.yaml
        (wiki_path / "reviewers.yaml").write_text(
            "sonnetmax:\n  type: single\n  provider: claude\n  model: claude-sonnet-4-6\n"
        )
        with patch.object(
            _reviewers,
            "resolve_plugin_template_path",
            return_value=tmp_path / "nonexistent" / "mill-agents.yaml"
        ):
            with patch.object(_paths, "resolve_wiki_path", return_value=wiki_path):
                registry = _reviewers.load(hub_dir)

        assert "sonnetmax" in registry
    print("PASS: load falls back to reviewers.yaml")


def test_validate_role_refs_catches_bad_implementer_model() -> None:
    """validate_role_refs raises ReviewerError for bad roles.implementer.model."""
    registry = make_minimal_registry()
    cfg = {"roles": {"implementer": {"self_fix_rounds": 2, "model": "nonexistent_entry"}}}
    try:
        _reviewers.validate_role_refs(cfg, registry)
        raise AssertionError("Expected ReviewerError")
    except ReviewerError:
        pass
    print("PASS: validate_role_refs catches bad implementer model ref")


def test_validate_role_refs_catches_bad_fixer_model() -> None:
    """validate_role_refs raises ReviewerError for bad roles.fixer.model."""
    registry = make_minimal_registry()
    cfg = {"roles": {"fixer": {"model": "nonexistent_entry"}}}
    try:
        _reviewers.validate_role_refs(cfg, registry)
        raise AssertionError("Expected ReviewerError")
    except ReviewerError:
        pass
    print("PASS: validate_role_refs catches bad fixer model ref")


def test_load_plugin_template_only() -> None:
    """load() uses plugin template when no local override present."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        hub_dir = tmp_path / "hub"
        hub_dir.mkdir()
        # Mock plugin template with 2 entries
        template_content = (
            "sonnetmax:\n  type: single\n  provider: claude\n  model: claude-sonnet-4-6\n"
            "sonnetmedium:\n  type: single\n  provider: claude\n  model: claude-sonnet-4-6\n"
        )
        with patch.object(
            _reviewers,
            "resolve_plugin_template_path",
            return_value=tmp_path / "templates" / "mill-agents.yaml"
        ):
            (tmp_path / "templates").mkdir(exist_ok=True)
            (tmp_path / "templates" / "mill-agents.yaml").write_text(template_content)
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                registry = _reviewers.load(hub_dir)

        assert "sonnetmax" in registry
        assert "sonnetmedium" in registry
    print("PASS: load plugin template only")


def test_local_overlay_adds_new_agent() -> None:
    """load() merges plugin template and local overlay."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        hub_dir = tmp_path / "hub"
        hub_dir.mkdir()
        # Mock plugin template
        template_content = "agentA:\n  type: single\n  provider: claude\n  model: claude-sonnet-4-6\n"
        # Mock local overlay
        (hub_dir / ".millhouse").mkdir()
        (hub_dir / ".millhouse" / "agents.local.yaml").write_text(
            "agentB:\n  type: single\n  provider: claude\n  model: claude-opus-4-1\n"
        )
        with patch.object(
            _reviewers,
            "resolve_plugin_template_path",
            return_value=tmp_path / "templates" / "mill-agents.yaml"
        ):
            (tmp_path / "templates").mkdir(exist_ok=True)
            (tmp_path / "templates" / "mill-agents.yaml").write_text(template_content)
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                registry = _reviewers.load(hub_dir)

        assert "agentA" in registry
        assert "agentB" in registry
    print("PASS: load local overlay adds new agent")


def test_local_overlay_overrides_model() -> None:
    """load() deep-merges local overrides into plugin template."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        hub_dir = tmp_path / "hub"
        hub_dir.mkdir()
        # Mock plugin template
        template_content = (
            "agentA:\n  type: single\n  provider: claude\n  model: model-x\n"
        )
        # Mock local override that only changes the model
        (hub_dir / ".millhouse").mkdir()
        (hub_dir / ".millhouse" / "agents.local.yaml").write_text(
            "agentA:\n  model: model-y\n"
        )
        with patch.object(
            _reviewers,
            "resolve_plugin_template_path",
            return_value=tmp_path / "templates" / "mill-agents.yaml"
        ):
            (tmp_path / "templates").mkdir(exist_ok=True)
            (tmp_path / "templates" / "mill-agents.yaml").write_text(template_content)
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                registry = _reviewers.load(hub_dir)

        assert registry["agentA"]["model"] == "model-y"
        assert registry["agentA"]["provider"] == "claude"
    print("PASS: load local overlay overrides model")


def test_raises_when_nothing_found() -> None:
    """load() raises ReviewerError when no source is found."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        hub_dir = tmp_path / "hub"
        hub_dir.mkdir()
        # No template, no local, no wiki
        with patch.object(
            _reviewers,
            "resolve_plugin_template_path",
            return_value=tmp_path / "nonexistent" / "mill-agents.yaml"
        ):
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                try:
                    _reviewers.load(hub_dir)
                    raise AssertionError("Expected ReviewerError")
                except ReviewerError as exc:
                    assert "Missing registry" in str(exc)
    print("PASS: load raises when nothing found")


def test_extends_single_level() -> None:
    """Single-level extends: child inherits from base."""
    registry = _load_with_overlay(
        "base:\n"
        "  type: single\n"
        "  provider: claude\n"
        "  model: claude-sonnet-4-6\n"
        "child:\n"
        "  extends: base\n"
        "  tooluse: true\n",
    )
    assert registry["child"] == {
        "type": "single",
        "provider": "claude",
        "model": "claude-sonnet-4-6",
        "tooluse": True,
    }
    assert registry["base"] == {
        "type": "single",
        "provider": "claude",
        "model": "claude-sonnet-4-6",
    }
    print("PASS: extends single level")


def test_extends_multi_level() -> None:
    """Multi-level chain c -> b -> a resolves correctly."""
    registry = _load_with_overlay(
        "a:\n"
        "  type: single\n"
        "  provider: claude\n"
        "  model: claude-sonnet-4-6\n"
        "b:\n"
        "  extends: a\n"
        "c:\n"
        "  extends: b\n"
        "  tooluse: true\n",
    )
    assert registry["c"]["type"] == "single"
    assert registry["c"]["provider"] == "claude"
    assert registry["c"]["model"] == "claude-sonnet-4-6"
    assert registry["c"]["tooluse"] is True
    print("PASS: extends multi-level")


def test_extends_child_overrides_parent_scalar() -> None:
    """Child overrides parent scalar value."""
    registry = _load_with_overlay(
        "base:\n"
        "  type: single\n"
        "  provider: claude\n"
        "  model: foo\n"
        "child:\n"
        "  extends: base\n"
        "  model: bar\n",
    )
    assert registry["child"]["model"] == "bar"
    print("PASS: extends child overrides parent scalar")


def test_extends_unknown_base_raises() -> None:
    """Extends referencing unknown base raises ReviewerError."""
    try:
        _load_with_overlay(
            "child:\n"
            "  extends: nonexistent\n"
            "  type: single\n"
            "  provider: claude\n"
            "  model: x\n",
        )
        raise AssertionError("Expected ReviewerError")
    except ReviewerError as exc:
        assert "nonexistent" in str(exc)
    print("PASS: extends unknown base raises")


def test_extends_cycle_raises() -> None:
    """Cycle in extends chain raises ReviewerError."""
    try:
        _load_with_overlay(
            "a:\n"
            "  extends: b\n"
            "  type: single\n"
            "  provider: claude\n"
            "  model: x\n"
            "b:\n"
            "  extends: a\n"
            "  type: single\n"
            "  provider: claude\n"
            "  model: y\n",
        )
        raise AssertionError("Expected ReviewerError")
    except ReviewerError as exc:
        exc_str = str(exc)
        assert "Cycle detected" in exc_str
        assert "a" in exc_str
        assert "b" in exc_str
    print("PASS: extends cycle raises")


def test_extends_self_cycle_raises() -> None:
    """Self-loop in extends raises ReviewerError."""
    try:
        _load_with_overlay(
            "a:\n"
            "  extends: a\n"
            "  type: single\n"
            "  provider: claude\n"
            "  model: x\n",
        )
        raise AssertionError("Expected ReviewerError")
    except ReviewerError as exc:
        exc_str = str(exc)
        assert "Cycle detected" in exc_str
        assert "a -> a" in exc_str
    print("PASS: extends self-cycle raises")


def test_extends_target_must_not_be_cluster() -> None:
    """Extends cannot target a cluster entry."""
    try:
        _load_with_overlay(
            "x:\n"
            "  type: single\n"
            "  provider: claude\n"
            "  model: y\n"
            "my_cluster:\n"
            "  type: cluster\n"
            "  workers:\n"
            "    use: x\n"
            "    count: 1\n"
            "  handler:\n"
            "    use: x\n"
            "child:\n"
            "  extends: my_cluster\n"
            "  tooluse: true\n",
        )
        raise AssertionError("Expected ReviewerError")
    except ReviewerError as exc:
        exc_str = str(exc)
        assert "my_cluster" in exc_str
        assert "cluster" in exc_str
    print("PASS: extends target must not be cluster")


def test_cluster_cannot_extend() -> None:
    """Cluster entries cannot use extends."""
    try:
        _load_with_overlay(
            "a:\n"
            "  type: single\n"
            "  provider: claude\n"
            "  model: x\n"
            "my_cluster:\n"
            "  type: cluster\n"
            "  extends: a\n"
            "  workers:\n"
            "    use: a\n"
            "    count: 1\n"
            "  handler:\n"
            "    use: a\n",
        )
        raise AssertionError("Expected ReviewerError")
    except ReviewerError as exc:
        exc_str = str(exc)
        assert "my_cluster" in exc_str
        assert "cluster" in exc_str
    print("PASS: cluster cannot extend")


def test_required_field_missing_after_merge_raises() -> None:
    """Missing required field after merge is caught by validation."""
    try:
        _load_with_overlay(
            "base:\n"
            "  type: single\n"
            "  model: foo\n"
            "child:\n"
            "  extends: base\n",
        )
        raise AssertionError("Expected ReviewerError")
    except ReviewerError as exc:
        assert "provider" in str(exc)
    print("PASS: required field missing after merge raises")


def test_extends_field_removed_from_output() -> None:
    """The extends: field is removed from resolved output."""
    registry = _load_with_overlay(
        "a:\n"
        "  type: single\n"
        "  provider: claude\n"
        "  model: x\n"
        "b:\n"
        "  extends: a\n",
    )
    assert "extends" not in registry["b"]
    print("PASS: extends field removed from output")


def main() -> int:
    tests = [
        test_load_happy_path,
        test_load_raises_on_missing_file,
        test_load_raises_single_missing_provider,
        test_load_raises_cluster_missing_workers,
        test_load_raises_cluster_missing_handler,
        test_load_raises_cluster_workers_count_non_positive,
        test_load_raises_unknown_type,
        test_load_raises_invalid_name_uppercase,
        test_load_raises_invalid_name_dot,
        test_load_raises_duplicate_name,
        test_load_raises_cluster_use_nonexistent,
        test_load_raises_cluster_use_referencing_cluster,
        test_resolve_single_happy_path,
        test_resolve_cluster_happy_path,
        test_resolve_raises_missing_name,
        test_resolve_test_stub_special_case,
        test_resolve_role_null_reviewer_returns_none,
        test_resolve_role_rounds_zero_returns_none,
        test_resolve_role_valid_name_returns_spec,
        test_validate_role_refs_happy_path,
        test_validate_role_refs_missing_raises,
        test_load_falls_back_to_reviewers_yaml,
        test_validate_role_refs_catches_bad_implementer_model,
        test_validate_role_refs_catches_bad_fixer_model,
        test_extends_single_level,
        test_extends_multi_level,
        test_extends_child_overrides_parent_scalar,
        test_extends_unknown_base_raises,
        test_extends_cycle_raises,
        test_extends_self_cycle_raises,
        test_extends_target_must_not_be_cluster,
        test_cluster_cannot_extend,
        test_required_field_missing_after_merge_raises,
        test_extends_field_removed_from_output,
        # --- _reviewer_single tests merged from test-reviewer-single.py ---
        test_single_signature,
        test_single_cluster_spec_raises,
        test_single_test_stub_forwards_prompt,
        test_single_claude_bulk_mode,
        test_single_claude_tool_use_mode,
        test_single_gemini_bulk_mode,
        test_single_unknown_provider_raises,
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


# ---------------------------------------------------------------------------
# _reviewer_single tests (was test-reviewer-single.py).
# ---------------------------------------------------------------------------

def test_single_signature() -> None:
    sig = inspect.signature(_reviewer_single.run)
    params = sig.parameters
    assert "spec" in params
    assert "prompt_text" in params
    assert "session_id" in params and params["session_id"].default is None
    assert "resume" in params and params["resume"].default is False
    assert "timeout" in params and params["timeout"].default is None
    assert "effort" not in params, "run must not expose an effort kwarg — effort lives in the spec"
    print("PASS: _reviewer_single.run signature")


def test_single_cluster_spec_raises() -> None:
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


def test_single_test_stub_forwards_prompt() -> None:
    stub.seed([("# Review\n\n```yaml\nverdict: APPROVE\n```\n", "sid-001")])
    spec = {"type": "single", "provider": "test_stub", "tooluse": False}
    text, session_id = _reviewer_single.run(spec, "hello prompt", session_id="sid-001")
    assert "APPROVE" in text
    captured = stub.captured_prompts()
    assert len(captured) == 1
    assert captured[0][0] == "hello prompt"
    print("PASS: test_stub provider forwards prompt and returns seeded response")


def test_single_claude_bulk_mode() -> None:
    import _llm_claude as llm_claude
    calls: list[dict] = []

    def fake_run_bulk(prompt_text: str, **kwargs) -> tuple[str, str]:
        calls.append({"prompt_text": prompt_text, **kwargs})
        return ("bulk response", "sid-bulk")

    original = llm_claude.run_bulk
    llm_claude.run_bulk = fake_run_bulk
    try:
        spec = {
            "type": "single", "provider": "claude", "model": "claude-sonnet-4-6",
            "effort": "max", "tooluse": False,
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


def test_single_claude_tool_use_mode() -> None:
    import _llm_claude as llm_claude
    calls: list[dict] = []

    def fake_run_tool_use(prompt_text: str, **kwargs) -> tuple[str, str]:
        calls.append({"prompt_text": prompt_text, **kwargs})
        return ("tool response", "sid-tool")

    original = llm_claude.run_tool_use
    llm_claude.run_tool_use = fake_run_tool_use
    try:
        spec = {
            "type": "single", "provider": "claude", "model": "claude-sonnet-4-6",
            "effort": "max", "tooluse": True,
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


def test_single_gemini_bulk_mode() -> None:
    import _llm_gemini as llm_gemini
    calls: list[dict] = []

    def fake_run_bulk(prompt_text: str, **kwargs) -> tuple[str, str]:
        calls.append({"prompt_text": prompt_text, **kwargs})
        return ("gemini bulk response", "sid-gemini-bulk")

    original = llm_gemini.run_bulk
    llm_gemini.run_bulk = fake_run_bulk
    try:
        spec = {
            "type": "single", "provider": "gemini", "model": "gemini-2.5-flash",
            "effort": None, "tooluse": False,
        }
        text, sid = _reviewer_single.run(spec, "test prompt", session_id="abc")
        assert text == "gemini bulk response"
        assert len(calls) == 1
        assert calls[0]["model"] == "gemini-2.5-flash"
    finally:
        llm_gemini.run_bulk = original
    print("PASS: gemini bulk mode calls run_bulk with model")


def test_single_unknown_provider_raises() -> None:
    spec = {
        "type": "single", "provider": "unk_provider_xyz", "model": "some-model",
        "effort": "medium", "tooluse": False,
    }
    try:
        _reviewer_single.run(spec, "test prompt")
        raise AssertionError("Expected ReviewerError")
    except ReviewerError as exc:
        assert "Unknown provider" in str(exc)
        assert "unk_provider_xyz" in str(exc)
    print("PASS: unknown provider raises ReviewerError")


if __name__ == "__main__":
    sys.exit(main())
