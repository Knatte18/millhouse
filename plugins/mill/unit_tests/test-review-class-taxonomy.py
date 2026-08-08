"""Unit tests for the class taxonomy added to plugins/mill/scripts/_review_common.py.

Covers: the per-stage blocking_classes ceiling table (resolve_blocking_classes +
finalize_scope), demote-only behaviour, the demotion rewrite (both the heading and
fenced-yaml mechanisms, asserted against the file written to disk), the re-read round
trip through extract_findings, verdict derivation from the surviving blocking count,
unknown-class handling, the no-double-count regression, mixed-format documents,
cross-mechanism and same-mechanism title deduplication, resolve_blocking_classes'
per-stage defaults, and parse_verdict's GAPS_FOUND -> REQUEST_CHANGES normalisation.

No real git, no real LLM -- tempfile fixtures only, via _test_helpers.safe_temp_dir.
"""
from __future__ import annotations

import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

_UNIT_TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_UNIT_TESTS))

import _test_helpers  # noqa: E402

from _review_common import (  # noqa: E402
    DEFAULT_BLOCKING_CLASSES,
    RECOGNIZED_CLASSES,
    extract_findings,
    finalize_scope,
    parse_verdict,
    resolve_blocking_classes,
)


def _finalize(
    tmpdir: Path,
    review_type: str,
    raw: str,
    *,
    round_n: int = 1,
    scope: str | None = None,
    blocking_classes: frozenset[str] | None = None,
) -> tuple[dict, str]:
    """Run finalize_scope against a fresh reviews_dir under tmpdir and return (result, written_text).

    written_text is read back from disk -- never the in-memory raw_text -- so assertions against it
    exercise the actual file/envelope agreement the demotion-rewritten-into-review-file Shared
    Decision requires.
    """
    reviews_dir = tmpdir / "reviews"
    result = finalize_scope(
        reviews_dir,
        review_type,
        round_n,
        raw,
        scope=scope,
        blocking_classes=blocking_classes,
    )
    written_text = Path(result["file"]).read_text(encoding="utf-8")
    return result, written_text


def _heading(severity: str, cls: str | None, title: str) -> str:
    bracket = f"{severity}:{cls}" if cls else severity
    return f"### [{bracket}] {title}\n"


def _yaml_block(entries: list[dict]) -> str:
    lines = ["```yaml", "findings:"]
    for entry in entries:
        first = True
        for key, value in entry.items():
            prefix = "  - " if first else "    "
            lines.append(f"{prefix}{key}: {value}")
            first = False
    lines.append("```")
    return "\n".join(lines) + "\n"


def _verdict_yaml(verdict: str = "REQUEST_CHANGES") -> str:
    return f"```yaml\nverdict: {verdict}\n```\n"


# ---------------------------------------------------------------------------
# Ceiling table: one finding per class, for each of the three stages.
# ---------------------------------------------------------------------------


def test_ceiling_table_discussion() -> bool:
    with _test_helpers.safe_temp_dir() as tmpdir:
        blocking_classes = resolve_blocking_classes({}, "discussion", None)
        raw = _verdict_yaml() + "".join(
            _heading("BLOCKING", cls, f"finding-{cls}") for cls in RECOGNIZED_CLASSES
        )
        result, _ = _finalize(
            tmpdir, "discussion", raw, blocking_classes=blocking_classes
        )
        return result["blocking_count"] == 1 and result["nit_count"] == 3


def test_ceiling_table_plan() -> bool:
    with _test_helpers.safe_temp_dir() as tmpdir:
        blocking_classes = resolve_blocking_classes({}, "plan", "holistic")
        raw = _verdict_yaml() + "".join(
            _heading("BLOCKING", cls, f"finding-{cls}") for cls in RECOGNIZED_CLASSES
        )
        result, _ = _finalize(tmpdir, "plan", raw, blocking_classes=blocking_classes)
        return result["blocking_count"] == 2 and result["nit_count"] == 2


