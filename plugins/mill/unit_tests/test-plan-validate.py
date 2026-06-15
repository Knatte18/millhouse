"""Unit tests for _plan_validate.py.

One test function per check (clean + dirty fixtures). Tests use in-memory
tempfile fixtures; no real LLM, no real git, no network.

Check coverage:
  check 1 — non-existent-path
  check 2 — card-missing-field
  check 3 — card-numbering (within-batch gap, cross-batch duplicate)
  check 4 — depends-on-unknown
  check 5 — parallel-modifies-overlap
  check 6 — reads-not-backtick-path (incl. none-exempt)
  check 8 — all-files-touched-mismatch
  meta    — sorted output, missing overview
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _plan_validate  # noqa: E402


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _make_overview(
    batches: list[dict],
    *,
    all_files_touched: list[str] | None = None,
) -> str:
    """Return 00-overview.md text.

    Each batch dict: {name, file, number (optional), depends-on (optional, default [])}.
    all_files_touched: optional list of path strings for the section.
    """
    entries = []
    for b in batches:
        deps = b.get("depends-on", [])
        deps_yaml = "[" + ", ".join(str(d) if isinstance(d, int) else f'"{d}"' for d in deps) + "]"
        if "number" in b:
            first_line = f"  - number: {b['number']}\n    name: {b['name']}\n"
        else:
            first_line = f"  - name: {b['name']}\n"
        entries.append(
            first_line
            + f"    file: {b['file']}\n"
            + f"    depends-on: {deps_yaml}\n"
            + "    verify: null"
        )
    batch_list = "\n".join(entries)
    text = (
        "# Overview\n\n"
        "```yaml\n"
        'task: test\nslug: test-slug\nroot: ""\n'
        "```\n\n"
        "## Batch Index\n\n"
        "```yaml\n"
        f"batches:\n{batch_list}\n"
        "```\n"
    )
    if all_files_touched is not None:
        if all_files_touched:
            bullets = "\n".join(f"- `{p}`" for p in all_files_touched)
        else:
            bullets = ""
        text += f"\n## All Files Touched\n\n{bullets}\n"
    return text


def _make_batch_file(
    name: str,
    card_num: int = 1,
    *,
    context: list[str] | None = None,
    edits: list[str] | None = None,
    creates: list[str] | None = None,
    deletes: list[str] | None = None,
    missing_fields: set[str] | None = None,
) -> str:
    """Return a well-formed batch file with one card.

    context/edits/creates/deletes: list of path strings (backtick-wrapped
        automatically), or None to default to "none".
    missing_fields: set of field names to omit (for check 2 tests).
    """
    missing_fields = missing_fields or set()

    def fmt(paths: list[str] | None) -> str:
        if not paths:
            return "none"
        return ", ".join(f"`{p}`" for p in paths)

    parts = [
        f"# Batch: {name}\n\n",
        "```yaml\n",
        f"task: test\nbatch: {name}\ncards: 1\nverify: null\ndepends-on: []\n",
        "```\n\n",
        "## Cards\n\n",
        f"### Card {card_num}: card {card_num}\n\n",
    ]
    if "Context" not in missing_fields:
        parts.append(f"- **Context:** {fmt(context)}\n")
    if "Edits" not in missing_fields:
        parts.append(f"- **Edits:** {fmt(edits)}\n")
    if "Creates" not in missing_fields:
        parts.append(f"- **Creates:** {fmt(creates)}\n")
    if "Deletes" not in missing_fields:
        parts.append(f"- **Deletes:** {fmt(deletes)}\n")
    if "Requirements" not in missing_fields:
        parts.append("- **Requirements:**\n  See scope.\n")
    if "Commit" not in missing_fields:
        parts.append(f"- **Commit:** feat({name}): card {card_num}\n")
    return "".join(parts)


def _make_batch_file_cards(name: str, card_nums: list[int]) -> str:
    """Return a batch file with multiple cards (all fields present)."""
    parts = [
        f"# Batch: {name}\n\n",
        "```yaml\n",
        f"task: test\nbatch: {name}\ncards: {len(card_nums)}\nverify: null\ndepends-on: []\n",
        "```\n\n",
        "## Cards\n",
    ]
    for n in card_nums:
        parts.append(
            f"\n### Card {n}: card {n}\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Requirements:**\n  See scope.\n"
            f"- **Commit:** feat({name}): card {n}\n"
        )
    return "".join(parts)


def _write_plan(plan_dir: Path, overview_text: str, batches: list[tuple[str, str]]) -> None:
    """Write overview + batch files into plan_dir."""
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "00-overview.md").write_text(overview_text, encoding="utf-8")
    for filename, content in batches:
        (plan_dir / filename).write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Test functions
# ---------------------------------------------------------------------------

def test_check_non_existent_path_clean() -> int:
    """Clean: all Reads:/Creates: paths exist on disk -> no errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"

        existing_file = project_root / "src" / "a.py"
        existing_file.parent.mkdir(parents=True)
        existing_file.write_text("# placeholder", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", context=["src/a.py"])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check1 = [e for e in result if e["check"] == "non-existent-path"]
        if check1:
            print(f"FAIL test_check_non_existent_path_clean: unexpected errors: {check1}",
                  file=sys.stderr)
            return 1
        print("PASS test_check_non_existent_path_clean")
        return 0


def test_check_non_existent_path_dirty() -> int:
    """Dirty: Reads: has nonexistent/path.py -> one non-existent-path error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", context=["nonexistent/path.py"])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check1 = [e for e in result if e["check"] == "non-existent-path"]
        try:
            assert len(check1) == 1, f"expected 1 error, got {len(check1)}: {check1}"
            assert check1[0]["path"] == "nonexistent/path.py", (
                f"wrong path: {check1[0]['path']!r}"
            )
            assert check1[0]["batch"] == "01-alpha", f"wrong batch: {check1[0]['batch']!r}"
            print("PASS test_check_non_existent_path_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_non_existent_path_dirty: {exc}", file=sys.stderr)
            return 1


def test_check_card_missing_field_clean() -> int:
    """Clean: all required fields present -> no card-missing-field errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha")
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check2 = [e for e in result if e["check"] == "card-missing-field"]
        if check2:
            print(f"FAIL test_check_card_missing_field_clean: unexpected errors: {check2}",
                  file=sys.stderr)
            return 1
        print("PASS test_check_card_missing_field_clean")
        return 0


def test_check_card_missing_field_dirty() -> int:
    """Dirty: card omits Edits: -> one card-missing-field error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", missing_fields={"Edits"})
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check2 = [e for e in result if e["check"] == "card-missing-field"]
        try:
            assert len(check2) == 1, f"expected 1 error, got {len(check2)}: {check2}"
            assert check2[0]["card"] == 1, f"wrong card: {check2[0]['card']}"
            assert "Edits" in check2[0]["message"], (
                f"message should mention 'Edits': {check2[0]['message']!r}"
            )
            print("PASS test_check_card_missing_field_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_card_missing_field_dirty: {exc}", file=sys.stderr)
            return 1


def test_check_card_numbering_clean() -> int:
    """Clean: sequential cards [1, 2, 3] -> no card-numbering errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file_cards("alpha", [1, 2, 3])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check3 = [e for e in result if e["check"] == "card-numbering"]
        if check3:
            print(f"FAIL test_check_card_numbering_clean: unexpected errors: {check3}",
                  file=sys.stderr)
            return 1
        print("PASS test_check_card_numbering_clean")
        return 0


def test_check_card_numbering_dirty_gap() -> int:
    """Dirty: cards [1, 2, 4] in one batch -> one card-numbering error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file_cards("alpha", [1, 2, 4])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check3 = [e for e in result if e["check"] == "card-numbering"]
        try:
            assert len(check3) == 1, f"expected 1 error, got {len(check3)}: {check3}"
            assert check3[0]["batch"] == "01-alpha", f"wrong batch: {check3[0]['batch']!r}"
            # card 4 is the one that breaks sequence (or 3 is the missing one)
            assert check3[0]["card"] in (3, 4), (
                f"expected card 3 or 4, got {check3[0]['card']}"
            )
            assert "numbering" in check3[0]["message"].lower() or \
                   "sequential" in check3[0]["message"].lower(), (
                f"message should mention numbering/sequential: {check3[0]['message']!r}"
            )
            print("PASS test_check_card_numbering_dirty_gap")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_card_numbering_dirty_gap: {exc}", file=sys.stderr)
            return 1


def test_check_card_numbering_dirty_cross_batch() -> int:
    """Dirty: card 1 in batch-a AND batch-b -> two card-numbering errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md"},
            {"name": "beta",  "file": "02-beta.md"},
        ])
        batch_a = _make_batch_file("alpha", card_num=1)
        batch_b = _make_batch_file("beta",  card_num=1)
        _write_plan(plan_dir, overview, [
            ("01-alpha.md", batch_a),
            ("02-beta.md",  batch_b),
        ])

        result = _plan_validate.run(plan_dir, project_root)
        check3 = [e for e in result if e["check"] == "card-numbering"]
        try:
            assert len(check3) == 2, f"expected 2 errors, got {len(check3)}: {check3}"
            batches = {e["batch"] for e in check3}
            assert "01-alpha" in batches, f"expected 01-alpha in {batches}"
            assert "02-beta" in batches, f"expected 02-beta in {batches}"
            for e in check3:
                assert e["card"] == 1, f"wrong card: {e['card']}"
            print("PASS test_check_card_numbering_dirty_cross_batch")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_card_numbering_dirty_cross_batch: {exc}", file=sys.stderr)
            return 1


