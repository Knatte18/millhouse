"""Unit tests for _nit_gate.py.

Tests the compute_unfixed_nits function's gate logic across various scenarios:
- Holistic scope with nits but marker present (should not be flagged)
- Holistic scope with nits but no marker (should be flagged)
- Holistic scope with zero nits in the final review (should not be flagged)
- approved-<batch> rows and leftover per-batch review files never create a gate scope
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _safe_rmtree  # noqa: E402
import _nit_gate  # noqa: E402
import _review_common  # noqa: E402


def _create_review_file(
    reviews_dir: Path,
    timestamp: str,
    review_type: str,
    scope: str,
    round_n: int,
    has_nits: bool,
) -> Path:
    """
    Create a synthetic review file in reviews_dir.

    For holistic scope:
        Format: YYYYMMDD-HHMMSS-<type>-review-r<round>.md

    For any other scope (a leftover per-batch file):
        Format: YYYYMMDD-HHMMSS-<type>-review-<scope>-r<round>.md
    """
    if scope == "holistic":
        filename = f"{timestamp}-{review_type}-review-r{round_n}.md"
    else:
        filename = f"{timestamp}-{review_type}-review-{scope}-r{round_n}.md"

    content = "# Review\n"
    if has_nits:
        content += "\n### [NIT] Fix formatting issue\n"
        content += "The code should be formatted correctly.\n"
        content += "\n### [NIT] Add docstring\n"
        content += "This function needs a docstring.\n"
    else:
        content += "\n### [BLOCKING] Critical error\n"
        content += "This is a blocking issue.\n"

    file_path = reviews_dir / filename
    file_path.write_text(content, encoding="utf-8")
    return file_path


class TestNitGate(unittest.TestCase):

    def setUp(self):
        """Create a temporary directory for fixtures."""
        self.tmp_path = Path(tempfile.mkdtemp())
        self.addCleanup(_safe_rmtree.safe_rmtree, self.tmp_path, allowed_root=self.tmp_path, ignore_errors=True)
        self.reviews_dir = self.tmp_path / "reviews"
        self.reviews_dir.mkdir(parents=True, exist_ok=True)

    def _make_status_file(self, timeline_lines: list[str]) -> Path:
        """Create a minimal status.md with a given timeline."""
        status_path = self.tmp_path / "status.md"
        content = (
            "```yaml\n"
            "phase: implementing\n"
            "slug: test-slug\n"
            "task: Test Task\n"
            "branch: test-branch\n"
            "```\n\n"
            "## Timeline\n\n"
            "```text\n"
        )
        for line in timeline_lines:
            content += f"{line}\n"
        content += "```\n"
        status_path.write_text(content, encoding="utf-8")
        return status_path

    def test_gate_returns_empty_when_nitted_scope_has_marker(self):
        """
        Test (a): gate returns empty list when the holistic scope has a nits-fixed marker.
        """
        _create_review_file(self.reviews_dir, "20260601-100000", "code", "holistic", 1, has_nits=True)

        timeline = [
            "implementing  2026-06-01T10:00:00Z",
            "holistic-approved  2026-06-01T10:30:00Z",
            "nits-fixed-holistic  2026-06-01T10:35:00Z",
        ]
        status_path = self._make_status_file(timeline)

        result = _nit_gate.compute_unfixed_nits(self.tmp_path, self.reviews_dir, status_path)
        self.assertEqual(result, [])

    def test_gate_flags_scope_with_nits_and_no_marker(self):
        """
        Test (b): gate flags the holistic scope whose final review has NIT headings and no marker.
        """
        _create_review_file(self.reviews_dir, "20260601-100000", "code", "holistic", 1, has_nits=True)

        timeline = [
            "implementing  2026-06-01T10:00:00Z",
            "holistic-approved  2026-06-01T10:30:00Z",
        ]
        status_path = self._make_status_file(timeline)

        result = _nit_gate.compute_unfixed_nits(self.tmp_path, self.reviews_dir, status_path)
        self.assertEqual(result, ["holistic"])

    def test_gate_ignores_scope_with_zero_nits_in_final_review(self):
        """
        Test (c): gate ignores a scope whose final (APPROVE) review has zero nits, even if an
        earlier round had nits.
        """
        _create_review_file(self.reviews_dir, "20260601-100000", "code", "holistic", 1, has_nits=True)
        _create_review_file(self.reviews_dir, "20260601-110000", "code", "holistic", 2, has_nits=False)

        timeline = [
            "implementing  2026-06-01T10:00:00Z",
            "holistic-approved  2026-06-01T11:30:00Z",
        ]
        status_path = self._make_status_file(timeline)

        result = _nit_gate.compute_unfixed_nits(self.tmp_path, self.reviews_dir, status_path)
        self.assertEqual(result, [])

    def test_gate_ignores_approved_batch_rows_and_leftover_batch_reviews(self):
        """
        An approved-<batch> row and a leftover per-batch code-review file create no gate scope;
        only the holistic scope is returned.
        """
        _create_review_file(self.reviews_dir, "20260601-100000", "code", "01-alpha", 1, has_nits=True)
        _create_review_file(self.reviews_dir, "20260601-105000", "code", "holistic", 1, has_nits=True)

        timeline = [
            "implementing  2026-06-01T10:00:00Z",
            "approved-01-alpha  2026-06-01T10:30:00Z",
            "holistic-approved  2026-06-01T11:00:00Z",
        ]
        status_path = self._make_status_file(timeline)

        result = _nit_gate.compute_unfixed_nits(self.tmp_path, self.reviews_dir, status_path)
        self.assertEqual(result, ["holistic"])

    def test_gate_returns_empty_when_no_approved_scopes(self):
        """Gate returns empty when no approved scopes exist in timeline."""
        timeline = [
            "implementing  2026-06-01T10:00:00Z",
        ]
        status_path = self._make_status_file(timeline)

        result = _nit_gate.compute_unfixed_nits(self.tmp_path, self.reviews_dir, status_path)
        self.assertEqual(result, [])

    def test_gate_returns_empty_when_status_file_missing(self):
        """Gate returns empty (gracefully) when status file is missing."""
        nonexistent_status = self.tmp_path / "nonexistent.md"
        result = _nit_gate.compute_unfixed_nits(self.tmp_path, self.reviews_dir, nonexistent_status)
        self.assertEqual(result, [])

    def test_gate_returns_empty_when_reviews_dir_missing(self):
        """Gate returns empty when reviews directory does not exist."""
        timeline = [
            "implementing  2026-06-01T10:00:00Z",
            "holistic-approved  2026-06-01T10:30:00Z",
        ]
        status_path = self._make_status_file(timeline)
        nonexistent_reviews = self.tmp_path / "nonexistent_reviews"

        result = _nit_gate.compute_unfixed_nits(self.tmp_path, nonexistent_reviews, status_path)
        self.assertEqual(result, [])

    def test_gate_flags_scope_with_only_classed_nit_headings(self):
        """
        Card 19, check 1: a final code-review file containing only `### [NIT:consistency]` headings
        is flagged, proving batch 1's widened `parse_blocking_count` pattern reaches this call site
        with no change to `_nit_gate.py` itself.
        """
        filename = "20260601-100000-code-review-r1.md"
        content = (
            "# Review\n\n"
            "### [NIT:consistency] contradicts an earlier statement\n"
            "The artefact contradicts a prior claim.\n"
        )
        (self.reviews_dir / filename).write_text(content, encoding="utf-8")

        timeline = [
            "implementing  2026-06-01T10:00:00Z",
            "holistic-approved  2026-06-01T10:30:00Z",
        ]
        status_path = self._make_status_file(timeline)

        result = _nit_gate.compute_unfixed_nits(self.tmp_path, self.reviews_dir, status_path)
        self.assertEqual(result, ["holistic"])

    def test_gate_counts_demoted_nit_heading_exactly_once(self):
        """
        Card 19, check 2: a `### [NIT:scope]` heading immediately followed by a
        `**Demoted-from:** BLOCKING` field line is counted exactly once -- the inserted field line
        must not inflate the nit count.
        """
        filename = "20260601-100000-code-review-r1.md"
        content = (
            "# Review\n\n"
            "### [NIT:scope] work inventory incomplete\n"
            "**Demoted-from:** BLOCKING\n"
            "The enumeration missed one file.\n"
        )
        (self.reviews_dir / filename).write_text(content, encoding="utf-8")

        timeline = [
            "implementing  2026-06-01T10:00:00Z",
            "holistic-approved  2026-06-01T10:30:00Z",
        ]
        status_path = self._make_status_file(timeline)

        result = _nit_gate.compute_unfixed_nits(self.tmp_path, self.reviews_dir, status_path)
        # Flagged (unfixed) proves the heading was seen; the real assertion is the exactly-once
        # count, checked directly against parse_blocking_count below.
        self.assertEqual(result, ["holistic"])
        nit_count = _review_common.parse_blocking_count(content, severity="NIT")
        self.assertEqual(nit_count, 1)

    def test_marker_precedes_approve_row(self):
        """
        Verify that nits-fixed marker can precede the holistic-approved row in the timeline.
        The gate should not impose a positional constraint.
        """
        _create_review_file(self.reviews_dir, "20260601-100000", "code", "holistic", 1, has_nits=True)

        # Marker BEFORE approved row (normal order when NIT-fix dispatch precedes approve write)
        timeline = [
            "implementing  2026-06-01T10:00:00Z",
            "nits-fixed-holistic  2026-06-01T10:25:00Z",
            "holistic-approved  2026-06-01T10:30:00Z",
        ]
        status_path = self._make_status_file(timeline)

        result = _nit_gate.compute_unfixed_nits(self.tmp_path, self.reviews_dir, status_path)
        # Should return empty (marker exists, regardless of position)
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
