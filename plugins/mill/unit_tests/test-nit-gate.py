"""Unit tests for _nit_gate.py.

Tests the compute_unfixed_nits function's gate logic across various scenarios:
- Scopes with nits but markers present (should not be flagged)
- Scopes with nits but no markers (should be flagged)
- Scopes with zero nits (should not be flagged)
- Per-batch and holistic scopes handled together
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

    For per-batch scopes:
        Format: YYYYMMDD-HHMMSS-<type>-review-<scope>-r<round>.md

    For holistic scope:
        Format: YYYYMMDD-HHMMSS-<type>-review-r<round>.md
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

    def test_gate_returns_empty_when_all_nitted_scopes_have_markers(self):
        """
        Test (a): gate returns empty list when every nitted scope has a nits-fixed marker.
        """
        # Create a per-batch code review with nits
        _create_review_file(
            self.reviews_dir,
            "20260601-100000",
            "code",
            "batch1",
            1,
            has_nits=True,
        )

        # Timeline: approved-batch1 and nits-fixed-batch1
        timeline = [
            "implementing  2026-06-01T10:00:00Z",
            "approved-batch1  2026-06-01T10:30:00Z",
            "nits-fixed-batch1  2026-06-01T10:35:00Z",
        ]
        status_path = self._make_status_file(timeline)

        result = _nit_gate.compute_unfixed_nits(self.tmp_path, self.reviews_dir, status_path)
        self.assertEqual(result, [])

    def test_gate_flags_scope_with_nits_and_no_marker(self):
        """
        Test (b): gate flags a scope whose final review has NIT headings and no marker.
        """
        # Create a per-batch code review with nits
        _create_review_file(
            self.reviews_dir,
            "20260601-100000",
            "code",
            "batch1",
            1,
            has_nits=True,
        )

        # Timeline: approved-batch1 but NO nits-fixed-batch1
        timeline = [
            "implementing  2026-06-01T10:00:00Z",
            "approved-batch1  2026-06-01T10:30:00Z",
        ]
        status_path = self._make_status_file(timeline)

        result = _nit_gate.compute_unfixed_nits(self.tmp_path, self.reviews_dir, status_path)
        self.assertEqual(result, ["batch1"])

    def test_gate_ignores_scope_with_zero_nits_in_final_review(self):
        """
        Test (c): gate ignores a scope whose final (APPROVE) review has zero nits,
        even if an earlier round had nits.
        """
        # Create two code reviews for batch2: round 1 with nits, round 2 without nits
        _create_review_file(
            self.reviews_dir,
            "20260601-100000",
            "code",
            "batch2",
            1,
            has_nits=True,
        )
        _create_review_file(
            self.reviews_dir,
            "20260601-110000",
            "code",
            "batch2",
            2,
            has_nits=False,
        )

        # Timeline: approved-batch2 referencing the round 2 review
        # (the gate will find the latest review, which is round 2, which has zero nits)
        timeline = [
            "implementing  2026-06-01T10:00:00Z",
            "approved-batch2  2026-06-01T11:30:00Z",
        ]
        status_path = self._make_status_file(timeline)

        result = _nit_gate.compute_unfixed_nits(self.tmp_path, self.reviews_dir, status_path)
        self.assertEqual(result, [])

    def test_gate_handles_per_batch_and_holistic_together(self):
        """
        Test (d): both per-batch and holistic scopes handled in one timeline.
        """
        # Create reviews: batch1 with nits (no marker), holistic with nits (has marker)
        _create_review_file(
            self.reviews_dir,
            "20260601-100000",
            "code",
            "batch1",
            1,
            has_nits=True,
        )
        _create_review_file(
            self.reviews_dir,
            "20260601-105000",
            "code",
            "holistic",
            1,
            has_nits=True,
        )

        # Timeline: both approved, but only holistic has a marker
        timeline = [
            "implementing  2026-06-01T10:00:00Z",
            "approved-batch1  2026-06-01T10:30:00Z",
            "holistic-approved  2026-06-01T11:00:00Z",
            "nits-fixed-holistic  2026-06-01T11:05:00Z",
        ]
        status_path = self._make_status_file(timeline)

        result = _nit_gate.compute_unfixed_nits(self.tmp_path, self.reviews_dir, status_path)
        # Only batch1 should be flagged (holistic has its marker)
        self.assertEqual(result, ["batch1"])

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
            "approved-batch1  2026-06-01T10:30:00Z",
        ]
        status_path = self._make_status_file(timeline)
        nonexistent_reviews = self.tmp_path / "nonexistent_reviews"

        result = _nit_gate.compute_unfixed_nits(self.tmp_path, nonexistent_reviews, status_path)
        self.assertEqual(result, [])

    def test_marker_precedes_approve_row(self):
        """
        Verify that nits-fixed marker can precede the approved- row in the timeline.
        The gate should not impose a positional constraint.
        """
        # Create review with nits
        _create_review_file(
            self.reviews_dir,
            "20260601-100000",
            "code",
            "batch1",
            1,
            has_nits=True,
        )

        # Timeline: marker BEFORE approved row (normal order when NIT-fix dispatch precedes approve write)
        timeline = [
            "implementing  2026-06-01T10:00:00Z",
            "nits-fixed-batch1  2026-06-01T10:25:00Z",
            "approved-batch1  2026-06-01T10:30:00Z",
        ]
        status_path = self._make_status_file(timeline)

        result = _nit_gate.compute_unfixed_nits(self.tmp_path, self.reviews_dir, status_path)
        # Should return empty (marker exists, regardless of position)
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
