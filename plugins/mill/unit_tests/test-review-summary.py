"""Unit tests for plugins/mill/scripts/millpy-review-summary.py.

Loads the CLI module by path via importlib (its filename is not importable as a module name, per
the convention already used by test-millpy-validate-plan.py and friends). Every fixture is
tempfile-based: no real git, no LLM, nothing written outside the temp dir.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

_SUMMARY_PATH = HUB / "plugins" / "mill" / "scripts" / "millpy-review-summary.py"

_spec = importlib.util.spec_from_file_location("millpy_review_summary", str(_SUMMARY_PATH))
_summary_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_summary_mod)


# ---------------------------------------------------------------------------
# parse_review_filename
# ---------------------------------------------------------------------------


def test_parse_review_filename_accepts_holistic_discussion() -> int:
    result = _summary_mod.parse_review_filename("20260418-001200-discussion-review-r1.md")
    try:
        assert result == {"round": 1, "type": "discussion", "scope": "holistic"}, result
        print("PASS test_parse_review_filename_accepts_holistic_discussion")
        return 0
    except AssertionError as exc:
        print(f"FAIL test_parse_review_filename_accepts_holistic_discussion: {exc}", file=sys.stderr)
        return 1


def test_parse_review_filename_accepts_batch_plan() -> int:
    result = _summary_mod.parse_review_filename("20260418-143300-plan-review-03-templates-r2.md")
    try:
        assert result == {"round": 2, "type": "plan", "scope": "03-templates"}, result
        print("PASS test_parse_review_filename_accepts_batch_plan")
        return 0
    except AssertionError as exc:
        print(f"FAIL test_parse_review_filename_accepts_batch_plan: {exc}", file=sys.stderr)
        return 1


def test_parse_review_filename_accepts_batch_code() -> int:
    result = _summary_mod.parse_review_filename("20260418-143300-code-review-05-cards-r3.md")
    try:
        assert result == {"round": 3, "type": "code", "scope": "05-cards"}, result
        print("PASS test_parse_review_filename_accepts_batch_code")
        return 0
    except AssertionError as exc:
        print(f"FAIL test_parse_review_filename_accepts_batch_code: {exc}", file=sys.stderr)
        return 1


def test_parse_review_filename_accepts_holistic_code() -> int:
    result = _summary_mod.parse_review_filename("20260418-143300-code-review-r5.md")
    try:
        assert result == {"round": 5, "type": "code", "scope": "holistic"}, result
        print("PASS test_parse_review_filename_accepts_holistic_code")
        return 0
    except AssertionError as exc:
        print(f"FAIL test_parse_review_filename_accepts_holistic_code: {exc}", file=sys.stderr)
        return 1


def test_parse_review_filename_rejects_fix_report() -> int:
    result = _summary_mod.parse_review_filename("20260418-143300-plan-fix-r2.md")
    try:
        assert result is None, result
        print("PASS test_parse_review_filename_rejects_fix_report")
        return 0
    except AssertionError as exc:
        print(f"FAIL test_parse_review_filename_rejects_fix_report: {exc}", file=sys.stderr)
        return 1


def test_parse_review_filename_rejects_arbitrary_name() -> int:
    result = _summary_mod.parse_review_filename("notes.md")
    try:
        assert result is None, result
        print("PASS test_parse_review_filename_rejects_arbitrary_name")
        return 0
    except AssertionError as exc:
        print(f"FAIL test_parse_review_filename_rejects_arbitrary_name: {exc}", file=sys.stderr)
        return 1


# ---------------------------------------------------------------------------
# build_rows
# ---------------------------------------------------------------------------


_NEW_FORMAT_FILE = """# Review: batch

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
duration_s: 37.4
tool_calls: 12
cost_usd: 0.4212
```

## Findings
(no findings)

## Verdict
APPROVE
Looks good.
"""

_OLD_FORMAT_FILE = """# Review: batch

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
```

## Findings
(no findings)

## Verdict
REQUEST_CHANGES
Needs work.
"""

_MALFORMED_YAML_FILE = """# Review: batch

