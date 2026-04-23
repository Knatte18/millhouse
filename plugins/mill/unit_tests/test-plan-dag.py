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
    topo_order,
    validate,
)


def test_good_plan_accepted() -> None:
    good = """
```yaml
batches:
  - name: a
    file: 01-a.md
    depends-on: []
    verify: pytest tests/a -q
  - name: b
    file: 02-b.md
    depends-on: [a]
    verify: null
  - name: c
    file: 03-c.md
    depends-on: [a]
    verify: null
  - name: d
    file: 04-d.md
    depends-on: [b, c]
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
        commands = iter_batch_verifies(plan_dir)
        assert commands == [
            ("a", "pytest tests/a -q"),
            ("b", "pytest tests/b -q"),
        ], commands
        print(f"PASS: iter_batch_verifies yields non-null verifies in DAG order -- {commands}")


def main() -> int:
    try:
        test_good_plan_accepted()
        test_cycle_rejected()
        test_unknown_dep_rejected()
        test_orphan_file_rejected()
        test_missing_block_rejected()
        test_topo_order()
        test_iter_batch_verifies()
        print("All _plan_dag unit tests passed.")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