def test_check_depends_on_unknown_clean() -> int:
    """Clean: no depends-on entries -> no depends-on-unknown errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha")
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check4 = [e for e in result if e["check"] == "depends-on-unknown"]
        if check4:
            print(f"FAIL test_check_depends_on_unknown_clean: unexpected: {check4}",
                  file=sys.stderr)
            return 1
        print("PASS test_check_depends_on_unknown_clean")
        return 0


def test_check_depends_on_unknown_dirty() -> int:
    """Dirty: depends-on has integer reference to unknown batch number -> one depends-on-unknown error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([
            {
                "name": "alpha",
                "file": "01-alpha.md",
                "number": 1,
                "depends-on": [99],
            }
        ])
        batch = _make_batch_file("alpha")
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check4 = [e for e in result if e["check"] == "depends-on-unknown"]
        try:
            assert len(check4) == 1, f"expected 1 error, got {len(check4)}: {check4}"
            assert check4[0]["batch"] == "alpha", f"wrong batch: {check4[0]['batch']!r}"
            assert "99" in check4[0]["message"], (
                f"message should mention the unknown number: {check4[0]['message']!r}"
            )
            print("PASS test_check_depends_on_unknown_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_depends_on_unknown_dirty: {exc}", file=sys.stderr)
            return 1


def test_check_depends_on_unknown_dirty_legacy_string() -> int:
    """Dirty (legacy): depends-on string references unknown batch name -> one depends-on-unknown error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([
            {
                "name": "alpha",
                "file": "01-alpha.md",
                "depends-on": ["non-existent-batch"],
            }
        ])
        batch = _make_batch_file("alpha")
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check4 = [e for e in result if e["check"] == "depends-on-unknown"]
        try:
            assert len(check4) == 1, f"expected 1 error, got {len(check4)}: {check4}"
            assert check4[0]["batch"] == "alpha", f"wrong batch: {check4[0]['batch']!r}"
            assert "non-existent-batch" in check4[0]["message"], (
                f"message should mention the unknown name: {check4[0]['message']!r}"
            )
            print("PASS test_check_depends_on_unknown_dirty_legacy_string")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_depends_on_unknown_dirty_legacy_string: {exc}", file=sys.stderr)
            return 1


def test_check_parallel_modifies_overlap_clean() -> int:
    """Clean: batch-b depends on batch-a, both modify same file -> no error (not parallel-eligible)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md", "depends-on": []},
            {"name": "beta",  "file": "02-beta.md",  "depends-on": ["alpha"]},
        ])
        batch_a = _make_batch_file("alpha", edits=["shared/file.py"])
        batch_b = _make_batch_file("beta",  edits=["shared/file.py"])
        _write_plan(plan_dir, overview, [
            ("01-alpha.md", batch_a),
            ("02-beta.md",  batch_b),
        ])

        result = _plan_validate.run(plan_dir, project_root)
        check5 = [e for e in result if e["check"] == "parallel-modifies-overlap"]
        if check5:
            print(f"FAIL test_check_parallel_modifies_overlap_clean: unexpected: {check5}",
                  file=sys.stderr)
            return 1
        print("PASS test_check_parallel_modifies_overlap_clean")
        return 0