```yaml
verdict: APPROVE
reviewer_model: [unterminated
```

## Verdict
APPROVE
Malformed header.
"""

_NO_FENCE_FILE = """# Review: batch

verdict: APPROVE

## Verdict
APPROVE
No fenced yaml block at all.
"""


def test_build_rows_handles_mixed_formats_without_raising() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        reviews_dir = Path(tmp)
        (reviews_dir / "20260418-100000-code-review-r1.md").write_text(
            _NEW_FORMAT_FILE, encoding="utf-8"
        )
        (reviews_dir / "20260418-100100-code-review-r2.md").write_text(
            _OLD_FORMAT_FILE, encoding="utf-8"
        )
        (reviews_dir / "20260418-100200-code-review-r3.md").write_text(
            _MALFORMED_YAML_FILE, encoding="utf-8"
        )
        (reviews_dir / "20260418-100300-code-review-r4.md").write_text(
            _NO_FENCE_FILE, encoding="utf-8"
        )

        rows = _summary_mod.build_rows(reviews_dir, registry=None)

        try:
            assert len(rows) == 4, f"expected 4 rows, got {len(rows)}"
            by_round = {row["round"]: row for row in rows}

            new_row = by_round[1]
            assert new_row["verdict"] == "APPROVE"
            assert new_row["model"] == "sonnetmax"
            assert new_row["duration_s"] == 37.4
            assert new_row["tool_calls"] == 12
            assert new_row["cost_usd"] == 0.4212

            old_row = by_round[2]
            assert old_row["verdict"] == "REQUEST_CHANGES"
            assert old_row["model"] == "sonnethigh"
            assert old_row["duration_s"] is None
            assert old_row["tool_calls"] is None
            assert old_row["cost_usd"] is None

            malformed_row = by_round[3]
            assert malformed_row["verdict"] is None
            assert malformed_row["model"] is None

            no_fence_row = by_round[4]
            assert no_fence_row["verdict"] is None
            assert no_fence_row["model"] is None

            print("PASS test_build_rows_handles_mixed_formats_without_raising")
            return 0
        except AssertionError as exc:
            print(
                f"FAIL test_build_rows_handles_mixed_formats_without_raising: {exc}",
                file=sys.stderr,
            )
            return 1


def test_build_rows_includes_revise_subdirectory() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        reviews_dir = Path(tmp)
        revise_dir = reviews_dir / "revise-1"
        revise_dir.mkdir()
        (revise_dir / "20260418-110000-plan-review-r1.md").write_text(
            _NEW_FORMAT_FILE, encoding="utf-8"
        )

        rows = _summary_mod.build_rows(reviews_dir, registry=None)

        try:
            assert len(rows) == 1, f"expected 1 row, got {len(rows)}"
            assert rows[0]["file"] == "20260418-110000-plan-review-r1.md"
            print("PASS test_build_rows_includes_revise_subdirectory")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_build_rows_includes_revise_subdirectory: {exc}", file=sys.stderr)
            return 1


def test_build_rows_excludes_fix_reports() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        reviews_dir = Path(tmp)
        (reviews_dir / "20260418-100000-code-review-r1.md").write_text(
            _NEW_FORMAT_FILE, encoding="utf-8"
        )
        (reviews_dir / "20260418-100100-plan-fix-r1.md").write_text(
            "not a review file", encoding="utf-8"
        )

        rows = _summary_mod.build_rows(reviews_dir, registry=None)

        try:
            assert len(rows) == 1, f"expected 1 row, got {len(rows)}"
            print("PASS test_build_rows_excludes_fix_reports")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_build_rows_excludes_fix_reports: {exc}", file=sys.stderr)
            return 1


def test_rows_sorted_by_round_then_scope_by_default() -> int:
    rows = [
        {"round": 2, "type": "code", "scope": "holistic", "verdict": "APPROVE", "model": None,
         "effort": None, "duration_s": None, "tool_calls": None, "cost_usd": None, "file": "b.md"},
        {"round": 1, "type": "code", "scope": "05-cards", "verdict": "APPROVE", "model": None,
         "effort": None, "duration_s": None, "tool_calls": None, "cost_usd": None, "file": "a.md"},
        {"round": 1, "type": "code", "scope": "01-setup", "verdict": "APPROVE", "model": None,
         "effort": None, "duration_s": None, "tool_calls": None, "cost_usd": None, "file": "c.md"},
    ]
    sorted_rows = sorted(rows, key=_summary_mod._sort_key_round)
    try:
        assert [r["file"] for r in sorted_rows] == ["c.md", "a.md", "b.md"], sorted_rows
        print("PASS test_rows_sorted_by_round_then_scope_by_default")
        return 0
    except AssertionError as exc:
        print(f"FAIL test_rows_sorted_by_round_then_scope_by_default: {exc}", file=sys.stderr)
        return 1


# ---------------------------------------------------------------------------
# format_duration
# ---------------------------------------------------------------------------


def test_format_duration_variants() -> int:
    try:
        assert _summary_mod.format_duration(None) == "n/a"
        assert _summary_mod.format_duration(37.4) == "37s"
        assert _summary_mod.format_duration(252.0) == "4m12s"
        print("PASS test_format_duration_variants")
        return 0
    except AssertionError as exc:
        print(f"FAIL test_format_duration_variants: {exc}", file=sys.stderr)
        return 1


# ---------------------------------------------------------------------------
# render_table
# ---------------------------------------------------------------------------


def test_render_table_shows_na_for_missing_cells() -> int:
    rows = [
        {"round": 1, "type": "code", "scope": "holistic", "verdict": "REQUEST_CHANGES",
         "model": "sonnethigh", "effort": None, "duration_s": None, "tool_calls": None,
         "cost_usd": None, "file": "x.md"},
    ]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        _summary_mod.render_table(rows, no_color=True, sort_by="round")
    output = buf.getvalue()
    lines = output.splitlines()

    try:
        assert output.count("n/a") == 4, output  # effort, duration, tools, cost
        assert len(lines) == 3, f"expected header + separator + 1 data row, got {len(lines)}"
        print("PASS test_render_table_shows_na_for_missing_cells")
        return 0
    except AssertionError as exc:
        print(f"FAIL test_render_table_shows_na_for_missing_cells: {exc}", file=sys.stderr)
        return 1


# ---------------------------------------------------------------------------
# --json shape
# ---------------------------------------------------------------------------


def test_json_shape_keeps_raw_numbers() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        reviews_dir = Path(tmp)
        (reviews_dir / "20260418-100000-code-review-r1.md").write_text(
            _NEW_FORMAT_FILE, encoding="utf-8"
        )
        rows = _summary_mod.build_rows(reviews_dir, registry=None)
        try:
            assert rows[0]["duration_s"] == 37.4, rows[0]["duration_s"]
            assert isinstance(rows[0]["duration_s"], float), type(rows[0]["duration_s"])
            print("PASS test_json_shape_keeps_raw_numbers")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_json_shape_keeps_raw_numbers: {exc}", file=sys.stderr)
            return 1


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def main() -> int:
    tests = [
        test_parse_review_filename_accepts_holistic_discussion,
        test_parse_review_filename_accepts_batch_plan,
        test_parse_review_filename_accepts_batch_code,
        test_parse_review_filename_accepts_holistic_code,
        test_parse_review_filename_rejects_fix_report,
        test_parse_review_filename_rejects_arbitrary_name,
        test_build_rows_handles_mixed_formats_without_raising,
        test_build_rows_includes_revise_subdirectory,
        test_build_rows_excludes_fix_reports,
        test_rows_sorted_by_round_then_scope_by_default,
        test_format_duration_variants,
        test_render_table_shows_na_for_missing_cells,
        test_json_shape_keeps_raw_numbers,
    ]

    errors = 0
    for t in tests:
        try:
            rc = t()
            if rc != 0:
                errors += 1
        except Exception as exc:
            errors += 1
            print(f"FAIL {t.__name__} (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All millpy-review-summary unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
