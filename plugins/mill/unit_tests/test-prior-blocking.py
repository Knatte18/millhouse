"""Unit tests for _prior_blocking.py.

Tests the build_digest function's extraction logic:
- Single holistic-scope file with a plain and a classed BLOCKING heading.
- Demoted findings (rendered as NIT with a Demoted-from marker) are excluded.
- Cumulative aggregation across holistic rounds.
- A leftover per-batch-named code-review file is ignored.
- Empty / non-existent reviews_dir returns "".
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _safe_rmtree  # noqa: E402
import _prior_blocking  # noqa: E402


def _write_review(reviews_dir: Path, filename: str, content: str) -> Path:
    """Write a synthetic review file into reviews_dir and return its path."""
    file_path = reviews_dir / filename
    file_path.write_text(content, encoding="utf-8")
    return file_path


class TestPriorBlocking(unittest.TestCase):

    def setUp(self):
        """Create a temporary directory for fixtures."""
        self.tmp_path = Path(tempfile.mkdtemp())
        self.addCleanup(_safe_rmtree.safe_rmtree, self.tmp_path, allowed_root=self.tmp_path, ignore_errors=True)
        self.reviews_dir = self.tmp_path / "reviews"
        self.reviews_dir.mkdir(parents=True, exist_ok=True)

    def test_holistic_single_file_plain_heading(self):
        """Case 1: a single holistic-scope file with one plain BLOCKING heading is included."""
        _write_review(
            self.reviews_dir,
            "20260601-100000-code-review-r1.md",
            "# Review\n\n### [BLOCKING] Missing null check\nThe function does not guard against None.\n",
        )

        digest = _prior_blocking.build_digest(self.reviews_dir)
        self.assertIn("Missing null check", digest)

    def test_holistic_classed_heading_included(self):
        """Case 2: a classed heading, ### [BLOCKING:design], is matched identically to a plain one."""
        _write_review(
            self.reviews_dir,
            "20260601-100000-code-review-r1.md",
            "# Review\n\n### [BLOCKING:design] Wrong abstraction layer\nThis violates layering.\n",
        )

        digest = _prior_blocking.build_digest(self.reviews_dir)
        self.assertIn("Wrong abstraction layer", digest)

    def test_demoted_finding_excluded(self):
        """Case 3: a demoted finding (NIT heading with Demoted-from marker) is excluded."""
        _write_review(
            self.reviews_dir,
            "20260601-100000-code-review-r1.md",
            (
                "# Review\n\n"
                "### [NIT:design] Formerly blocking issue\n"
                "**Demoted-from:** BLOCKING\n"
                "This was downgraded during review.\n"
            ),
        )

        digest = _prior_blocking.build_digest(self.reviews_dir)
        self.assertNotIn("Formerly blocking issue", digest)

    def test_cumulative_across_holistic_rounds(self):
        """Case 4: two holistic rounds both contribute their BLOCKING findings."""
        _write_review(
            self.reviews_dir,
            "20260601-100000-code-review-r1.md",
            "# Review\n\n### [BLOCKING] Round one issue\nDetails for round one.\n",
        )
        _write_review(
            self.reviews_dir,
            "20260601-110000-code-review-r2.md",
            "# Review\n\n### [BLOCKING] Round two issue\nDetails for round two.\n",
        )

        digest = _prior_blocking.build_digest(self.reviews_dir)
        self.assertIn("Round one issue", digest)
        self.assertIn("Round two issue", digest)

    def test_per_batch_named_file_ignored(self):
        """Case 5: a leftover per-batch-named code-review file's BLOCKING headings are excluded."""
        _write_review(
            self.reviews_dir,
            "20260601-100000-code-review-foo-r1.md",
            "# Review\n\n### [BLOCKING] Foo batch issue\nDetails for foo.\n",
        )
        _write_review(
            self.reviews_dir,
            "20260601-110000-code-review-retry-fix-r1.md",
            "# Review\n\n### [BLOCKING] Retry fix batch issue\nDetails for retry-fix.\n",
        )
        _write_review(
            self.reviews_dir,
            "20260601-120000-code-review-r1.md",
            "# Review\n\n### [BLOCKING] Holistic round issue\nDetails for holistic.\n",
        )

        digest = _prior_blocking.build_digest(self.reviews_dir)
        self.assertEqual(digest, "- Holistic round issue: Details for holistic.")

    def test_empty_reviews_dir_returns_empty_string(self):
        """Case 6: an empty (or non-matching-only) reviews_dir returns ""."""
        _write_review(self.reviews_dir, "not-a-review.txt", "irrelevant content\n")

        digest = _prior_blocking.build_digest(self.reviews_dir)
        self.assertEqual(digest, "")

    def test_nonexistent_reviews_dir_returns_empty_string(self):
        """Case 7: reviews_dir pointing at a non-existent path returns "" without raising."""
        nonexistent = self.tmp_path / "does-not-exist"

        digest = _prior_blocking.build_digest(nonexistent)
        self.assertEqual(digest, "")


if __name__ == "__main__":
    unittest.main()
