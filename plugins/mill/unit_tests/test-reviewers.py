"""Unit tests for _reviewers.py: load, resolve, resolve_role, validate_role_refs."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))
sys.path.insert(0, str(HUB / "plugins" / "mill" / "unit_tests"))

import _reviewers  # noqa: E402
from _reviewers import ReviewerError  # noqa: E402
from _test_cfg import make_minimal_cfg  # noqa: E402
from _test_registry import make_minimal_registry, write_to  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_yaml(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_load_happy_path() -> None:
    """load() round-trips a valid reviewers.yaml."""
    with tempfile.TemporaryDirectory() as tmp:
        wiki = Path(tmp) / "wiki"
        write_to(wiki)
        registry = _reviewers.load(wiki)
        assert "sonnetmax" in registry
        assert registry["sonnetmax"]["type"] == "single"
        assert registry["sonnetmax"]["provider"] == "claude"
        assert "sonnetmax_tool" in registry
        assert registry["sonnetmax_tool"]["tooluse"] is True
    print("PASS: load happy path round-trips")


def test_load_raises_on_missing_file() -> None:
    """load() raises ReviewerError when reviewers.yaml is absent."""
    with tempfile.TemporaryDirectory() as tmp:
        wiki = Path(tmp) / "wiki"
        wiki.mkdir()
        try:
            _reviewers.load(wiki)
            raise AssertionError("Expected ReviewerError")
        except ReviewerError as exc:
            assert "Missing registry" in str(exc)
    print("PASS: load raises on missing file")


def test_load_raises_single_missing_provider() -> None:
    """load() raises when a single entry is missing 'provider'."""
    with tempfile.TemporaryDirectory() as tmp:
        wiki = Path(tmp) / "wiki"
        _write_yaml(
            wiki / "agents.yaml",
            "bad:\n  type: single\n  model: claude-sonnet-4-6\n",
        )
        try:
            _reviewers.load(wiki)
            raise AssertionError("Expected ReviewerError")
        except ReviewerError as exc:
            assert "provider" in str(exc)
    print("PASS: load raises single missing provider")


def test_load_raises_cluster_missing_workers() -> None:
    """load() raises when a cluster entry is missing 'workers'."""
    with tempfile.TemporaryDirectory() as tmp:
        wiki = Path(tmp) / "wiki"
        _write_yaml(
            wiki / "agents.yaml",
            "myworker:\n  type: single\n  provider: claude\n  model: claude-sonnet-4-6\n"
            "mycluster:\n  type: cluster\n  handler:\n    use: myworker\n",
        )
        try:
            _reviewers.load(wiki)
            raise AssertionError("Expected ReviewerError")
        except ReviewerError as exc:
            assert "workers" in str(exc)
    print("PASS: load raises cluster missing workers")


def test_load_raises_cluster_missing_handler() -> None:
    """load() raises when a cluster entry is missing 'handler'."""
    with tempfile.TemporaryDirectory() as tmp:
        wiki = Path(tmp) / "wiki"
        _write_yaml(
            wiki / "agents.yaml",
            "myworker:\n  type: single\n  provider: claude\n  model: claude-sonnet-4-6\n"
            "mycluster:\n  type: cluster\n  workers:\n    use: myworker\n    count: 2\n",
        )
        try:
            _reviewers.load(wiki)
            raise AssertionError("Expected ReviewerError")
        except ReviewerError as exc:
            assert "handler" in str(exc)
    print("PASS: load raises cluster missing handler")


def test_load_raises_cluster_workers_count_non_positive() -> None:
    """load() raises when cluster workers.count is not a positive integer."""
    with tempfile.TemporaryDirectory() as tmp:
        wiki = Path(tmp) / "wiki"
        _write_yaml(
            wiki / "agents.yaml",
            "myworker:\n  type: single\n  provider: claude\n  model: claude-sonnet-4-6\n"
            "mycluster:\n  type: cluster\n"
            "  workers:\n    use: myworker\n    count: 0\n"
            "  handler:\n    use: myworker\n",
        )
        try:
            _reviewers.load(wiki)
            raise AssertionError("Expected ReviewerError")
        except ReviewerError as exc:
            assert "count" in str(exc)
    print("PASS: load raises cluster workers.count non-positive")


def test_load_raises_unknown_type() -> None:
    """load() raises on unknown reviewer type."""
    with tempfile.TemporaryDirectory() as tmp:
        wiki = Path(tmp) / "wiki"
        _write_yaml(
            wiki / "agents.yaml",
            "bad:\n  type: unknown\n  provider: claude\n  model: x\n",
        )
        try:
            _reviewers.load(wiki)
            raise AssertionError("Expected ReviewerError")
        except ReviewerError as exc:
            assert "unknown" in str(exc).lower() or "type" in str(exc)
    print("PASS: load raises unknown type")


def test_load_raises_invalid_name_uppercase() -> None:
    """load() raises on names with uppercase letters."""
    with tempfile.TemporaryDirectory() as tmp:
        wiki = Path(tmp) / "wiki"
        _write_yaml(
            wiki / "agents.yaml",
            "BadName:\n  type: single\n  provider: claude\n  model: x\n",
        )
        try:
            _reviewers.load(wiki)
            raise AssertionError("Expected ReviewerError")
        except ReviewerError as exc:
            assert "BadName" in str(exc) or "Invalid" in str(exc)
    print("PASS: load raises invalid name (uppercase)")


def test_load_raises_invalid_name_dot() -> None:
    """load() raises on names containing a dot."""
    with tempfile.TemporaryDirectory() as tmp:
        wiki = Path(tmp) / "wiki"
        _write_yaml(
            wiki / "agents.yaml",
            "bad.name:\n  type: single\n  provider: claude\n  model: x\n",
        )
        try:
            _reviewers.load(wiki)
            raise AssertionError("Expected ReviewerError")
        except ReviewerError as exc:
            assert "bad.name" in str(exc) or "Invalid" in str(exc)
    print("PASS: load raises invalid name (dot)")


def test_load_raises_duplicate_name() -> None:
    """load() raises when the same name appears twice in the file."""
    with tempfile.TemporaryDirectory() as tmp:
        wiki = Path(tmp) / "wiki"
        _write_yaml(
            wiki / "agents.yaml",
            "sonnetmax:\n  type: single\n  provider: claude\n  model: x\n"
            "sonnetmax:\n  type: single\n  provider: claude\n  model: y\n",
        )
        try:
            _reviewers.load(wiki)
            raise AssertionError("Expected ReviewerError")
        except ReviewerError as exc:
            assert "sonnetmax" in str(exc) or "Duplicate" in str(exc)
    print("PASS: load raises duplicate name")


def test_load_raises_cluster_use_nonexistent() -> None:
    """load() raises when a cluster use: references a non-existent name."""
    with tempfile.TemporaryDirectory() as tmp:
        wiki = Path(tmp) / "wiki"
        _write_yaml(
            wiki / "agents.yaml",
            "myworker:\n  type: single\n  provider: claude\n  model: x\n"
            "mycluster:\n  type: cluster\n"
            "  workers:\n    use: nonexistent\n    count: 2\n"
            "  handler:\n    use: myworker\n",
        )
        try:
            _reviewers.load(wiki)
            raise AssertionError("Expected ReviewerError")
        except ReviewerError as exc:
            assert "nonexistent" in str(exc)
    print("PASS: load raises cluster use referencing nonexistent name")


def test_load_raises_cluster_use_referencing_cluster() -> None:
    """load() raises when a cluster use: references another cluster."""
    with tempfile.TemporaryDirectory() as tmp:
        wiki = Path(tmp) / "wiki"
        _write_yaml(
            wiki / "agents.yaml",
            "myworker:\n  type: single\n  provider: claude\n  model: x\n"
            "clusterb:\n  type: cluster\n"
            "  workers:\n    use: myworker\n    count: 2\n"
            "  handler:\n    use: myworker\n"
            "clustera:\n  type: cluster\n"
            "  workers:\n    use: clusterb\n    count: 3\n"
            "  handler:\n    use: myworker\n",
        )
        try:
            _reviewers.load(wiki)
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
    """load() succeeds when only reviewers.yaml exists (backward compat)."""
    with tempfile.TemporaryDirectory() as tmp:
        wiki = Path(tmp) / "wiki"
        write_to(wiki)  # writes agents.yaml
        (wiki / "agents.yaml").rename(wiki / "reviewers.yaml")
        registry = _reviewers.load(wiki)
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
