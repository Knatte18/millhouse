"""Unit tests for plugins/mill/scripts/_plan_dag.py.

The fixtures below are intentionally throwaway dummy data — they do NOT reflect what mill-plan will
actually name batches in real plans. _plan_dag has no knowledge of specific batch names;
it parses whatever the overview declares.
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
    parse_commit_none_card_ids,
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
        # Flat layout fixture: hub_root == git_root == plan_dir's parent, matching the Shared Decision that flat-layout output must stay byte-identical after the verify-cwd mapping form was introduced.
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

    # Missing cwd on the mapping form also raises -- mapping form has no implicit default, unlike the plain-string form.
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

    # Absent, None, and empty/whitespace-only verify all normalize to (None, None) -- "nothing to run".
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


def test_parse_commit_none_card_ids_real_message_returns_empty_set() -> None:
    text = """
### Card 1: do something

- **Commit:** feat(x): real commit message
"""
    assert parse_commit_none_card_ids(text) == set()
    print("PASS: parse_commit_none_card_ids ignores a real commit message")


def test_parse_commit_none_card_ids_none_sentinel_included() -> None:
    text = """
### Card 1: verify earlier work

- **Commit:** none
"""
    assert parse_commit_none_card_ids(text) == {1}
    print("PASS: parse_commit_none_card_ids includes a lowercase none sentinel")


def test_parse_commit_none_card_ids_mixed_case_included() -> None:
    for sentinel in ("None", "NONE"):
        text = f"""
### Card 1: verify earlier work

- **Commit:** {sentinel}
"""
        assert parse_commit_none_card_ids(text) == {1}, sentinel
    print("PASS: parse_commit_none_card_ids matches Commit: none case-insensitively")


def test_parse_commit_none_card_ids_only_middle_card_none() -> None:
    text = """
### Card 1: first

- **Commit:** feat(a): first card

### Card 2: verify earlier work

- **Commit:** none

### Card 3: third

- **Commit:** feat(c): third card
"""
    assert parse_commit_none_card_ids(text) == {2}
    print("PASS: parse_commit_none_card_ids picks out only the none card among three")


def test_parse_commit_none_card_ids_missing_field_not_included() -> None:
    text = """
### Card 1: missing commit field entirely

- **Context:** none
"""
    assert parse_commit_none_card_ids(text) == set()
    print("PASS: parse_commit_none_card_ids excludes a card with no Commit: line")


# ---------------------------------------------------------------------------
# Cross-batch verify-suppression fixtures (iter_batch_verifies Card 3/4) These fixtures write real batch markdown files (not just the overview's yaml block) because the suppression logic under test reads each batch file's own ``- **Deletes:**`` / ``- **Moves:**`` bullets, not just its fenced-yaml frontmatter.
# ---------------------------------------------------------------------------


def _write_overview(plan_dir: Path, batches_yaml_body: str) -> None:
    (plan_dir / "00-overview.md").write_text(
        f"```yaml\nbatches:\n{batches_yaml_body}```\n", encoding="utf-8"
    )


def _write_batch(
    plan_dir: Path,
    filename: str,
    *,
    name: str,
    verify: str,
    deletes: str | None = None,
) -> None:
    """Write a batch markdown file with a fenced-yaml ``verify:`` frontmatter and an optional ``-
    **Deletes:**`` bullet (inline, backtick-quoted).