def test_check_parallel_modifies_overlap_dirty() -> int:
    """Dirty: two batches with no deps both modify shared/file.py -> one error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md", "depends-on": []},
            {"name": "beta",  "file": "02-beta.md",  "depends-on": []},
        ])
        batch_a = _make_batch_file("alpha", card_num=1, edits=["shared/file.py"])
        batch_b = _make_batch_file("beta",  card_num=2, edits=["shared/file.py"])
        _write_plan(plan_dir, overview, [
            ("01-alpha.md", batch_a),
            ("02-beta.md",  batch_b),
        ])

        result = _plan_validate.run(plan_dir, project_root)
        check5 = [e for e in result if e["check"] == "parallel-modifies-overlap"]
        try:
            assert len(check5) == 1, f"expected 1 error, got {len(check5)}: {check5}"
            assert check5[0]["path"] == "shared/file.py", (
                f"wrong path: {check5[0]['path']!r}"
            )
            assert "alpha" in check5[0]["message"] and "beta" in check5[0]["message"], (
                f"message should mention both batch names: {check5[0]['message']!r}"
            )
            print("PASS test_check_parallel_modifies_overlap_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_parallel_modifies_overlap_dirty: {exc}", file=sys.stderr)
            return 1


def test_check_reads_not_backtick_path_clean() -> int:
    """Clean: backtick-only bullets and 'none' sentinel -> no reads-not-backtick-path errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"

        # Create the referenced file so check 1 doesn't fire.
        (project_root / "src").mkdir(parents=True)
        (project_root / "src" / "a.py").write_text("# placeholder", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        # Single-line backtick: clean; Edits: none (exempt)
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify: null\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: description\n\n"
            "- **Context:** `src/a.py`\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        check6 = [e for e in result if e["check"] == "reads-not-backtick-path"]
        if check6:
            print(f"FAIL test_check_reads_not_backtick_path_clean: unexpected: {check6}",
                  file=sys.stderr)
            return 1
        print("PASS test_check_reads_not_backtick_path_clean")
        return 0


def test_check_reads_not_backtick_path_none_exempt() -> int:
    """Clean: `- **Context:** none` returns [] for check 6."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha")  # defaults to "none" for reads/modifies/creates
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check6 = [e for e in result if e["check"] == "reads-not-backtick-path"]
        if check6:
            print(
                f"FAIL test_check_reads_not_backtick_path_none_exempt: "
                f"'none' should be exempt: {check6}",
                file=sys.stderr,
            )
            return 1
        print("PASS test_check_reads_not_backtick_path_none_exempt")
        return 0


def test_check_reads_not_backtick_path_dirty() -> int:
    """Dirty: Reads: bullet has prose alongside backtick path -> one reads-not-backtick-path error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"

        # Create file so check 1 doesn't fire.
        (project_root / "src").mkdir(parents=True)
        (project_root / "src" / "foo.py").write_text("# placeholder", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify: null\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: description\n\n"
            "- **Context:** `src/foo.py` (used by foo)\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        check6 = [e for e in result if e["check"] == "reads-not-backtick-path"]
        try:
            assert len(check6) == 1, f"expected 1 error, got {len(check6)}: {check6}"
            assert check6[0]["check"] == "reads-not-backtick-path"
            print("PASS test_check_reads_not_backtick_path_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_reads_not_backtick_path_dirty: {exc}", file=sys.stderr)
            return 1


def test_check_all_files_touched_mismatch_clean_no_section() -> int:
    """Clean: overview without All Files Touched section -> no errors for check 8."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha")
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check8 = [e for e in result if e["check"] == "all-files-touched-mismatch"]
        if check8:
            print(
                f"FAIL test_check_all_files_touched_mismatch_clean_no_section: "
                f"no section should produce no errors: {check8}",
                file=sys.stderr,
            )
            return 1
        print("PASS test_check_all_files_touched_mismatch_clean_no_section")
        return 0


def test_check_all_files_touched_mismatch_dirty() -> int:
    """Dirty: overview lists path/extra.py not in any card's Modifies:/Creates: -> one error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        # Overview declares "path/extra.py" but no card modifies/creates it.
        overview = _make_overview(
            [{"name": "alpha", "file": "01-alpha.md"}],
            all_files_touched=["path/extra.py"],
        )
        batch = _make_batch_file("alpha")  # Modifies: none, Creates: none
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check8 = [e for e in result if e["check"] == "all-files-touched-mismatch"]
        try:
            assert len(check8) == 1, f"expected 1 error, got {len(check8)}: {check8}"
            assert check8[0]["path"] == "path/extra.py", (
                f"wrong path: {check8[0]['path']!r}"
            )
            assert "All Files Touched" in check8[0]["message"], (
                f"message should mention 'All Files Touched': {check8[0]['message']!r}"
            )
            print("PASS test_check_all_files_touched_mismatch_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_all_files_touched_mismatch_dirty: {exc}", file=sys.stderr)
            return 1


def test_run_returns_sorted() -> int:
    """Output is sorted by (batch or '', card or 0, check)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md"},
            {"name": "beta",  "file": "02-beta.md"},
        ])
        # 01-alpha: card missing Edits -> card-missing-field (batch=01-alpha, card=1)
        batch_a = _make_batch_file("alpha", missing_fields={"Edits"})
        # 02-beta: nonexistent path -> non-existent-path (batch=02-beta, card=None->0)
        batch_b = _make_batch_file("beta", context=["nonexistent/thing.py"])
        _write_plan(plan_dir, overview, [
            ("01-alpha.md", batch_a),
            ("02-beta.md",  batch_b),
        ])

        result = _plan_validate.run(plan_dir, project_root)
        try:
            assert len(result) >= 2, f"expected at least 2 errors, got {len(result)}: {result}"
            # Verify sort key: (batch or "", card or 0, check)
            keys = [(e["batch"] or "", e["card"] or 0, e["check"]) for e in result]
            assert keys == sorted(keys), f"result is not sorted: {keys}"
            print("PASS test_run_returns_sorted")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_run_returns_sorted: {exc}", file=sys.stderr)
            return 1


def test_run_no_overview() -> int:
    """Empty plan_dir (no overview) -> one missing-overview error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        plan_dir.mkdir()
        project_root.mkdir()

        result = _plan_validate.run(plan_dir, project_root)
        try:
            assert len(result) == 1, f"expected 1 error, got {len(result)}: {result}"
            assert result[0]["check"] == "missing-overview", (
                f"wrong check: {result[0]['check']!r}"
            )
            print("PASS test_run_no_overview")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_run_no_overview: {exc}", file=sys.stderr)
            return 1


# ---------------------------------------------------------------------------
# Tests for Deletes-aware behaviour (Cards 26–28)
# ---------------------------------------------------------------------------

def test_deletes_field_required() -> int:
    """(a) Card without - **Deletes:** line -> card-missing-field error mentioning 'Deletes:'."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", missing_fields={"Deletes"})
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        deletes_errs = [
            e for e in result
            if e["check"] == "card-missing-field" and "Deletes:" in e["message"]
        ]
        try:
            assert len(deletes_errs) == 1, (
                f"expected 1 Deletes: card-missing-field error, got: {deletes_errs}"
            )
            assert deletes_errs[0]["card"] == 1, f"wrong card: {deletes_errs[0]['card']}"
            assert "missing required field: Deletes:" in deletes_errs[0]["message"], (
                f"message should contain 'missing required field: Deletes:': "
                f"{deletes_errs[0]['message']!r}"
            )
            print("PASS test_deletes_field_required")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_deletes_field_required: {exc}", file=sys.stderr)
            return 1


def test_deletes_token_on_disk_clean() -> int:
    """(b) Deletes: token resolves to an on-disk file -> no non-existent-path error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"

        existing_file = project_root / "src" / "to_delete.py"
        existing_file.parent.mkdir(parents=True)
        existing_file.write_text("# placeholder", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", deletes=["src/to_delete.py"])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check1 = [e for e in result if e["check"] == "non-existent-path"]
        if check1:
            print(
                f"FAIL test_deletes_token_on_disk_clean: unexpected errors: {check1}",
                file=sys.stderr,
            )
            return 1
        print("PASS test_deletes_token_on_disk_clean")
        return 0


def test_deletes_token_in_creates_union_clean() -> int:
    """(c) Deletes: token missing on disk + in another batch's Creates: -> no error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md", "depends-on": []},
            {"name": "beta",  "file": "02-beta.md",  "depends-on": ["alpha"]},
        ])
        batch_a = _make_batch_file("alpha", card_num=1, creates=["generated/file.py"])
        batch_b = _make_batch_file("beta",  card_num=2, deletes=["generated/file.py"])
        _write_plan(plan_dir, overview, [
            ("01-alpha.md", batch_a),
            ("02-beta.md",  batch_b),
        ])

        result = _plan_validate.run(plan_dir, project_root)
        check1 = [e for e in result if e["check"] == "non-existent-path"]
        if check1:
            print(
                f"FAIL test_deletes_token_in_creates_union_clean: unexpected errors: {check1}",
                file=sys.stderr,
            )
            return 1
        print("PASS test_deletes_token_in_creates_union_clean")
        return 0


def test_deletes_token_missing_not_in_creates_dirty() -> int:
    """(d) Deletes: token missing on disk + not in any Creates: -> non-existent-path with Deletes-specific message."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", deletes=["missing/file.py"])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check1 = [e for e in result if e["check"] == "non-existent-path"]
        try:
            assert len(check1) == 1, f"expected 1 error, got {len(check1)}: {check1}"
            assert check1[0]["path"] == "missing/file.py", (
                f"wrong path: {check1[0]['path']!r}"
            )
            assert check1[0]["message"].startswith("Deletes: token '"), (
                f"message should start with \"Deletes: token '\": {check1[0]['message']!r}"
            )
            print("PASS test_deletes_token_missing_not_in_creates_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_deletes_token_missing_not_in_creates_dirty: {exc}", file=sys.stderr)
            return 1


def test_reads_token_in_deletes_union_clean() -> int:
    """(e) Reads: token missing on disk + in another batch's Deletes: -> no error for that token."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md", "depends-on": []},
            {"name": "beta",  "file": "02-beta.md",  "depends-on": ["alpha"]},
        ])
        # alpha reads going/away.py (not on disk); beta declares it as Deletes:.
        # Alpha's Reads: reference must be suppressed by deletes_union.
        batch_a = _make_batch_file("alpha", card_num=1, context=["going/away.py"])
        batch_b = _make_batch_file("beta",  card_num=2, deletes=["going/away.py"])
        _write_plan(plan_dir, overview, [
            ("01-alpha.md", batch_a),
            ("02-beta.md",  batch_b),
        ])

        result = _plan_validate.run(plan_dir, project_root)
        alpha_errs = [
            e for e in result
            if e["check"] == "non-existent-path"
            and e["batch"] == "01-alpha"
            and e["path"] == "going/away.py"
        ]
        try:
            assert len(alpha_errs) == 0, (
                f"expected no error for alpha's Reads: token, got: {alpha_errs}"
            )
            print("PASS test_reads_token_in_deletes_union_clean")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_reads_token_in_deletes_union_clean: {exc}", file=sys.stderr)
            return 1


def test_reads_token_in_creates_union_suppressed() -> int:
    """(f) Reads: token missing on disk + in creates_union -> no error (existing behaviour)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md", "depends-on": []},
            {"name": "beta",  "file": "02-beta.md",  "depends-on": ["alpha"]},
        ])
        batch_a = _make_batch_file("alpha", card_num=1, creates=["generated/output.py"])
        batch_b = _make_batch_file("beta",  card_num=2, context=["generated/output.py"])
        _write_plan(plan_dir, overview, [
            ("01-alpha.md", batch_a),
            ("02-beta.md",  batch_b),
        ])

        result = _plan_validate.run(plan_dir, project_root)
        check1 = [e for e in result if e["check"] == "non-existent-path"]
        if check1:
            print(
                f"FAIL test_reads_token_in_creates_union_suppressed: unexpected errors: {check1}",
                file=sys.stderr,
            )
            return 1
        print("PASS test_reads_token_in_creates_union_suppressed")
        return 0


