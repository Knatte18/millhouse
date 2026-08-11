"""Unit tests for _prior_blocking.py.

Tests the build_digest function's extraction and scoping logic:
- Single holistic-scope file with a plain and a classed BLOCKING heading.
- Demoted findings (rendered as NIT with a Demoted-from marker) are excluded.
- Cumulative aggregation across rounds within one batch.
- Cross-scope and cross-batch aggregation for holistic scope.
- Batch scope excludes other batches' findings.
- Empty / non-existent reviews_dir returns "".
- A batch literally named "retry-fix" is never misclassified as holistic.
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

        digest = _prior_blocking.build_digest(self.reviews_dir, scope="holistic")
        self.assertIn("Missing null check", digest)

    def test_holistic_classed_heading_included(self):
        """Case 2: a classed heading, ### [BLOCKING:design], is matched identically to a plain one."""
        _write_review(
            self.reviews_dir,
            "20260601-100000-code-review-r1.md",
            "# Review\n\n### [BLOCKING:design] Wrong abstraction layer\nThis violates layering.\n",
        )

        digest = _prior_blocking.build_digest(self.reviews_dir, scope="holistic")
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

        digest = _prior_blocking.build_digest(self.reviews_dir, scope="holistic")
        self.assertNotIn("Formerly blocking issue", digest)

    def test_batch_scope_cumulative_across_rounds(self):
        """Case 4: two rounds of the same batch both contribute their BLOCKING findings."""
        _write_review(
            self.reviews_dir,
            "20260601-100000-code-review-foo-r1.md",
            "# Review\n\n### [BLOCKING] Round one issue\nDetails for round one.\n",
        )
        _write_review(
            self.reviews_dir,
            "20260601-110000-code-review-foo-r2.md",
            "# Review\n\n### [BLOCKING] Round two issue\nDetails for round two.\n",
        )

        digest = _prior_blocking.build_digest(self.reviews_dir, scope="batch", batch_name="foo")
        self.assertIn("Round one issue", digest)
        self.assertIn("Round two issue", digest)

    def test_holistic_cross_scope_and_cross_batch_aggregation(self):
        """Case 5: holistic scope aggregates findings across two batches plus a holistic file."""
        _write_review(
            self.reviews_dir,
            "20260601-100000-code-review-foo-r1.md",
            "# Review\n\n### [BLOCKING] Foo batch issue\nDetails for foo.\n",
        )
        _write_review(
            self.reviews_dir,
            "20260601-110000-code-review-bar-r1.md",
            "# Review\n\n### [BLOCKING] Bar batch issue\nDetails for bar.\n",
        )
        _write_review(
            self.reviews_dir,
            "20260601-120000-code-review-r1.md",
            "# Review\n\n### [BLOCKING] Holistic round issue\nDetails for holistic.\n",
        )

        digest = _prior_blocking.build_digest(self.reviews_dir, scope="holistic")
        self.assertIn("Foo batch issue", digest)
        self.assertIn("Bar batch issue", digest)
        self.assertIn("Holistic round issue", digest)

    def test_batch_scope_excludes_other_batches(self):
        """Case 6: batch scope includes its own batch plus the holistic file, but excludes other batches."""
        _write_review(
            self.reviews_dir,
            "20260601-100000-code-review-foo-r1.md",
            "# Review\n\n### [BLOCKING] Foo batch issue\nDetails for foo.\n",
        )
        _write_review(
            self.reviews_dir,
            "20260601-110000-code-review-bar-r1.md",
            "# Review\n\n### [BLOCKING] Bar batch issue\nDetails for bar.\n",
        )
        _write_review(
            self.reviews_dir,
            "20260601-120000-code-review-r1.md",
            "# Review\n\n### [BLOCKING] Holistic round issue\nDetails for holistic.\n",
        )

        digest = _prior_blocking.build_digest(self.reviews_dir, scope="batch", batch_name="foo")
        self.assertIn("Foo batch issue", digest)
        self.assertIn("Holistic round issue", digest)
        self.assertNotIn("Bar batch issue", digest)

    def test_empty_reviews_dir_returns_empty_string(self):
        """Case 7: an empty (or non-matching-only) reviews_dir returns ""."""
        _write_review(self.reviews_dir, "not-a-review.txt", "irrelevant content\n")

        digest = _prior_blocking.build_digest(self.reviews_dir, scope="holistic")
        self.assertEqual(digest, "")

    def test_retry_fix_batch_name_not_misclassified_as_holistic(self):
        """
        Case 8: a batch literally named "retry-fix" is matched correctly by RE_BATCH when its own
        batch scope is requested, and is never misclassified as a holistic-classified file via an
        unanchored match.

        RE_SIMPLE requires "-review-r<digits>.md" to immediately follow the type token, which
        "...-code-review-retry-fix-r1.md" does not satisfy, so this file must classify as
        batch-scope (batch="retry-fix"), not holistic-scope.
        Since holistic-classified files are included under every batch scope (any batch_name),
        while batch-classified files are included only under their own batch_name, the
        distinguishing proof is that this file is ABSENT from a different batch's digest -- if it
        had been misclassified as holistic-classified, it would incorrectly appear there too.
        """
        _write_review(
            self.reviews_dir,
            "20260601-100000-code-review-retry-fix-r1.md",
            "# Review\n\n### [BLOCKING] Retry fix batch issue\nDetails for retry-fix.\n",
        )
        _write_review(
            self.reviews_dir,
            "20260601-110000-code-review-r1.md",
            "# Review\n\n### [BLOCKING] Genuine holistic issue\nDetails for holistic.\n",
        )

        digest = _prior_blocking.build_digest(self.reviews_dir, scope="batch", batch_name="retry-fix")
        self.assertIn("Retry fix batch issue", digest)

        only_retry_fix_dir = self.tmp_path / "reviews-only-retry-fix"
        only_retry_fix_dir.mkdir(parents=True, exist_ok=True)
        _write_review(
            only_retry_fix_dir,
            "20260601-100000-code-review-retry-fix-r1.md",
            "# Review\n\n### [BLOCKING] Retry fix batch issue\nDetails for retry-fix.\n",
        )

        other_batch_digest = _prior_blocking.build_digest(
            only_retry_fix_dir, scope="batch", batch_name="unrelated-batch"
        )
        self.assertEqual(other_batch_digest, "")

    def test_nonexistent_reviews_dir_returns_empty_string(self):
        """Case 9: reviews_dir pointing at a non-existent path returns "" without raising."""
        nonexistent = self.tmp_path / "does-not-exist"

        digest = _prior_blocking.build_digest(nonexistent, scope="holistic")
        self.assertEqual(digest, "")


if __name__ == "__main__":
    unittest.main()