def test_ceiling_table_code() -> bool:
    with _test_helpers.safe_temp_dir() as tmpdir:
        blocking_classes = resolve_blocking_classes({}, "code", "holistic")
        raw = _verdict_yaml() + "".join(
            _heading("BLOCKING", cls, f"finding-{cls}") for cls in RECOGNIZED_CLASSES
        )
        result, _ = _finalize(tmpdir, "code", raw, blocking_classes=blocking_classes)
        return result["blocking_count"] == 4 and result["nit_count"] == 0


# ---------------------------------------------------------------------------
# Demote-only: the ceiling never promotes.
# ---------------------------------------------------------------------------


def test_ceiling_never_promotes() -> bool:
    with _test_helpers.safe_temp_dir() as tmpdir:
        blocking_classes = resolve_blocking_classes({}, "discussion", None)
        raw = _verdict_yaml("APPROVE") + _heading("NIT", "design", "already a nit")
        result, _ = _finalize(
            tmpdir, "discussion", raw, blocking_classes=blocking_classes
        )
        return result["blocking_count"] == 0 and result["nit_count"] == 1


# ---------------------------------------------------------------------------
# Demotion rewrite: heading mechanism, asserted against the file on disk.
# ---------------------------------------------------------------------------


def test_demotion_rewrite_heading_on_disk() -> bool:
    with _test_helpers.safe_temp_dir() as tmpdir:
        blocking_classes = resolve_blocking_classes({}, "discussion", None)
        raw = _verdict_yaml() + _heading("BLOCKING", "scope", "missed call sites")
        _, written_text = _finalize(
            tmpdir, "discussion", raw, blocking_classes=blocking_classes
        )
        return (
            "### [NIT:scope] missed call sites" in written_text
            and "**Demoted-from:** BLOCKING" in written_text
            and "### [BLOCKING:scope]" not in written_text
        )


# ---------------------------------------------------------------------------
# Demotion rewrite: YAML-only mechanism, asserted against the file on disk.
# ---------------------------------------------------------------------------


def test_demotion_rewrite_yaml_only_on_disk() -> bool:
    with _test_helpers.safe_temp_dir() as tmpdir:
        blocking_classes = resolve_blocking_classes({}, "discussion", None)
        raw = _verdict_yaml() + _yaml_block(
            [{"severity": "BLOCKING", "class": "scope", "title": "yaml-only finding"}]
        )
        _, written_text = _finalize(
            tmpdir, "discussion", raw, blocking_classes=blocking_classes
        )
        return "severity: NIT" in written_text and "demoted_from: BLOCKING" in written_text


# ---------------------------------------------------------------------------
# A title present in both mechanisms, demoted: both representations rewritten,
# findings carries exactly one entry for it.
# ---------------------------------------------------------------------------


def test_demotion_rewrite_both_mechanisms_dedup_to_one_finding() -> bool:
    with _test_helpers.safe_temp_dir() as tmpdir:
        blocking_classes = resolve_blocking_classes({}, "discussion", None)
        raw = (
            _verdict_yaml()
            + _heading("BLOCKING", "scope", "shared title")
            + _yaml_block(
                [{"severity": "BLOCKING", "class": "scope", "title": "shared title"}]
            )
        )
        result, written_text = _finalize(
            tmpdir, "discussion", raw, blocking_classes=blocking_classes
        )
        matching = [f for f in result["findings"] if f["title"] == "shared title"]
        return (
            len(matching) == 1
            and "### [NIT:scope] shared title" in written_text
            and "**Demoted-from:** BLOCKING" in written_text
            and "severity: NIT" in written_text
            and "demoted_from: BLOCKING" in written_text
        )


# ---------------------------------------------------------------------------
# Re-read round trip: text written by a demoting finalize_scope call, fed back into a
# bare extract_findings call, reports demoted:true from the marker alone -- both mechanisms.
# ---------------------------------------------------------------------------


def test_reread_round_trip_reports_demoted_from_marker() -> bool:
    with _test_helpers.safe_temp_dir() as tmpdir:
        blocking_classes = resolve_blocking_classes({}, "discussion", None)
        raw = (
            _verdict_yaml()
            + _heading("BLOCKING", "scope", "heading demoted")
            + _yaml_block(
                [{"severity": "BLOCKING", "class": "scope", "title": "yaml demoted"}]
            )
        )
        _, written_text = _finalize(
            tmpdir, "discussion", raw, blocking_classes=blocking_classes
        )
        reread = {f.title: f for f in extract_findings(written_text)}
        return (
            reread["heading demoted"].demoted is True
            and reread["heading demoted"].severity == "NIT"
            and reread["yaml demoted"].demoted is True
            and reread["yaml demoted"].severity == "NIT"
        )