def test_wiki_config_mutation_clean() -> int:
    """mill-config.yaml only in Reads: (not Modifies/Creates) -> zero wiki-config-mutation errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", context=["mill-config.yaml"])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "wiki-config-mutation"]
        try:
            assert len(check_errors) == 0, (
                f"expected 0 wiki-config-mutation errors, got: {check_errors}"
            )
            print("PASS test_wiki_config_mutation_clean")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_wiki_config_mutation_clean: {exc}", file=sys.stderr)
            return 1


def test_wiki_config_mutation_modifies() -> int:
    """mill-config.yaml in Modifies: -> exactly one wiki-config-mutation error with correct shape."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", edits=["mill-config.yaml"])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "wiki-config-mutation"]
        try:
            assert len(check_errors) == 1, (
                f"expected 1 wiki-config-mutation error, got: {check_errors}"
            )
            e = check_errors[0]
            assert e["check"] == "wiki-config-mutation", f"wrong check: {e['check']!r}"
            assert e["batch"] == "01-alpha", f"wrong batch: {e['batch']!r}"
            assert e["card"] is None, f"card should be None, got: {e['card']!r}"
            assert e["path"] == "mill-config.yaml", f"wrong path: {e['path']!r}"
            print("PASS test_wiki_config_mutation_modifies")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_wiki_config_mutation_modifies: {exc}", file=sys.stderr)
            return 1


def test_wiki_config_mutation_creates() -> int:
    """mill-config.yaml in Creates: -> exactly one wiki-config-mutation error with correct shape."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", creates=["mill-config.yaml"])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "wiki-config-mutation"]
        try:
            assert len(check_errors) == 1, (
                f"expected 1 wiki-config-mutation error, got: {check_errors}"
            )
            e = check_errors[0]
            assert e["check"] == "wiki-config-mutation", f"wrong check: {e['check']!r}"
            assert e["batch"] == "01-alpha", f"wrong batch: {e['batch']!r}"
            assert e["card"] is None, f"card should be None, got: {e['card']!r}"
            assert e["path"] == "mill-config.yaml", f"wrong path: {e['path']!r}"
            print("PASS test_wiki_config_mutation_creates")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_wiki_config_mutation_creates: {exc}", file=sys.stderr)
            return 1


def test_wiki_config_mutation_multi_batch() -> int:
    """Two batches each with mill-config.yaml in Modifies: -> exactly two wiki-config-mutation errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md", "depends-on": []},
            {"name": "beta",  "file": "02-beta.md",  "depends-on": []},
        ])
        batch_a = _make_batch_file("alpha", card_num=1, edits=["mill-config.yaml"])
        batch_b = _make_batch_file("beta",  card_num=2, edits=["mill-config.yaml"])
        _write_plan(plan_dir, overview, [
            ("01-alpha.md", batch_a),
            ("02-beta.md",  batch_b),
        ])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "wiki-config-mutation"]
        try:
            assert len(check_errors) == 2, (
                f"expected 2 wiki-config-mutation errors (one per batch), got: {check_errors}"
            )
            batches = {e["batch"] for e in check_errors}
            assert "01-alpha" in batches, f"expected 01-alpha in {batches}"
            assert "02-beta" in batches, f"expected 02-beta in {batches}"
            print("PASS test_wiki_config_mutation_multi_batch")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_wiki_config_mutation_multi_batch: {exc}", file=sys.stderr)
            return 1


def test_wiki_config_mutation_modifies_and_creates() -> int:
    """mill-config.yaml in both Modifies: and Creates: -> exactly one error (deduplicated)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            edits=["mill-config.yaml"],
            creates=["mill-config.yaml"],
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "wiki-config-mutation"]
        try:
            assert len(check_errors) == 1, (
                f"expected 1 wiki-config-mutation error (deduplicated), got: {check_errors}"
            )
            print("PASS test_wiki_config_mutation_modifies_and_creates")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_wiki_config_mutation_modifies_and_creates: {exc}", file=sys.stderr)
            return 1


def test_skip_checks_filters_wiki_config_mutation() -> int:
    """skip_checks={"wiki-config-mutation"} suppresses that check entirely."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "mill-config.yaml").write_text("# placeholder", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", edits=["mill-config.yaml"])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(
            plan_dir, project_root,
            skip_checks=frozenset({"wiki-config-mutation"}),
        )
        try:
            assert result == [], f"expected no errors, got: {result}"
            print("PASS test_skip_checks_filters_wiki_config_mutation")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_skip_checks_filters_wiki_config_mutation: {exc}", file=sys.stderr)
            return 1


def test_skip_checks_does_not_suppress_other_checks() -> int:
    """skip_checks={"wiki-config-mutation"} suppresses that check but not card-missing-field."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "mill-config.yaml").write_text("# placeholder", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", edits=["mill-config.yaml"], missing_fields={"Commit"})
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(
            plan_dir, project_root,
            skip_checks=frozenset({"wiki-config-mutation"}),
        )
        try:
            assert len(result) == 1, f"expected exactly 1 error, got: {result}"
            assert result[0]["check"] == "card-missing-field", (
                f"expected card-missing-field, got: {result[0]['check']!r}"
            )
            print("PASS test_skip_checks_does_not_suppress_other_checks")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_skip_checks_does_not_suppress_other_checks: {exc}", file=sys.stderr)
            return 1


def test_skip_checks_unknown_check_silently_ignored() -> int:
    """Unknown check name in skip_checks raises no exception and returns empty list."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha")
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        try:
            result = _plan_validate.run(
                plan_dir, project_root,
                skip_checks=frozenset({"nonexistent-check"}),
            )
            assert result == [], f"expected no errors, got: {result}"
            print("PASS test_skip_checks_unknown_check_silently_ignored")
            return 0
        except Exception as exc:
            print(f"FAIL test_skip_checks_unknown_check_silently_ignored: {exc}", file=sys.stderr)
            return 1


def test_check_verify_not_isolated_null() -> int:
    """Clean: per-batch frontmatter verify: null -> no verify-not-isolated error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha")
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        verify_errs = [e for e in result if e["check"] == "verify-not-isolated"]
        try:
            assert len(verify_errs) == 0, f"expected no errors, got {len(verify_errs)}: {verify_errs}"
            print("PASS test_check_verify_not_isolated_null")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_verify_not_isolated_null: {exc}", file=sys.stderr)
            return 1


def test_check_verify_not_isolated_missing_key() -> int:
    """Clean: per-batch frontmatter omits verify: entirely -> no verify-not-isolated error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        verify_errs = [e for e in result if e["check"] == "verify-not-isolated"]
        try:
            assert len(verify_errs) == 0, f"expected no errors, got {len(verify_errs)}: {verify_errs}"
            print("PASS test_check_verify_not_isolated_missing_key")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_verify_not_isolated_missing_key: {exc}", file=sys.stderr)
            return 1


