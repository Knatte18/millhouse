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

    Each batch dict: {name, file, depends-on (optional, default [])}.
    all_files_touched: optional list of path strings for the section.
    """
    entries = []
    for b in batches:
        deps = b.get("depends-on", [])
        deps_yaml = "[" + ", ".join(f'"{d}"' for d in deps) + "]"
        entries.append(
            f"  - name: {b['name']}\n"
            f"    file: {b['file']}\n"
            f"    depends-on: {deps_yaml}\n"
            f"    verify: null"
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
    reads: list[str] | None = None,
    modifies: list[str] | None = None,
    creates: list[str] | None = None,
    deletes: list[str] | None = None,
    missing_fields: set[str] | None = None,
) -> str:
    """Return a well-formed batch file with one card.

    reads/modifies/creates/deletes: list of path strings (backtick-wrapped
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
    if "Reads" not in missing_fields:
        parts.append(f"- **Reads:** {fmt(reads)}\n")
    if "Modifies" not in missing_fields:
        parts.append(f"- **Modifies:** {fmt(modifies)}\n")
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
            "- **Reads:** none\n"
            "- **Modifies:** none\n"
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
    """Clean: all Reads:/Creates: paths exist on disk → no errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"

        existing_file = project_root / "src" / "a.py"
        existing_file.parent.mkdir(parents=True)
        existing_file.write_text("# placeholder", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", reads=["src/a.py"])
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
    """Dirty: Reads: has nonexistent/path.py → one non-existent-path error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", reads=["nonexistent/path.py"])
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
    """Clean: all required fields present → no card-missing-field errors."""
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
    """Dirty: card omits Modifies: → one card-missing-field error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", missing_fields={"Modifies"})
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check2 = [e for e in result if e["check"] == "card-missing-field"]
        try:
            assert len(check2) == 1, f"expected 1 error, got {len(check2)}: {check2}"
            assert check2[0]["card"] == 1, f"wrong card: {check2[0]['card']}"
            assert "Modifies" in check2[0]["message"], (
                f"message should mention 'Modifies': {check2[0]['message']!r}"
            )
            print("PASS test_check_card_missing_field_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_card_missing_field_dirty: {exc}", file=sys.stderr)
            return 1


def test_check_card_numbering_clean() -> int:
    """Clean: sequential cards [1, 2, 3] → no card-numbering errors."""
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
    """Dirty: cards [1, 2, 4] in one batch → one card-numbering error."""
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
    """Dirty: card 1 in batch-a AND batch-b → two card-numbering errors."""
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
    """Clean: no depends-on entries → no depends-on-unknown errors."""
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
    """Dirty: depends-on references non-existent-batch → one depends-on-unknown error."""
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
            print("PASS test_check_depends_on_unknown_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_depends_on_unknown_dirty: {exc}", file=sys.stderr)
            return 1


def test_check_parallel_modifies_overlap_clean() -> int:
    """Clean: batch-b depends on batch-a, both modify same file → no error (not parallel-eligible)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md", "depends-on": []},
            {"name": "beta",  "file": "02-beta.md",  "depends-on": ["alpha"]},
        ])
        batch_a = _make_batch_file("alpha", modifies=["shared/file.py"])
        batch_b = _make_batch_file("beta",  modifies=["shared/file.py"])
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
    """Dirty: two batches with no deps both modify shared/file.py → one error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md", "depends-on": []},
            {"name": "beta",  "file": "02-beta.md",  "depends-on": []},
        ])
        batch_a = _make_batch_file("alpha", card_num=1, modifies=["shared/file.py"])
        batch_b = _make_batch_file("beta",  card_num=2, modifies=["shared/file.py"])
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
    """Clean: backtick-only bullets and 'none' sentinel → no reads-not-backtick-path errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"

        # Create the referenced file so check 1 doesn't fire.
        (project_root / "src").mkdir(parents=True)
        (project_root / "src" / "a.py").write_text("# placeholder", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        # Single-line backtick: clean; Modifies: none (exempt)
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify: null\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: description\n\n"
            "- **Reads:** `src/a.py`\n"
            "- **Modifies:** none\n"
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
    """Clean: `- **Reads:** none` returns [] for check 6."""
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
    """Dirty: Reads: bullet has prose alongside backtick path → one reads-not-backtick-path error."""
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
            "- **Reads:** `src/foo.py` (used by foo)\n"
            "- **Modifies:** none\n"
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
    """Clean: overview without All Files Touched section → no errors for check 8."""
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
    """Dirty: overview lists path/extra.py not in any card's Modifies:/Creates: → one error."""
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
        # 01-alpha: card missing Modifies → card-missing-field (batch=01-alpha, card=1)
        batch_a = _make_batch_file("alpha", missing_fields={"Modifies"})
        # 02-beta: nonexistent path → non-existent-path (batch=02-beta, card=None→0)
        batch_b = _make_batch_file("beta", reads=["nonexistent/thing.py"])
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
    """Empty plan_dir (no overview) → one missing-overview error."""
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
        test_check_parallel_modifies_overlap_clean,
        test_check_parallel_modifies_overlap_dirty,
        test_check_reads_not_backtick_path_clean,
        test_check_reads_not_backtick_path_none_exempt,
        test_check_reads_not_backtick_path_dirty,
        test_check_all_files_touched_mismatch_clean_no_section,
        test_check_all_files_touched_mismatch_dirty,
        test_run_returns_sorted,
        test_run_no_overview,
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