# ---------------------------------------------------------------------------
# Verdict derivation: [BLOCKING:scope]-only at discussion stage yields APPROVE.
# ---------------------------------------------------------------------------


def test_verdict_derivation_discussion_scope_only_approves() -> bool:
    with _test_helpers.safe_temp_dir() as tmpdir:
        blocking_classes = resolve_blocking_classes({}, "discussion", None)
        raw = _verdict_yaml() + _heading("BLOCKING", "scope", "missed call sites")
        result, _ = _finalize(
            tmpdir, "discussion", raw, blocking_classes=blocking_classes
        )
        return (
            result["verdict"] == "APPROVE"
            and result["nit_count"] == 1
            and result["blocking_count"] == 0
        )


# ---------------------------------------------------------------------------
# Unknown-class handling: stated severity is preserved, no demotion occurs.
# ---------------------------------------------------------------------------


def test_unknown_class_preserves_severity_and_exempts_ceiling() -> bool:
    with _test_helpers.safe_temp_dir() as tmpdir:
        blocking_classes = resolve_blocking_classes({}, "discussion", None)
        raw = (
            _verdict_yaml()
            + _heading("BLOCKING", "perf", "unclassed blocking with unknown class")
            + _heading("BLOCKING", None, "bare blocking")
            + _heading("NIT", "perf", "unclassed nit with unknown class")
            + _heading("NIT", None, "bare nit")
        )
        result, _ = _finalize(
            tmpdir, "discussion", raw, blocking_classes=blocking_classes
        )
        by_title = {f["title"]: f for f in result["findings"]}
        return (
            by_title["unclassed blocking with unknown class"]["severity"] == "BLOCKING"
            and by_title["unclassed blocking with unknown class"]["demoted"] is False
            and by_title["bare blocking"]["severity"] == "BLOCKING"
            and by_title["bare blocking"]["demoted"] is False
            and by_title["unclassed nit with unknown class"]["severity"] == "NIT"
            and by_title["bare nit"]["severity"] == "NIT"
            and result["blocking_count"] == 2
            and result["nit_count"] == 2
        )


# ---------------------------------------------------------------------------
# No-double-count regression: a single [NIT:perf] contributes exactly 1 to nit_count,
# 0 to blocking_count, and appears exactly once in findings -- all asserted together.
# ---------------------------------------------------------------------------


def test_no_double_count_nit_with_unknown_class() -> bool:
    with _test_helpers.safe_temp_dir() as tmpdir:
        blocking_classes = resolve_blocking_classes({}, "code", "holistic")
        raw = _verdict_yaml("APPROVE") + _heading("NIT", "perf", "cosmetic nit")
        result, _ = _finalize(tmpdir, "code", raw, blocking_classes=blocking_classes)
        matching = [f for f in result["findings"] if f["title"] == "cosmetic nit"]
        return (
            result["nit_count"] == 1
            and result["blocking_count"] == 0
            and len(matching) == 1
        )


# ---------------------------------------------------------------------------
# Mixed-format document: markdown headings for one severity, a fenced yaml block for the
# other, with an unknown class hidden in whichever mechanism the known labels did not use.
# ---------------------------------------------------------------------------


def test_mixed_format_document_hides_no_finding() -> bool:
    with _test_helpers.safe_temp_dir() as tmpdir:
        blocking_classes = resolve_blocking_classes({}, "code", "holistic")
        raw = (
            _verdict_yaml()
            + _heading("BLOCKING", "design", "heading blocking finding")
            + _heading("BLOCKING", "perf", "heading blocking unknown class")
            + _yaml_block(
                [
                    {"severity": "NIT", "class": "consistency", "title": "yaml nit finding"},
                    {"severity": "NIT", "class": "perf", "title": "yaml nit unknown class"},
                ]
            )
        )
        result, _ = _finalize(tmpdir, "code", raw, blocking_classes=blocking_classes)
        titles = {f["title"] for f in result["findings"]}
        expected = {
            "heading blocking finding",
            "heading blocking unknown class",
            "yaml nit finding",
            "yaml nit unknown class",
        }
        return (
            titles == expected
            and result["blocking_count"] == 2
            and result["nit_count"] == 2
        )