def test_check_verify_not_isolated_dirty_no_prefix() -> int:
    """Dirty: Python project + per-batch frontmatter verify: without PYTHONPATH= prefix -> one error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        # Add Python marker to make this a Python project
        (project_root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify: uv run --project plugins/mill python test.py\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        verify_errs = [e for e in result if e["check"] == "verify-not-isolated"]
        try:
            assert len(verify_errs) == 1, f"expected 1 error, got {len(verify_errs)}: {verify_errs}"
            e = verify_errs[0]
            assert e["batch"] == "01-alpha", f"wrong batch: {e['batch']!r}"
            assert e["card"] is None, f"wrong card: {e['card']!r}"
            assert e["path"] == "uv run --project plugins/mill python test.py", f"wrong path: {e['path']!r}"
            assert e["message"] == "verify command missing PYTHONPATH= prefix", f"wrong message: {e['message']!r}"
            # Verify 5-key envelope
            assert set(e.keys()) == {"check", "batch", "card", "path", "message"}, (
                f"wrong keys: {set(e.keys())}"
            )
            print("PASS test_check_verify_not_isolated_dirty_no_prefix")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_verify_not_isolated_dirty_no_prefix: {exc}", file=sys.stderr)
            return 1


def test_check_verify_not_isolated_clean_with_prefix() -> int:
    """Clean: per-batch frontmatter verify: with PYTHONPATH= prefix -> no error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify: PYTHONPATH= uv run --project plugins/mill python test.py\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        verify_errs = [e for e in result if e["check"] == "verify-not-isolated"]
        try:
            assert len(verify_errs) == 0, f"expected no errors, got {len(verify_errs)}: {verify_errs}"
            print("PASS test_check_verify_not_isolated_clean_with_prefix")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_verify_not_isolated_clean_with_prefix: {exc}", file=sys.stderr)
            return 1


def test_check_verify_not_isolated_two_batches_dirty() -> int:
    """Dirty: Python project + two batch files both unprefixed -> exactly two verify-not-isolated errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        # Add Python marker to make this a Python project
        (project_root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md"},
            {"name": "beta", "file": "02-beta.md"},
        ])
        batch_a = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify: uv run test-a.py\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        batch_b = (
            "# Batch: beta\n\n"
            "```yaml\n"
            "task: test\nbatch: beta\ncards: 1\nverify: uv run test-b.py\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(beta): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_a), ("02-beta.md", batch_b)])

        result = _plan_validate.run(plan_dir, project_root)
        verify_errs = [e for e in result if e["check"] == "verify-not-isolated"]
        try:
            assert len(verify_errs) == 2, f"expected 2 errors, got {len(verify_errs)}: {verify_errs}"
            batches = {e["batch"] for e in verify_errs}
            assert batches == {"01-alpha", "02-beta"}, f"wrong batch names: {batches}"
            print("PASS test_check_verify_not_isolated_two_batches_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_verify_not_isolated_two_batches_dirty: {exc}", file=sys.stderr)
            return 1


def test_check_verify_not_isolated_leading_whitespace() -> int:
    """Clean: extra leading whitespace before PYTHONPATH= -> no error (uses .strip())."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify:   PYTHONPATH= uv run test.py\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        verify_errs = [e for e in result if e["check"] == "verify-not-isolated"]
        try:
            assert len(verify_errs) == 0, f"expected no errors, got {len(verify_errs)}: {verify_errs}"
            print("PASS test_check_verify_not_isolated_leading_whitespace")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_verify_not_isolated_leading_whitespace: {exc}", file=sys.stderr)
            return 1


def test_check_verify_not_isolated_non_empty_pythonpath_value() -> int:
    """Clean: verify: PYTHONPATH=/some/path uv run ... -> no error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify: PYTHONPATH=/some/path uv run test.py\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        verify_errs = [e for e in result if e["check"] == "verify-not-isolated"]
        try:
            assert len(verify_errs) == 0, f"expected no errors, got {len(verify_errs)}: {verify_errs}"
            print("PASS test_check_verify_not_isolated_non_empty_pythonpath_value")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_verify_not_isolated_non_empty_pythonpath_value: {exc}", file=sys.stderr)
            return 1


def test_check_verify_not_isolated_run_integration() -> int:
    """Integration: Python project + unprefixed batch, verify 5-key envelope."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        # Add Python marker to make this a Python project
        (project_root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify: uv run test.py\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        try:
            result = _plan_validate.run(plan_dir, project_root)
            verify_errs = [e for e in result if e["check"] == "verify-not-isolated"]
            assert len(verify_errs) == 1, f"expected 1 error, got {len(verify_errs)}: {verify_errs}"
            e = verify_errs[0]
            # Verify all 5 keys are present
            assert set(e.keys()) == {"check", "batch", "card", "path", "message"}, (
                f"envelope missing keys: {set(e.keys())}"
            )
            assert e["check"] == "verify-not-isolated"
            assert e["batch"] == "01-alpha"
            assert e["card"] is None
            assert e["path"] == "uv run test.py"
            assert e["message"] == "verify command missing PYTHONPATH= prefix"
            print("PASS test_check_verify_not_isolated_run_integration")
            return 0
        except (AssertionError, KeyError) as exc:
            print(f"FAIL test_check_verify_not_isolated_run_integration: {exc}", file=sys.stderr)
            return 1


def test_reads_token_missing_both_unions_dirty() -> int:
    """(g) Reads: token missing on disk + in neither union -> non-existent-path error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", context=["totally/missing.py"])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check1 = [e for e in result if e["check"] == "non-existent-path"]
        try:
            assert len(check1) == 1, f"expected 1 error, got {len(check1)}: {check1}"
            assert check1[0]["path"] == "totally/missing.py", (
                f"wrong path: {check1[0]['path']!r}"
            )
            assert not check1[0]["message"].startswith("Deletes: token '"), (
                f"Reads: token should not use Deletes prefix: {check1[0]['message']!r}"
            )
            print("PASS test_reads_token_missing_both_unions_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_reads_token_missing_both_unions_dirty: {exc}", file=sys.stderr)
            return 1


def test_all_files_touched_deletes_counted() -> int:
    """Deletes: token listed in All Files Touched -> no all-files-touched-mismatch error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"

        # foo.md must exist on disk so non-existent-path check doesn't fire.
        (project_root / "foo.md").parent.mkdir(parents=True)
        (project_root / "foo.md").write_text("# foo", encoding="utf-8")

        overview = _make_overview(
            [{"name": "alpha", "file": "01-alpha.md"}],
            all_files_touched=["foo.md"],
        )
        batch = _make_batch_file("alpha", deletes=["foo.md"])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        mismatch_errs = [
            e for e in result
            if e["check"] == "all-files-touched-mismatch" and e["path"] == "foo.md"
        ]
        try:
            assert len(mismatch_errs) == 0, (
                f"Deletes: token should count toward all-files-touched union, "
                f"got: {mismatch_errs}"
            )
            print("PASS test_all_files_touched_deletes_counted")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_all_files_touched_deletes_counted: {exc}", file=sys.stderr)
            return 1


def test_depends_on_batch_mismatch_no_finding_on_match() -> int:
    """Clean: per-batch file's depends-on matches overview's -> no mismatch error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md", "number": 1, "depends-on": []},
            {"name": "beta",  "file": "02-beta.md",  "number": 2, "depends-on": [1]},
        ])
        # Batch file with depends-on matching overview: [1] -> ["alpha"]
        batch_a = _make_batch_file("alpha")
        batch_b_text = (
            "# Batch: beta\n\n"
            "```yaml\n"
            "task: test\n"
            "batch: beta\n"
            "cards: 1\n"
            "verify: null\n"
            "depends-on: [1]\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(beta): card 1\n"
        )
        _write_plan(plan_dir, overview, [
            ("01-alpha.md", batch_a),
            ("02-beta.md", batch_b_text),
        ])

        result = _plan_validate.run(plan_dir, project_root)
        mismatch_errs = [e for e in result if e["check"] == "depends-on-batch-mismatch"]
        if mismatch_errs:
            print(f"FAIL test_depends_on_batch_mismatch_no_finding_on_match: unexpected errors: {mismatch_errs}",
                  file=sys.stderr)
            return 1
        print("PASS test_depends_on_batch_mismatch_no_finding_on_match")
        return 0


def test_depends_on_batch_mismatch_emits_finding() -> int:
    """Dirty: per-batch file's depends-on disagrees with overview's -> one mismatch error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md", "number": 1, "depends-on": []},
            {"name": "beta",  "file": "02-beta.md",  "number": 2, "depends-on": [1]},
        ])
        # Batch file with depends-on NOT matching overview: [] instead of [1]
        batch_a = _make_batch_file("alpha")
        batch_b_text = (
            "# Batch: beta\n\n"
            "```yaml\n"
            "task: test\n"
            "batch: beta\n"
            "cards: 1\n"
            "verify: null\n"
            "depends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(beta): card 1\n"
        )
        _write_plan(plan_dir, overview, [
            ("01-alpha.md", batch_a),
            ("02-beta.md", batch_b_text),
        ])

        result = _plan_validate.run(plan_dir, project_root)
        mismatch_errs = [e for e in result if e["check"] == "depends-on-batch-mismatch"]
        try:
            assert len(mismatch_errs) == 1, f"expected 1 error, got {len(mismatch_errs)}: {mismatch_errs}"
            assert mismatch_errs[0]["batch"] == "beta", f"wrong batch: {mismatch_errs[0]['batch']!r}"
            assert "depends-on" in mismatch_errs[0]["message"], (
                f"message should mention 'depends-on': {mismatch_errs[0]['message']!r}"
            )
            print("PASS test_depends_on_batch_mismatch_emits_finding")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_depends_on_batch_mismatch_emits_finding: {exc}", file=sys.stderr)
            return 1