"""
    lines = [f"# Batch: {name}", "", "```yaml", f"batch: {name}", verify, "```", ""]
    if deletes is not None:
        lines.append(f"- **Deletes:** `{deletes}`")
        lines.append("")
    (plan_dir / filename).write_text("\n".join(lines), encoding="utf-8")


def test_iter_batch_verifies_suppresses_target_removed_by_later_batch() -> None:
    # #689's exact fixture: batches 1-3 build the same package, batch 4 deletes that package's directory and builds everything else instead.
    # Only batch 4's triple should survive.
    with tempfile.TemporaryDirectory() as td:
        plan_dir = Path(td)
        hub_root = plan_dir.parent
        git_root = plan_dir.parent
        _write_overview(
            plan_dir,
            "  - name: batch1\n"
            "    file: 01-batch1.md\n"
            "    depends-on: []\n"
            "  - name: batch2\n"
            "    file: 02-batch2.md\n"
            "    depends-on: [batch1]\n"
            "  - name: batch3\n"
            "    file: 03-batch3.md\n"
            "    depends-on: [batch2]\n"
            "  - name: batch4\n"
            "    file: 04-batch4.md\n"
            "    depends-on: [batch1, batch2, batch3]\n",
        )
        _write_batch(
            plan_dir,
            "01-batch1.md",
            name="batch1",
            verify="verify: go build ./tools/x/",
        )
        _write_batch(
            plan_dir,
            "02-batch2.md",
            name="batch2",
            verify="verify: go build ./tools/x/",
        )
        _write_batch(
            plan_dir,
            "03-batch3.md",
            name="batch3",
            verify="verify: go build ./tools/x/",
        )
        _write_batch(
            plan_dir,
            "04-batch4.md",
            name="batch4",
            verify="verify: go build ./...",
            deletes="tools/x/",
        )
        commands = iter_batch_verifies(plan_dir, hub_root, git_root)
        assert commands == [("batch4", "go build ./...", None)], commands
        print(
            "PASS: iter_batch_verifies suppresses batches 1-3, keeps batch 4 -- "
            f"{commands}"
        )


def test_iter_batch_verifies_self_delete_not_suppressed() -> None:
    # A batch that deletes a path its own verify: references must NOT be suppressed -- only strictly-later removals count.
    with tempfile.TemporaryDirectory() as td:
        plan_dir = Path(td)
        hub_root = plan_dir.parent
        git_root = plan_dir.parent
        _write_overview(
            plan_dir,
            "  - name: a\n    file: 01-a.md\n    depends-on: []\n",
        )
        _write_batch(
            plan_dir,
            "01-a.md",
            name="a",
            verify="verify: go build ./tools/x/",
            deletes="tools/x/",
        )
        commands = iter_batch_verifies(plan_dir, hub_root, git_root)
        assert commands == [("a", "go build ./tools/x/", None)], commands
        print(f"PASS: self-delete does not suppress own verify -- {commands}")


def test_iter_batch_verifies_tokenizer_edge_cases_not_spuriously_matched() -> None:
    # Ellipsis/glob-style Go build targets and flag-form tokens must never be treated as path candidates, even against a maximally-tempting later Deletes: set.
    with tempfile.TemporaryDirectory() as td:
        plan_dir = Path(td)
        hub_root = plan_dir.parent
        git_root = plan_dir.parent
        _write_overview(
            plan_dir,
            "  - name: a\n"
            "    file: 01-a.md\n"
            "    depends-on: []\n"
            "  - name: b\n"
            "    file: 02-b.md\n"
            "    depends-on: []\n"
            "  - name: c\n"
            "    file: 03-c.md\n"
            "    depends-on: []\n"
            "  - name: z\n"
            "    file: 04-z.md\n"
            "    depends-on: [a, b, c]\n",
        )
        _write_batch(plan_dir, "01-a.md", name="a", verify="verify: go build ./...")
        _write_batch(
            plan_dir, "02-b.md", name="b", verify="verify: go test ./pkg/..."
        )
        _write_batch(
            plan_dir, "03-c.md", name="c", verify="verify: mytool --dir=foo/bar"
        )
        _write_batch(plan_dir, "04-z.md", name="z", verify="verify: null")
        commands = iter_batch_verifies(plan_dir, hub_root, git_root)
        assert commands == [
            ("a", "go build ./...", None),
            ("b", "go test ./pkg/...", None),
            ("c", "mytool --dir=foo/bar", None),
        ], commands
        print(f"PASS: tokenizer edge cases not spuriously matched -- {commands}")


def test_iter_batch_verifies_directory_containment_not_suppressed() -> None:
    # Exact-match only, no directory-containment: Deletes: tools/x/ must NOT suppress a verify referencing tools/x/cmd/app.
    with tempfile.TemporaryDirectory() as td:
        plan_dir = Path(td)
        hub_root = plan_dir.parent
        git_root = plan_dir.parent
        _write_overview(
            plan_dir,
            "  - name: a\n"
            "    file: 01-a.md\n"
            "    depends-on: []\n"
            "  - name: b\n"
            "    file: 02-b.md\n"
            "    depends-on: [a]\n",
        )
        _write_batch(
            plan_dir,
            "01-a.md",
            name="a",
            verify="verify: go build ./tools/x/cmd/app",
        )
        _write_batch(
            plan_dir,
            "02-b.md",
            name="b",
            verify="verify: go build ./...",
            deletes="tools/x/",
        )
        commands = iter_batch_verifies(plan_dir, hub_root, git_root)
        assert commands == [
            ("a", "go build ./tools/x/cmd/app", None),
            ("b", "go build ./...", None),
        ], commands
        print(f"PASS: directory-containment not suppressed (exact-match only) -- {commands}")


def test_iter_batch_verifies_multi_target_existential_suppression() -> None:
    # A multi-target command is fully suppressed if any single target matches -- including a still-valid second target.
    with tempfile.TemporaryDirectory() as td:
        plan_dir = Path(td)
        hub_root = plan_dir.parent
        git_root = plan_dir.parent
        _write_overview(
            plan_dir,
            "  - name: a\n"
            "    file: 01-a.md\n"
            "    depends-on: []\n"
            "  - name: b\n"
            "    file: 02-b.md\n"
            "    depends-on: [a]\n",
        )
        _write_batch(
            plan_dir,
            "01-a.md",
            name="a",
            verify="verify: go build ./tools/x ./tools/y",
        )
        _write_batch(
            plan_dir,
            "02-b.md",
            name="b",
            verify="verify: go build ./...",
            deletes="tools/x/",
        )
        commands = iter_batch_verifies(plan_dir, hub_root, git_root)
        assert commands == [("b", "go build ./...", None)], commands
        print(
            "PASS: multi-target command fully suppressed by one matching "
            f"target -- {commands}"
        )


def test_iter_batch_verifies_coordinate_space_mismatch_not_suppressed() -> None:
    # A mapping-form verify: {cwd: ..., command: ...} authored under a different coordinate space than a later Deletes: token degrades to "still runs" -- purely lexical matching, no root resolution.
    with tempfile.TemporaryDirectory() as td:
        plan_dir = Path(td)
        hub_root = plan_dir.parent
        git_root = plan_dir.parent
        _write_overview(
            plan_dir,
            "  - name: a\n"
            "    file: 01-a.md\n"
            "    depends-on: []\n"
            "  - name: b\n"
            "    file: 02-b.md\n"
            "    depends-on: [a]\n",
        )
        (plan_dir / "01-a.md").write_text(
            "# Batch: a\n\n"
            "```yaml\n"
            "batch: a\n"
            "verify:\n"
            "  cwd: git_root\n"
            "  command: go build ./tools/x/\n"
            "```\n",
            encoding="utf-8",
        )
        _write_batch(
            plan_dir,
            "02-b.md",
            name="b",
            verify="verify: go build ./...",
            deletes="nested/tools/x/",
        )
        commands = iter_batch_verifies(plan_dir, hub_root, git_root)
        assert commands == [
            ("a", "go build ./tools/x/", git_root),
            ("b", "go build ./...", None),
        ], commands
        print(
            "PASS: coordinate-space mismatch not suppressed (lexical only) -- "
            f"{commands}"
        )


def test_iter_batch_verifies_status_path_mixed_states() -> None:
    # Only "approved" batches' triples are returned when status_path is passed; omitting status_path stays byte-for-byte unchanged.
    with tempfile.TemporaryDirectory() as td:
        plan_dir = Path(td)
        hub_root = plan_dir.parent
        git_root = plan_dir.parent
        _write_overview(
            plan_dir,
            "  - name: a\n"
            "    file: 01-a.md\n"
            "    depends-on: []\n"
            "  - name: b\n"
            "    file: 02-b.md\n"
            "    depends-on: []\n"
            "  - name: c\n"
            "    file: 03-c.md\n"
            "    depends-on: []\n",
        )
        _write_batch(plan_dir, "01-a.md", name="a", verify="verify: pytest tests/a -q")
        _write_batch(plan_dir, "02-b.md", name="b", verify="verify: pytest tests/b -q")
        _write_batch(plan_dir, "03-c.md", name="c", verify="verify: pytest tests/c -q")

        status_path = plan_dir / "status.md"
        status_path.write_text(
            "## Batches\n\n"
            "```yaml\n"
            "batches:\n"
            "  - name: a\n"
            "    state: approved\n"
            "  - name: b\n"
            "    state: pending\n"
            "```\n",
            encoding="utf-8",
        )
        # c is absent from the status.md batches list entirely.

        without_status = iter_batch_verifies(plan_dir, hub_root, git_root)
        assert without_status == [
            ("a", "pytest tests/a -q", None),
            ("b", "pytest tests/b -q", None),
            ("c", "pytest tests/c -q", None),
        ], without_status

        with_status = iter_batch_verifies(
            plan_dir, hub_root, git_root, status_path=status_path
        )
        assert with_status == [("a", "pytest tests/a -q", None)], with_status
        print(
            "PASS: status_path gates to approved-only, omitted stays "
            f"unchanged -- without={without_status} with={with_status}"
        )


def test_iter_batch_verifies_no_batches_section_with_status_path_returns_empty() -> (
    None
):
    with tempfile.TemporaryDirectory() as td:
        plan_dir = Path(td)
        hub_root = plan_dir.parent
        git_root = plan_dir.parent
        _write_overview(
            plan_dir,
            "  - name: a\n    file: 01-a.md\n    depends-on: []\n",
        )
        _write_batch(plan_dir, "01-a.md", name="a", verify="verify: pytest tests/a -q")

        status_path = plan_dir / "status.md"
        status_path.write_text("## Task\n\nnothing here.\n", encoding="utf-8")

        commands = iter_batch_verifies(
            plan_dir, hub_root, git_root, status_path=status_path
        )
        assert commands == [], commands
        print("PASS: no ## Batches section with status_path returns []")


def test_iter_batch_verifies_malformed_batches_block_returns_empty() -> None:
    with tempfile.TemporaryDirectory() as td:
        plan_dir = Path(td)
        hub_root = plan_dir.parent
        git_root = plan_dir.parent
        _write_overview(
            plan_dir,
            "  - name: a\n    file: 01-a.md\n    depends-on: []\n",
        )
        _write_batch(plan_dir, "01-a.md", name="a", verify="verify: pytest tests/a -q")

        status_path = plan_dir / "status.md"
        # Unterminated fenced-yaml block under ## Batches -- read_batches raises ValueError, which must degrade to [] rather than propagate.
        status_path.write_text(
            "## Batches\n\n```yaml\nbatches:\n  - name: a\n    state: approved\n",
            encoding="utf-8",
        )

        commands = iter_batch_verifies(
            plan_dir, hub_root, git_root, status_path=status_path
        )
        assert commands == [], commands
        print("PASS: malformed ## Batches block returns [] (no raised ValueError)")


def test_iter_batch_verifies_decision2_x_decision4_composition() -> None:
    # The exact composition fixture from _mill/discussion.md: batches 1-3 approved with a shared verify:, batch 4 declares the removal.
    # Batch 4 pending -> batches 1-3 still run (remover not yet approved).
    # Batch 4 approved -> batches 1-3 now suppressed.
    with tempfile.TemporaryDirectory() as td:
        plan_dir = Path(td)
        hub_root = plan_dir.parent
        git_root = plan_dir.parent
        _write_overview(
            plan_dir,
            "  - name: batch1\n"
            "    file: 01-batch1.md\n"
            "    depends-on: []\n"
            "  - name: batch2\n"
            "    file: 02-batch2.md\n"
            "    depends-on: [batch1]\n"
            "  - name: batch3\n"
            "    file: 03-batch3.md\n"
            "    depends-on: [batch2]\n"
            "  - name: batch4\n"
            "    file: 04-batch4.md\n"
            "    depends-on: [batch1, batch2, batch3]\n",
        )
        _write_batch(
            plan_dir, "01-batch1.md", name="batch1", verify="verify: go build ./tools/x/"
        )
        _write_batch(
            plan_dir, "02-batch2.md", name="batch2", verify="verify: go build ./tools/x/"
        )
        _write_batch(
            plan_dir, "03-batch3.md", name="batch3", verify="verify: go build ./tools/x/"
        )
        _write_batch(
            plan_dir,
            "04-batch4.md",
            name="batch4",
            verify="verify: go build ./...",
            deletes="tools/x/",
        )

        status_path = plan_dir / "status.md"
        status_path.write_text(
            "## Batches\n\n"
            "```yaml\n"
            "batches:\n"
            "  - name: batch1\n"
            "    state: approved\n"
            "  - name: batch2\n"
            "    state: approved\n"
            "  - name: batch3\n"
            "    state: approved\n"
            "  - name: batch4\n"
            "    state: pending\n"
            "```\n",
            encoding="utf-8",
        )
        pending_variant = iter_batch_verifies(
            plan_dir, hub_root, git_root, status_path=status_path
        )
        assert pending_variant == [
            ("batch1", "go build ./tools/x/", None),
            ("batch2", "go build ./tools/x/", None),
            ("batch3", "go build ./tools/x/", None),
        ], pending_variant

        status_path.write_text(
            "## Batches\n\n"
            "```yaml\n"
            "batches:\n"
            "  - name: batch1\n"
            "    state: approved\n"
            "  - name: batch2\n"
            "    state: approved\n"
            "  - name: batch3\n"
            "    state: approved\n"
            "  - name: batch4\n"
            "    state: approved\n"
            "```\n",
            encoding="utf-8",
        )
        approved_variant = iter_batch_verifies(
            plan_dir, hub_root, git_root, status_path=status_path
        )
        assert approved_variant == [
            ("batch4", "go build ./...", None)
        ], approved_variant
        print(
            "PASS: Decision-2 x Decision-4 composition -- "
            f"pending={pending_variant} approved={approved_variant}"
        )


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
        test_parse_commit_none_card_ids_real_message_returns_empty_set()
        test_parse_commit_none_card_ids_none_sentinel_included()
        test_parse_commit_none_card_ids_mixed_case_included()
        test_parse_commit_none_card_ids_only_middle_card_none()
        test_parse_commit_none_card_ids_missing_field_not_included()
        test_iter_batch_verifies_suppresses_target_removed_by_later_batch()
        test_iter_batch_verifies_self_delete_not_suppressed()
        test_iter_batch_verifies_tokenizer_edge_cases_not_spuriously_matched()
        test_iter_batch_verifies_directory_containment_not_suppressed()
        test_iter_batch_verifies_multi_target_existential_suppression()
        test_iter_batch_verifies_coordinate_space_mismatch_not_suppressed()
        test_iter_batch_verifies_status_path_mixed_states()
        test_iter_batch_verifies_no_batches_section_with_status_path_returns_empty()
        test_iter_batch_verifies_malformed_batches_block_returns_empty()
        test_iter_batch_verifies_decision2_x_decision4_composition()
        print("All _plan_dag unit tests passed.")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