# ---------------------------------------------------------------------------
# Deduplication: a title present in both mechanisms appears once in findings.
# ---------------------------------------------------------------------------


def test_cross_mechanism_dedup_by_title() -> bool:
    raw = (
        _verdict_yaml()
        + _heading("BLOCKING", "design", "shared title")
        + _yaml_block(
            [{"severity": "BLOCKING", "class": "design", "title": "shared title"}]
        )
    )
    findings = extract_findings(raw)
    matching = [f for f in findings if f.title == "shared title"]
    return len(matching) == 1


# ---------------------------------------------------------------------------
# Two same-mechanism headings sharing one title: both survive and contribute to the
# scalars; when out-of-ceiling, the written file carries two rewritten headings and no
# residual BLOCKING heading.
# ---------------------------------------------------------------------------


def test_duplicate_title_same_mechanism_headings_both_survive_and_rewrite() -> bool:
    with _test_helpers.safe_temp_dir() as tmpdir:
        blocking_classes = resolve_blocking_classes({}, "discussion", None)
        raw = (
            _verdict_yaml()
            + _heading("BLOCKING", "scope", "missing test coverage")
            + _heading("BLOCKING", "scope", "missing test coverage")
        )
        result, written_text = _finalize(
            tmpdir, "discussion", raw, blocking_classes=blocking_classes
        )
        matching = [f for f in result["findings"] if f["title"] == "missing test coverage"]
        return (
            len(matching) == 2
            and result["blocking_count"] == 0
            and result["nit_count"] == 2
            and written_text.count("### [NIT:scope] missing test coverage") == 2
            and "### [BLOCKING:scope]" not in written_text
        )


# ---------------------------------------------------------------------------
# The same duplicate-title case expressed entirely within the YAML mechanism: two
# fenced findings: entries sharing one title and no heading for either.
# ---------------------------------------------------------------------------


def test_duplicate_title_same_mechanism_yaml_both_survive_and_rewrite() -> bool:
    with _test_helpers.safe_temp_dir() as tmpdir:
        blocking_classes = resolve_blocking_classes({}, "discussion", None)
        raw = _verdict_yaml() + _yaml_block(
            [
                {"severity": "BLOCKING", "class": "scope", "title": "duplicate yaml title"},
                {"severity": "BLOCKING", "class": "scope", "title": "duplicate yaml title"},
            ]
        )
        result, written_text = _finalize(
            tmpdir, "discussion", raw, blocking_classes=blocking_classes
        )
        matching = [f for f in result["findings"] if f["title"] == "duplicate yaml title"]
        return (
            len(matching) == 2
            and result["blocking_count"] == 0
            and result["nit_count"] == 2
            and written_text.count("severity: NIT") == 2
            and written_text.count("demoted_from: BLOCKING") == 2
        )


# ---------------------------------------------------------------------------
# resolve_blocking_classes: per-stage defaults when blocking_classes is absent from cfg.
# ---------------------------------------------------------------------------


def test_resolve_blocking_classes_defaults() -> bool:
    checks = [
        (resolve_blocking_classes({}, "discussion", None), "discussion-review"),
        (resolve_blocking_classes({}, "discussion", "holistic"), "discussion-review"),
        (resolve_blocking_classes({}, "plan", "holistic"), "plan-review"),
        (resolve_blocking_classes({}, "plan", "01-setup"), "plan-review"),
        (resolve_blocking_classes({}, "code", "holistic"), "code-review"),
        (resolve_blocking_classes({}, "code", "01-setup"), "code-review"),
    ]
    return all(
        actual == DEFAULT_BLOCKING_CLASSES[role] for actual, role in checks
    )