# ---------------------------------------------------------------------------
# Language-aware verify-not-isolated check (Python markers)
# ---------------------------------------------------------------------------

def test_check_verify_not_isolated_python_marker_pyproject_dirty() -> int:
    """Dirty: Python marker (pyproject.toml) present + no PYTHONPATH= -> one error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        # Create Python marker at project root
        (project_root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify: uv run test.py\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        verify_errs = [e for e in result if e["check"] == "verify-not-isolated"]
        try:
            assert len(verify_errs) == 1, f"expected 1 error, got {len(verify_errs)}: {verify_errs}"
            assert verify_errs[0]["batch"] == "01-alpha", (
                f"wrong batch: {verify_errs[0]['batch']!r}"
            )
            print("PASS test_check_verify_not_isolated_python_marker_pyproject_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_verify_not_isolated_python_marker_pyproject_dirty: {exc}",
                  file=sys.stderr)
            return 1


def test_check_verify_not_isolated_python_marker_setup_py_dirty() -> int:
    """Dirty: Python marker (setup.py) present + no PYTHONPATH= -> one error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        # Create Python marker at project root
        (project_root / "setup.py").write_text("from setuptools import setup\n", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify: pytest test.py\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        verify_errs = [e for e in result if e["check"] == "verify-not-isolated"]
        try:
            assert len(verify_errs) == 1, f"expected 1 error, got {len(verify_errs)}: {verify_errs}"
            print("PASS test_check_verify_not_isolated_python_marker_setup_py_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_verify_not_isolated_python_marker_setup_py_dirty: {exc}",
                  file=sys.stderr)
            return 1


def test_check_verify_not_isolated_python_marker_plugins_mill_clean() -> int:
    """Clean: Python marker (plugins/mill/pyproject.toml) + PYTHONPATH= present -> no error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        # Create Python marker in plugins/mill subdirectory
        (project_root / "plugins" / "mill").mkdir(parents=True)
        (project_root / "plugins" / "mill" / "pyproject.toml").write_text("[project]\n", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify: PYTHONPATH= uv run test.py\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        verify_errs = [e for e in result if e["check"] == "verify-not-isolated"]
        try:
            assert len(verify_errs) == 0, f"expected no errors, got {len(verify_errs)}: {verify_errs}"
            print("PASS test_check_verify_not_isolated_python_marker_plugins_mill_clean")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_verify_not_isolated_python_marker_plugins_mill_clean: {exc}",
                  file=sys.stderr)
            return 1


def test_check_verify_not_isolated_no_python_marker_native_command_clean() -> int:
    """Clean: no Python marker + native verify command (go test) -> no error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        # Create a non-Python marker (go.mod)
        (project_root / "go.mod").write_text("module example.com/test\n", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify: go test ./...\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        verify_errs = [e for e in result if e["check"] == "verify-not-isolated"]
        try:
            assert len(verify_errs) == 0, f"expected no errors, got {len(verify_errs)}: {verify_errs}"
            print("PASS test_check_verify_not_isolated_no_python_marker_native_command_clean")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_verify_not_isolated_no_python_marker_native_command_clean: {exc}",
                  file=sys.stderr)
            return 1


def test_check_verify_not_isolated_no_python_marker_dotnet_test_clean() -> int:
    """Clean: C# project (no Python marker) + dotnet test -> no error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        # Create a C# marker (.csproj)
        (project_root / "Project.csproj").write_text("<Project Sdk=\"Microsoft.NET.Sdk\">\n</Project>\n",
                                                       encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify: dotnet test\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        verify_errs = [e for e in result if e["check"] == "verify-not-isolated"]
        try:
            assert len(verify_errs) == 0, f"expected no errors, got {len(verify_errs)}: {verify_errs}"
            print("PASS test_check_verify_not_isolated_no_python_marker_dotnet_test_clean")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_verify_not_isolated_no_python_marker_dotnet_test_clean: {exc}",
                  file=sys.stderr)
            return 1


# ---------------------------------------------------------------------------
# out-of-worktree-target check
# ---------------------------------------------------------------------------

def test_out_of_worktree_target_home_dir_flags() -> int:
    """Dirty: Edits/Creates with ~/ prefix -> out-of-worktree-target error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", edits=["~/.claude/CLAUDE.md"])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        target_errs = [e for e in result if e["check"] == "out-of-worktree-target"]
        try:
            assert len(target_errs) == 1, f"expected 1 error, got {len(target_errs)}: {target_errs}"
            assert target_errs[0]["path"] == "~/.claude/CLAUDE.md", (
                f"wrong path: {target_errs[0]['path']!r}"
            )
            assert "resolves outside the worktree" in target_errs[0]["message"], (
                f"message should mention 'resolves outside': {target_errs[0]['message']!r}"
            )
            print("PASS test_out_of_worktree_target_home_dir_flags")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_out_of_worktree_target_home_dir_flags: {exc}", file=sys.stderr)
            return 1


def test_out_of_worktree_target_absolute_path_flags() -> int:
    """Dirty: Edits/Creates with absolute path outside tree -> out-of-worktree-target error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        # Create an external directory for the absolute path test
        external_dir = tmp / "external"
        external_dir.mkdir()
        external_file = external_dir / "file.txt"
        external_file.write_text("content", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", edits=[str(external_file)])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        target_errs = [e for e in result if e["check"] == "out-of-worktree-target"]
        try:
            assert len(target_errs) == 1, f"expected 1 error, got {len(target_errs)}: {target_errs}"
            assert "resolves outside the worktree" in target_errs[0]["message"], (
                f"message should mention 'resolves outside': {target_errs[0]['message']!r}"
            )
            print("PASS test_out_of_worktree_target_absolute_path_flags")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_out_of_worktree_target_absolute_path_flags: {exc}", file=sys.stderr)
            return 1


def test_out_of_worktree_target_relative_path_clean() -> int:
    """Clean: Edits/Creates with relative path inside tree -> no error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        # Create file to reference
        (project_root / "src" / "main.py").parent.mkdir(parents=True)
        (project_root / "src" / "main.py").write_text("# code", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", edits=["src/main.py"])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        target_errs = [e for e in result if e["check"] == "out-of-worktree-target"]
        if target_errs:
            print(f"FAIL test_out_of_worktree_target_relative_path_clean: unexpected errors: {target_errs}",
                  file=sys.stderr)
            return 1
        print("PASS test_out_of_worktree_target_relative_path_clean")
        return 0


def test_out_of_worktree_target_creates_nonexistent_clean() -> int:
    """Clean: Creates: target that doesn't yet exist + inside tree -> no error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", creates=["generated/output.py"])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        target_errs = [e for e in result if e["check"] == "out-of-worktree-target"]
        if target_errs:
            print(f"FAIL test_out_of_worktree_target_creates_nonexistent_clean: unexpected errors: {target_errs}",
                  file=sys.stderr)
            return 1
        print("PASS test_out_of_worktree_target_creates_nonexistent_clean")
        return 0


# ---------------------------------------------------------------------------
# batch-oversized check
# ---------------------------------------------------------------------------

def test_batch_oversized_card_count_clean() -> int:
    """Clean: batch with 5 cards (under cap of 10) -> no batch-oversized error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file_cards("alpha", [1, 2, 3, 4, 5])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root, max_cards_per_batch=10)
        oversized_errs = [e for e in result if e["check"] == "batch-oversized"]
        if oversized_errs:
            print(f"FAIL test_batch_oversized_card_count_clean: unexpected errors: {oversized_errs}",
                  file=sys.stderr)
            return 1
        print("PASS test_batch_oversized_card_count_clean")
        return 0


def test_batch_oversized_card_count_dirty() -> int:
    """Dirty: batch with 12 cards (over cap of 10) -> one batch-oversized error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file_cards("alpha", list(range(1, 13)))
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root, max_cards_per_batch=10)
        oversized_errs = [e for e in result if e["check"] == "batch-oversized" and "cards" in e["message"]]
        try:
            assert len(oversized_errs) == 1, f"expected 1 error, got {len(oversized_errs)}: {oversized_errs}"
            assert "12 cards" in oversized_errs[0]["message"], f"message should mention '12 cards': {oversized_errs[0]['message']!r}"
            assert "cap 10" in oversized_errs[0]["message"], f"message should mention 'cap 10': {oversized_errs[0]['message']!r}"
            print("PASS test_batch_oversized_card_count_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_batch_oversized_card_count_dirty: {exc}", file=sys.stderr)
            return 1


def test_batch_oversized_context_tokens_clean() -> int:
    """Clean: batch with small file (under 480k token cap) -> no batch-oversized error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        # Create a small 10KB file (2500 token estimate)
        existing_file = project_root / "src" / "small.py"
        existing_file.parent.mkdir(parents=True)
        existing_file.write_text("x" * 10000, encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", context=["src/small.py"])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root, max_batch_context_tokens=120000)
        oversized_errs = [e for e in result if e["check"] == "batch-oversized" and "tokens" in e["message"]]
        if oversized_errs:
            print(f"FAIL test_batch_oversized_context_tokens_clean: unexpected errors: {oversized_errs}",
                  file=sys.stderr)
            return 1
        print("PASS test_batch_oversized_context_tokens_clean")
        return 0


def test_batch_oversized_context_tokens_dirty() -> int:
    """Dirty: batch with large file (over 12k token cap) -> one batch-oversized error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        # Create a file that's 50KB = 12500 tokens (over 12k cap)
        large_file = project_root / "src" / "large.py"
        large_file.parent.mkdir(parents=True)
        large_file.write_text("x" * 50000, encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", context=["src/large.py"])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root, max_batch_context_tokens=12000)
        oversized_errs = [e for e in result if e["check"] == "batch-oversized" and "tokens" in e["message"]]
        try:
            assert len(oversized_errs) == 1, f"expected 1 error, got {len(oversized_errs)}: {oversized_errs}"
            assert "tokens" in oversized_errs[0]["message"], f"message should mention 'tokens': {oversized_errs[0]['message']!r}"
            assert "cap 12000" in oversized_errs[0]["message"], f"message should mention 'cap 12000': {oversized_errs[0]['message']!r}"
            print("PASS test_batch_oversized_context_tokens_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_batch_oversized_context_tokens_dirty: {exc}", file=sys.stderr)
            return 1


def test_batch_oversized_defaults_applied() -> int:
    """Clean: run() called without max_*_per_batch kwargs applies 10 and 120000 defaults."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file_cards("alpha", list(range(1, 11)))
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        # Call without max_cards_per_batch/max_batch_context_tokens to test defaults
        result = _plan_validate.run(plan_dir, project_root)
        oversized_errs = [e for e in result if e["check"] == "batch-oversized"]
        try:
            assert len(oversized_errs) == 0, (
                f"batch with exactly 10 cards and small files should pass defaults, "
                f"got: {oversized_errs}"
            )
            print("PASS test_batch_oversized_defaults_applied")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_batch_oversized_defaults_applied: {exc}", file=sys.stderr)
            return 1


# ---------------------------------------------------------------------------
# verify-full-suite check
# ---------------------------------------------------------------------------

def test_check_verify_full_suite_run_all_py_without_filter_is_error() -> int:
    """Dirty: verify invokes run-all.py without -k or --only filter -> one verify-full-suite error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        check_full_suite = [e for e in result if e["check"] == "verify-full-suite"]
        try:
            assert len(check_full_suite) == 1, f"expected 1 error, got {len(check_full_suite)}: {check_full_suite}"
            assert check_full_suite[0]["batch"] == "01-alpha", f"wrong batch: {check_full_suite[0]['batch']!r}"
            assert "run-all.py" in check_full_suite[0]["message"], (
                f"message should mention run-all.py: {check_full_suite[0]['message']!r}"
            )
            print("PASS test_check_verify_full_suite_run_all_py_without_filter_is_error")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_verify_full_suite_run_all_py_without_filter_is_error: {exc}", file=sys.stderr)
            return 1


def test_check_verify_full_suite_run_all_py_with_k_filter_is_ok() -> int:
    """Clean: verify invokes run-all.py with -k filter -> no verify-full-suite error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py -k test_foo\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        check_full_suite = [e for e in result if e["check"] == "verify-full-suite"]
        if check_full_suite:
            print(f"FAIL test_check_verify_full_suite_run_all_py_with_k_filter_is_ok: unexpected error: {check_full_suite}",
                  file=sys.stderr)
            return 1
        print("PASS test_check_verify_full_suite_run_all_py_with_k_filter_is_ok")
        return 0


def test_check_verify_full_suite_run_all_py_with_only_is_ok() -> int:
    """Clean: verify invokes run-all.py with --only flag -> no verify-full-suite error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-foo.py\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        check_full_suite = [e for e in result if e["check"] == "verify-full-suite"]
        if check_full_suite:
            print(f"FAIL test_check_verify_full_suite_run_all_py_with_only_is_ok: unexpected error: {check_full_suite}",
                  file=sys.stderr)
            return 1
        print("PASS test_check_verify_full_suite_run_all_py_with_only_is_ok")
        return 0


# ---------------------------------------------------------------------------
# git_root threading tests (Card 5)
# ---------------------------------------------------------------------------

def test_git_root_threading_with_subfolder_cwd_clean() -> int:
    """Clean: project_root is git_root/root subfolder, files at git_root/root/<path>, git_root threaded.

    This test verifies the fix for #471 layout: when project_root is a subfolder
    (root:) of the git repo, and git_root is threaded through the validator,
    resolve_existing_paths should find files at git_root/root/raw correctly
    instead of mis-resolving under a doubled path.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        git_root = tmp / "repo"                    # repo top
        project_root = git_root / "subproject"     # project_root is a subfolder
        plan_dir = git_root / "plan"               # plan dir at repo top

        # Create the project root
        project_root.mkdir(parents=True)

        # Create a source file at git_root/subproject/src/code.py
        source_file = project_root / "src" / "code.py"
        source_file.parent.mkdir(parents=True)
        source_file.write_text("# source code", encoding="utf-8")

        # Create the plan at git_root/plan/ with root: "subproject"
        overview = (
            "# Overview\n\n"
            "```yaml\n"
            'task: test\nslug: test-slug\nroot: "subproject"\n'
            "```\n\n"
            "## Batch Index\n\n"
            "```yaml\n"
            "batches:\n"
            "  - name: alpha\n"
            "    file: 01-alpha.md\n"
            "    depends-on: []\n"
            "    verify: null\n"
            "```\n"
        )
        batch = _make_batch_file("alpha", context=["src/code.py"])
        plan_dir.mkdir(parents=True)
        (plan_dir / "00-overview.md").write_text(overview, encoding="utf-8")
        (plan_dir / "01-alpha.md").write_text(batch, encoding="utf-8")

        # When git_root is provided, the validator should resolve src/code.py
        # against git_root/subproject/src/code.py (primary) before trying
        # project_root/subproject/src/code.py (fallback).
        result = _plan_validate.run(plan_dir, project_root, root="subproject", git_root=git_root)

        # Should have no non-existent-path errors
        check1 = [e for e in result if e["check"] == "non-existent-path"]
        try:
            assert len(check1) == 0, (
                f"expected no non-existent-path errors with git_root threading, "
                f"got: {check1}"
            )
            print("PASS test_git_root_threading_with_subfolder_cwd_clean")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_git_root_threading_with_subfolder_cwd_clean: {exc}", file=sys.stderr)
            return 1


def test_git_root_threading_without_git_root_default_none_documents_required() -> int:
    """Comment: demonstrates why git_root threading is necessary.

    This test documents the potential issue: when project_root is the root
    subfolder itself (git_root/subproject) and root="subproject" is set,
    resolve_existing_paths without git_root will try:
      1. project_root / "subproject" / raw  → DOUBLED, wrong path
      2. project_root / raw  → correct, file is here

    So the file IS found, but only by luck (via the fallback). Threading git_root
    makes git_root/root/raw PRIMARY, which is safer and doesn't depend on
    correct project_root positioning in the worktree.

    This test skips root param to avoid the doubling issue and focus on the
    threading mechanism: it shows that when root="" (default empty), files
    resolve correctly either way.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        git_root = tmp / "repo"
        project_root = git_root / "subproject"
        plan_dir = git_root / "plan"

        project_root.mkdir(parents=True)
        source_file = project_root / "src" / "code.py"
        source_file.parent.mkdir(parents=True)
        source_file.write_text("# source code", encoding="utf-8")

        # Use empty root (the default) to test that the mechanism works
        overview = (
            "# Overview\n\n"
            "```yaml\n"
            'task: test\nslug: test-slug\nroot: ""\n'
            "```\n\n"
            "## Batch Index\n\n"
            "```yaml\n"
            "batches:\n"
            "  - name: alpha\n"
            "    file: 01-alpha.md\n"
            "    depends-on: []\n"
            "    verify: null\n"
            "```\n"
        )
        batch = _make_batch_file("alpha", context=["src/code.py"])
        plan_dir.mkdir(parents=True)
        (plan_dir / "00-overview.md").write_text(overview, encoding="utf-8")
        (plan_dir / "01-alpha.md").write_text(batch, encoding="utf-8")

        # Without git_root and without root param, the validator finds the file
        # at project_root/src/code.py. This test confirms the basic resolution
        # works and documents why git_root threading is still necessary for the
        # subfolder layout case (root="subproject").
        result = _plan_validate.run(plan_dir, project_root)

        check1 = [e for e in result if e["check"] == "non-existent-path"]
        try:
            assert len(check1) == 0, (
                f"expected no non-existent-path errors when root='', "
                f"got: {check1}"
            )
            print("PASS test_git_root_threading_without_git_root_default_none_documents_required")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_git_root_threading_without_git_root_default_none_documents_required: {exc}", file=sys.stderr)
            return 1


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main() -> int:
    tests = [
        test_check_non_existent_path_clean,
        test_check_non_existent_path_dirty,
        test_check_card_missing_field_clean,
        test_check_card_missing_field_dirty,
        test_check_card_numbering_clean,
        test_check_card_numbering_dirty_gap,
        test_check_card_numbering_dirty_cross_batch,
        test_check_depends_on_unknown_clean,
        test_check_depends_on_unknown_dirty,
        test_check_depends_on_unknown_dirty_legacy_string,
        test_depends_on_batch_mismatch_no_finding_on_match,
        test_depends_on_batch_mismatch_emits_finding,
        test_check_parallel_modifies_overlap_clean,
        test_check_parallel_modifies_overlap_dirty,
        test_check_reads_not_backtick_path_clean,
        test_check_reads_not_backtick_path_none_exempt,
        test_check_reads_not_backtick_path_dirty,
        test_check_all_files_touched_mismatch_clean_no_section,
        test_check_all_files_touched_mismatch_dirty,
        test_run_returns_sorted,
        test_run_no_overview,
        # Deletes-aware behaviour (Cards 26–28)
        test_deletes_field_required,
        test_deletes_token_on_disk_clean,
        test_deletes_token_in_creates_union_clean,
        test_deletes_token_missing_not_in_creates_dirty,
        test_reads_token_in_deletes_union_clean,
        test_reads_token_in_creates_union_suppressed,
        test_reads_token_missing_both_unions_dirty,
        test_all_files_touched_deletes_counted,

        test_wiki_config_mutation_clean,
        test_wiki_config_mutation_modifies,
        test_wiki_config_mutation_creates,
        test_wiki_config_mutation_multi_batch,
        test_wiki_config_mutation_modifies_and_creates,
        # skip_checks filtering (Card 7 / #188)
        test_skip_checks_filters_wiki_config_mutation,
        test_skip_checks_does_not_suppress_other_checks,
        test_skip_checks_unknown_check_silently_ignored,
        # verify-not-isolated check
        test_check_verify_not_isolated_null,
        test_check_verify_not_isolated_missing_key,
        test_check_verify_not_isolated_dirty_no_prefix,
        test_check_verify_not_isolated_clean_with_prefix,
        test_check_verify_not_isolated_two_batches_dirty,
        test_check_verify_not_isolated_leading_whitespace,
        test_check_verify_not_isolated_non_empty_pythonpath_value,
        test_check_verify_not_isolated_run_integration,
        # Language-aware verify-not-isolated check (Python markers)
        test_check_verify_not_isolated_python_marker_pyproject_dirty,
        test_check_verify_not_isolated_python_marker_setup_py_dirty,
        test_check_verify_not_isolated_python_marker_plugins_mill_clean,
        test_check_verify_not_isolated_no_python_marker_native_command_clean,
        test_check_verify_not_isolated_no_python_marker_dotnet_test_clean,
        # out-of-worktree-target check
        test_out_of_worktree_target_home_dir_flags,
        test_out_of_worktree_target_absolute_path_flags,
        test_out_of_worktree_target_relative_path_clean,
        test_out_of_worktree_target_creates_nonexistent_clean,
        # batch-oversized check
        test_batch_oversized_card_count_clean,
        test_batch_oversized_card_count_dirty,
        test_batch_oversized_context_tokens_clean,
        test_batch_oversized_context_tokens_dirty,
        test_batch_oversized_defaults_applied,
        # verify-full-suite check
        test_check_verify_full_suite_run_all_py_without_filter_is_error,
        test_check_verify_full_suite_run_all_py_with_k_filter_is_ok,
        test_check_verify_full_suite_run_all_py_with_only_is_ok,
        # git_root threading (Card 5 / #471)
        test_git_root_threading_with_subfolder_cwd_clean,
        test_git_root_threading_without_git_root_default_none_documents_required,
    ]

    errors = 0
    for t in tests:
        try:
            rc = t()
            if rc != 0:
                errors += 1
        except Exception as exc:
            errors += 1
            print(f"FAIL {t.__name__} (unexpected {type(exc).__name__}): {exc}",
                  file=sys.stderr)

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All _plan_validate unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
