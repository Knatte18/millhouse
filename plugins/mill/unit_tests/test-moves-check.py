"""Unit tests for _moves_check.planned_rename_findings.

Tests exercise the pure rename-finding logic with crafted diff strings;
no real git invocation is made.  Covers:
  - A planned pair shown as R100 or R030 yields no finding.
  - A planned pair shown as separate A+D lines yields one NIT.
  - Multiple planned moves with mixed outcomes.
  - Empty moves list returns empty list.
  - Malformed or blank diff text yields no crash.
  - CRLF-terminated diff string parses identically to LF case.
"""
from __future__ import annotations

import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _moves_check  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _nit_count(findings: list[str]) -> int:
    """Count findings that carry the [NIT] marker."""
    return sum(1 for f in findings if "[NIT]" in f)


def _mentions_pair(findings: list[str], src: str, dst: str) -> bool:
    """Return True if any finding mentions both src and dst."""
    return any(src in f and dst in f for f in findings)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_rename_detected_r100_yields_no_finding() -> None:
    """A move pair reported as R100 (identical content rename) produces no NIT."""
    diff = "R100\told/module.py\tnew/module.py\n"
    moves = [("old/module.py", "new/module.py")]
    findings = _moves_check.planned_rename_findings(diff, moves)
    assert findings == [], f"expected no findings for R100, got {findings}"
    print("PASS test_rename_detected_r100_yields_no_finding")


def test_rename_detected_r030_yields_no_finding() -> None:
    """A move pair reported as R030 (low similarity) still produces no NIT."""
    diff = "R030\told/a.py\tnew/a.py\n"
    moves = [("old/a.py", "new/a.py")]
    findings = _moves_check.planned_rename_findings(diff, moves)
    assert findings == [], f"expected no findings for R030, got {findings}"
    print("PASS test_rename_detected_r030_yields_no_finding")


def test_add_delete_pair_yields_one_nit() -> None:
    """A planned pair shown as separate A+D entries (no R line) yields one NIT."""
    diff = (
        "A\tnew/module.py\n"
        "D\told/module.py\n"
    )
    moves = [("old/module.py", "new/module.py")]
    findings = _moves_check.planned_rename_findings(diff, moves)
    assert len(findings) == 1, f"expected 1 NIT, got {len(findings)}"
    assert "[NIT]" in findings[0], f"finding missing [NIT] marker: {findings[0]}"
    assert "old/module.py" in findings[0], "source path missing from finding"
    assert "new/module.py" in findings[0], "destination path missing from finding"
    print("PASS test_add_delete_pair_yields_one_nit")


def test_mixed_outcomes_multiple_moves() -> None:
    """Multiple planned moves: detected renames yield no finding; undetected yield NITs."""
    diff = (
        "R085\told/keeper.py\tnew/keeper.py\n"  # detected -- no NIT
        "M\tunrelated.py\n"
        "A\tnew/rewrite.py\n"                    # not a rename -- NIT expected
        "D\told/rewrite.py\n"
    )
    moves = [
        ("old/keeper.py", "new/keeper.py"),   # in rename set
        ("old/rewrite.py", "new/rewrite.py"), # NOT in rename set
    ]
    findings = _moves_check.planned_rename_findings(diff, moves)
    assert len(findings) == 1, f"expected 1 NIT (one undetected move), got {len(findings)}"
    assert _mentions_pair(findings, "old/rewrite.py", "new/rewrite.py"), (
        "NIT should reference the undetected pair"
    )
    assert not _mentions_pair(findings, "old/keeper.py", "new/keeper.py"), (
        "detected rename should not appear in findings"
    )
    print("PASS test_mixed_outcomes_multiple_moves")


def test_empty_moves_returns_empty_list() -> None:
    """Empty moves list returns [] without parsing diff text."""
    diff = "R100\told/x.py\tnew/x.py\n"
    findings = _moves_check.planned_rename_findings(diff, [])
    assert findings == [], f"expected [] for empty moves, got {findings}"
    print("PASS test_empty_moves_returns_empty_list")


def test_blank_diff_text_no_crash() -> None:
    """Blank or whitespace-only diff text yields one NIT per move (no crash)."""
    findings_blank = _moves_check.planned_rename_findings("", [("a.py", "b.py")])
    assert len(findings_blank) == 1, f"expected 1 NIT for blank diff, got {len(findings_blank)}"

    findings_whitespace = _moves_check.planned_rename_findings("   \n\n\t\n", [("a.py", "b.py")])
    assert len(findings_whitespace) == 1, (
        f"expected 1 NIT for whitespace-only diff, got {len(findings_whitespace)}"
    )
    print("PASS test_blank_diff_text_no_crash")


def test_malformed_diff_lines_no_crash() -> None:
    """Lines without the expected tab structure are silently skipped."""
    diff = (
        "not a valid diff line\n"
        "R\tonly_one_column\n"        # too few columns for rename
        "R100\told.py\tnew.py\n"      # valid rename
    )
    moves = [
        ("old.py", "new.py"),         # detected -- no NIT
        ("missing_src.py", "missing_dst.py"),  # no line at all -- NIT
    ]
    findings = _moves_check.planned_rename_findings(diff, moves)
    assert len(findings) == 1, f"expected 1 NIT for undetected pair, got {len(findings)}"
    assert _mentions_pair(findings, "missing_src.py", "missing_dst.py"), (
        "NIT should reference the undetected pair"
    )
    print("PASS test_malformed_diff_lines_no_crash")


def test_crlf_diff_parses_identically_to_lf() -> None:
    """CRLF-terminated diff string produces the same result as LF-terminated."""
    lf_diff = "R100\told/x.py\tnew/x.py\nA\tnew/y.py\nD\told/y.py\n"
    crlf_diff = lf_diff.replace("\n", "\r\n")
    moves = [
        ("old/x.py", "new/x.py"),   # detected rename in both
        ("old/y.py", "new/y.py"),   # add+delete in both -> NIT
    ]
    lf_findings = _moves_check.planned_rename_findings(lf_diff, moves)
    crlf_findings = _moves_check.planned_rename_findings(crlf_diff, moves)
    assert len(lf_findings) == 1, f"LF: expected 1 NIT, got {len(lf_findings)}"
    assert len(crlf_findings) == 1, f"CRLF: expected 1 NIT, got {len(crlf_findings)}"
    assert lf_findings == crlf_findings, (
        f"CRLF and LF results differ:\nLF: {lf_findings}\nCRLF: {crlf_findings}"
    )
    print("PASS test_crlf_diff_parses_identically_to_lf")


def main() -> int:
    """Run all tests and report results."""
    tests = [
        test_rename_detected_r100_yields_no_finding,
        test_rename_detected_r030_yields_no_finding,
        test_add_delete_pair_yields_one_nit,
        test_mixed_outcomes_multiple_moves,
        test_empty_moves_returns_empty_list,
        test_blank_diff_text_no_crash,
        test_malformed_diff_lines_no_crash,
        test_crlf_diff_parses_identically_to_lf,
    ]
    failures: list[str] = []
    for fn in tests:
        try:
            fn()
        except AssertionError as exc:
            print(f"FAIL [{fn.__name__}]: {exc}", file=sys.stderr)
            failures.append(fn.__name__)
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR [{fn.__name__}]: {type(exc).__name__}: {exc}", file=sys.stderr)
            failures.append(fn.__name__)
    if failures:
        print(f"\n{len(failures)} test(s) failed: {failures}", file=sys.stderr)
        return 1
    print("All _moves_check tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