def test_resolve_blocking_classes_reads_configured_value() -> bool:
    cfg = {
        "roles": {
            "plan-review": {"holistic": {"blocking_classes": ["design"]}},
        }
    }
    return resolve_blocking_classes(cfg, "plan", "holistic") == frozenset({"design"})


def test_resolve_blocking_classes_never_raises_on_missing_levels() -> bool:
    try:
        result = resolve_blocking_classes({"roles": None}, "code", None)
    except Exception:
        return False
    return result == DEFAULT_BLOCKING_CLASSES["code-review"]


def test_resolve_blocking_classes_unrecognized_review_type_falls_back_to_all() -> bool:
    return resolve_blocking_classes({}, "unknown-type", None) == frozenset(
        RECOGNIZED_CLASSES
    )


# ---------------------------------------------------------------------------
# parse_verdict: historical GAPS_FOUND normalises to REQUEST_CHANGES.
# ---------------------------------------------------------------------------


def test_parse_verdict_normalises_gaps_found() -> bool:
    fenced = parse_verdict("```yaml\nverdict: GAPS_FOUND\n```\n")
    unfenced = parse_verdict("verdict: GAPS_FOUND\n")
    return fenced == "REQUEST_CHANGES" and unfenced == "REQUEST_CHANGES"


TESTS = [
    ("ceiling table -- discussion (only design survives BLOCKING)", test_ceiling_table_discussion),
    ("ceiling table -- plan (design+scope survive BLOCKING)", test_ceiling_table_plan),
    ("ceiling table -- code (all four classes survive BLOCKING)", test_ceiling_table_code),
    ("ceiling never promotes a stated NIT", test_ceiling_never_promotes),
    ("demotion rewrite -- heading mechanism, on disk", test_demotion_rewrite_heading_on_disk),
    ("demotion rewrite -- yaml-only mechanism, on disk", test_demotion_rewrite_yaml_only_on_disk),
    (
        "demotion rewrite -- both mechanisms, one finding, both rewritten",
        test_demotion_rewrite_both_mechanisms_dedup_to_one_finding,
    ),
    (
        "re-read round trip reports demoted from marker alone",
        test_reread_round_trip_reports_demoted_from_marker,
    ),
    (
        "verdict derivation -- discussion scope-only BLOCKING approves",
        test_verdict_derivation_discussion_scope_only_approves,
    ),
    (
        "unknown class preserves stated severity and is ceiling-exempt",
        test_unknown_class_preserves_severity_and_exempts_ceiling,
    ),
    ("no double-count for NIT with unknown class", test_no_double_count_nit_with_unknown_class),
    ("mixed-format document hides no finding", test_mixed_format_document_hides_no_finding),
    ("cross-mechanism dedup by title", test_cross_mechanism_dedup_by_title),
    (
        "duplicate title, same mechanism (headings), both survive and rewrite",
        test_duplicate_title_same_mechanism_headings_both_survive_and_rewrite,
    ),
    (
        "duplicate title, same mechanism (yaml), both survive and rewrite",
        test_duplicate_title_same_mechanism_yaml_both_survive_and_rewrite,
    ),
    ("resolve_blocking_classes per-stage defaults", test_resolve_blocking_classes_defaults),
    (
        "resolve_blocking_classes reads a configured value",
        test_resolve_blocking_classes_reads_configured_value,
    ),
    (
        "resolve_blocking_classes never raises on missing/None levels",
        test_resolve_blocking_classes_never_raises_on_missing_levels,
    ),
    (
        "resolve_blocking_classes unrecognized review_type falls back to all classes",
        test_resolve_blocking_classes_unrecognized_review_type_falls_back_to_all,
    ),
    ("parse_verdict normalises GAPS_FOUND to REQUEST_CHANGES", test_parse_verdict_normalises_gaps_found),
]


def main() -> int:
    errors = 0
    for label, test_fn in TESTS:
        try:
            if test_fn():
                print(f"PASS: {label}")
            else:
                print(f"FAIL: {label}", file=sys.stderr)
                errors += 1
        except Exception as exc:
            print(f"FAIL: {label} ({exc})", file=sys.stderr)
            errors += 1

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All review-class-taxonomy unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
