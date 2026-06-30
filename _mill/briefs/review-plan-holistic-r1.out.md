I've completed a thorough source-grounded review of the overview and all three batches against the 19 manifest files. Here is the review.

MILL_REVIEW_BEGIN
# Review: Fix discussion review round-cap, daemon cold-start, and nits-only no-op in finalize -- holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-30
```

## Findings

### [BLOCKING] Card 4 references `wiki.WikiStartupError` from a file outside Context
**Location:** Batch 2 / Card 4 (test-marker.py, test-millpy-implement.py)
**Issue:** Requirements instruct `side_effect=[wiki.WikiStartupError("cold"), ...]` (test-marker.py) and a bare `self.mock_slug_from_branch.side_effect = WikiStartupError(...)` (test-millpy-implement.py), but the defining file `plugins/mill/scripts/wiki/__init__.py` is not in Card 4's `Context:` (only `_marker.py`, `millpy-implement.py`, `_test_helpers.py` are listed), and neither test file currently imports `wiki`/`WikiStartupError`.
**Fix:** Add `plugins/mill/scripts/wiki/__init__.py` to Card 4's `Context:`, and specify the exact accessor each test should use -- `_marker.wiki.WikiStartupError` (test-marker.py, via `_marker`'s existing `from wiki import _client as wiki` alias) and `millpy_implement.WikiStartupError` (test-millpy-implement.py, available post-Card-3's `from wiki import WikiStartupError`) -- so no fresh import or cold-start exploration is needed.

## Nits

### [NIT] millpy-fix.py keeps the same uncaught-WikiStartupError pattern Card 3 fixes elsewhere
**Location:** Batch 2 (scope) -- `plugins/mill/scripts/millpy-fix.py:159-160`
**Issue:** `millpy-fix.py` wraps `_marker.slug_from_branch(...)` in `except _marker.MarkerError` only, identical to the pre-fix `millpy-implement.py` pattern Card 3 corrects; Card 2's retry helper makes the exhausted case rarer but does not eliminate the raw-traceback risk there.
**Fix:** Confirm with the GH issue (#579) whether this is intentionally out of scope; if not, add the same `except WikiStartupError` clean-catch to `millpy-fix.py`'s `main()`.

## Verdict

REQUEST_CHANGES
Card 4's `wiki.WikiStartupError` references need an explicit Context entry/accessor to avoid cold-start exploration.
MILL_REVIEW_END
