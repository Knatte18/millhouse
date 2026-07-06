"""Unit tests for plugins/mill/scripts/_plan_dag.py.

The fixtures below are intentionally throwaway dummy data — they do NOT
reflect what mill-plan will actually name batches in real plans.
_plan_dag has no knowledge of specific batch names; it parses whatever
the overview declares.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _plan_dag import (  # noqa: E402
    PlanDAGError,
    extract_batch_index,
    iter_batch_verifies,
    parse_verify_field,
    topo_order,
    validate,
)


def test_good_plan_accepted() -> None:
    good = """
```yaml
batches:
  - number: 1
    name: a
    file: 01-a.md
    depends-on: []
    verify: pytest tests/a -q
  - number: 2
    name: b
    file: 02-b.md
    depends-on: [1]
    verify: null
  - number: 3
    name: c
    file: 03-c.md
    depends-on: [1]
    verify: null
  - number: 4
    name: d
    file: 04-d.md
    depends-on: [2, 3]
    verify: pytest tests/d -q
```
"""
    batches = extract_batch_index(good)
    validate(batches, ["01-a.md", "02-b.md", "03-c.md", "04-d.md"])
    print("PASS: good plan accepted")


def test_cycle_rejected() -> None:
    cycle = """
```yaml
batches:
  - name: a
    file: 01-a.md
    depends-on: [b]
  - name: b
    file: 02-b.md
    depends-on: [a]
```
"""
    batches = extract_batch_index(cycle)
    try:
        validate(batches, ["01-a.md", "02-b.md"])
    except PlanDAGError as exc:
        assert "Cycle" in str(exc), str(exc)
        print(f"PASS: cycle rejected -- {exc}")
        return
    raise AssertionError("cycle was not rejected")


def test_unknown_dep_rejected() -> None:
    unknown = """
```yaml
batches:
  - name: a
    file: 01-a.md
    depends-on: [ghost]
```
"""
    batches = extract_batch_index(unknown)
    try:
        validate(batches, ["01-a.md"])
    except PlanDAGError as exc:
        assert "unknown batch" in str(exc), str(exc)
        print(f"PASS: unknown dep rejected -- {exc}")
        return
    raise AssertionError("unknown dep was not rejected")


def test_orphan_file_rejected() -> None:
    orphan = """
```yaml
batches:
  - name: a
    file: 01-a.md
    depends-on: []
```
"""
    batches = extract_batch_index(orphan)
    try:
        validate(batches, ["01-a.md", "99-orphan.md"])
    except PlanDAGError as exc:
        assert "not listed" in str(exc), str(exc)
        print(f"PASS: orphan file rejected -- {exc}")
        return
    raise AssertionError("orphan file was not rejected")


def test_missing_block_rejected() -> None:
    try:
        extract_batch_index("no yaml here")
    except PlanDAGError as exc:
        assert "missing" in str(exc), str(exc)
        print(f"PASS: missing block rejected -- {exc}")
        return
    raise AssertionError("missing block was not rejected")


def test_topo_order() -> None:
    order = topo_order([
        {"name": "a", "depends-on": []},
        {"name": "b", "depends-on": ["a"]},
        {"name": "c", "depends-on": ["a"]},
        {"name": "d", "depends-on": ["b", "c"]},
    ])
    assert order.index("a") < order.index("b")
    assert order.index("a") < order.index("c")
    assert order.index("b") < order.index("d")
    assert order.index("c") < order.index("d")
    # Authored-order tie-break: b (2nd authored) precedes c (3rd).
    assert order.index("b") < order.index("c")
    print(f"PASS: topo_order respects dependencies and authored order -- {order}")


def test_iter_batch_verifies() -> None:
    with tempfile.TemporaryDirectory() as td:
        plan_dir = Path(td)
        # Flat layout fixture: hub_root == git_root == plan_dir's parent,
        # matching the Shared Decision that flat-layout output must stay
        # byte-identical after the verify-cwd mapping form was introduced.
        hub_root = plan_dir.parent
        git_root = plan_dir.parent
        (plan_dir / "00-overview.md").write_text(
            "```yaml\n"
            "batches:\n"
            "  - name: a\n"
            "    file: 01-a.md\n"
            "    depends-on: []\n"
            "  - name: b\n"
            "    file: 02-b.md\n"
            "    depends-on: [a]\n"
            "  - name: c\n"
            "    file: 03-c.md\n"
            "    depends-on: [a]\n"
            "```\n",
            encoding="utf-8",
        )
        (plan_dir / "01-a.md").write_text(
            "# Batch: a\n\n```yaml\nbatch: a\nverify: pytest tests/a -q\n```\n",
            encoding="utf-8",
        )
        (plan_dir / "02-b.md").write_text(
            "# Batch: b\n\n```yaml\nbatch: b\nverify: pytest tests/b -q\n```\n",
            encoding="utf-8",
        )
        (plan_dir / "03-c.md").write_text(
            "# Batch: c\n\n```yaml\nbatch: c\nverify: null\n```\n",
            encoding="utf-8",
        )
        commands = iter_batch_verifies(plan_dir, hub_root, git_root)
        assert commands == [
            ("a", "pytest tests/a -q", None),
            ("b", "pytest tests/b -q", None),
        ], commands
        print(
            f"PASS: iter_batch_verifies yields non-null verifies in DAG order -- {commands}"
        )


def test_parse_verify_field() -> None:
    hub_root = Path("/hub")
    git_root = Path("/hub/nested/git")

    # Plain-string form: no cwd opinion -- caller keeps its existing default.
    command, cwd = parse_verify_field(
        {"verify": "pytest tests/a -q"}, hub_root, git_root
    )
    assert (command, cwd) == ("pytest tests/a -q", None), (command, cwd)

    # Mapping form with cwd: hub -- resolves to hub_root.
    command, cwd = parse_verify_field(
        {"verify": {"cwd": "hub", "command": "pytest tests/a -q"}}, hub_root, git_root
    )
    assert (command, cwd) == ("pytest tests/a -q", hub_root), (command, cwd)

    # Mapping form with cwd: git_root -- resolves to git_root.
    command, cwd = parse_verify_field(
        {"verify": {"cwd": "git_root", "command": "pytest tests/a -q"}},
        hub_root,
        git_root,
    )
    assert (command, cwd) == ("pytest tests/a -q", git_root), (command, cwd)

    # Unrecognized cwd value raises ValueError (fail loud, no silent default).
    try:
        parse_verify_field(
            {"verify": {"cwd": "somewhere", "command": "pytest tests/a -q"}},
            hub_root,
            git_root,
        )
        raise AssertionError("unrecognized cwd was not rejected")
    except ValueError as exc:
        assert "cwd" in str(exc), str(exc)

    # Missing cwd on the mapping form also raises -- mapping form has no
    # implicit default, unlike the plain-string form.
    try:
        parse_verify_field(
            {"verify": {"command": "pytest tests/a -q"}}, hub_root, git_root
        )
        raise AssertionError("missing cwd was not rejected")
    except ValueError as exc:
        assert "cwd" in str(exc), str(exc)

    # Mapping missing `command:` raises ValueError.
    try:
        parse_verify_field({"verify": {"cwd": "hub"}}, hub_root, git_root)
        raise AssertionError("missing command was not rejected")
    except ValueError as exc:
        assert "command" in str(exc), str(exc)

    # Absent, None, and empty/whitespace-only verify all normalize to
    # (None, None) -- "nothing to run".
    assert parse_verify_field({}, hub_root, git_root) == (None, None)
    assert parse_verify_field({"verify": None}, hub_root, git_root) == (None, None)
    assert parse_verify_field({"verify": ""}, hub_root, git_root) == (None, None)
    assert parse_verify_field({"verify": "   "}, hub_root, git_root) == (None, None)

    print("PASS: parse_verify_field covers string, mapping, and error cases")


def test_good_plan_with_numbers_accepted() -> None:
    text = """
```yaml
batches:
  - number: 1
    name: a
    file: 01-a.md
    depends-on: []
  - number: 2
    name: b
    file: 02-b.md
    depends-on: [1]
```
"""
    batches = extract_batch_index(text)
    validate(batches, ["01-a.md", "02-b.md"])
    order = topo_order(batches)
    assert order == ["a", "b"], f"expected ['a', 'b'], got {order}"
    print(f"PASS: good plan with numbers accepted -- {order}")


def test_number_dep_unknown_rejected() -> None:
    text = """
```yaml
batches:
  - number: 1
    name: a
    file: 01-a.md
    depends-on: [99]
```
"""
    batches = extract_batch_index(text)
    try:
        validate(batches, ["01-a.md"])
    except PlanDAGError as exc:
        assert "unknown batch number 99" in str(exc), str(exc)
        print(f"PASS: unknown number dep rejected -- {exc}")
        return
    raise AssertionError("unknown number dep was not rejected")


def test_number_dep_duplicate_rejected() -> None:
    text = """
```yaml
batches:
  - number: 1
    name: a
    file: 01-a.md
    depends-on: []
  - number: 1
    name: b
    file: 02-b.md
    depends-on: []
```
"""
    batches = extract_batch_index(text)
    try:
        validate(batches, ["01-a.md", "02-b.md"])
    except PlanDAGError as exc:
        assert "Duplicate batch number" in str(exc), str(exc)
        print(f"PASS: duplicate batch number rejected -- {exc}")
        return
    raise AssertionError("duplicate batch number was not rejected")


def test_mixed_dep_type_rejected() -> None:
    text = """
```yaml
batches:
  - number: 1
    name: a
    file: 01-a.md
    depends-on: [1, "other"]
```
"""
    batches = extract_batch_index(text)
    try:
        validate(batches, ["01-a.md"])
    except PlanDAGError as exc:
        assert "mix" in str(exc).lower(), str(exc)
        print(f"PASS: mixed dep types rejected -- {exc}")
        return
    raise AssertionError("mixed dep types were not rejected")


def test_old_name_deps_still_valid() -> None:
    text = """
```yaml
batches:
  - name: a
    file: 01-a.md
    depends-on: []
  - name: b
    file: 02-b.md
    depends-on: [a]
```
"""
    batches = extract_batch_index(text)
    validate(batches, ["01-a.md", "02-b.md"])
    print("PASS: old string name deps still valid (backward compat)")


def main() -> int:
    try:
        test_good_plan_accepted()
        test_cycle_rejected()
        test_unknown_dep_rejected()
        test_orphan_file_rejected()
        test_missing_block_rejected()
        test_topo_order()
        test_iter_batch_verifies()
        test_parse_verify_field()
        test_good_plan_with_numbers_accepted()
        test_number_dep_unknown_rejected()
        test_number_dep_duplicate_rejected()
        test_mixed_dep_type_rejected()
        test_old_name_deps_still_valid()
        print("All _plan_dag unit tests passed.")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
