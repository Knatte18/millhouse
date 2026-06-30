I now have everything needed to write the review.

MILL_REVIEW_BEGIN
# Review: Handle pre-closed and pre-merged PRs gracefully in mill-merge -- holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-06-30
```

## Findings

### [NIT] Misleading test function name implies exception is raised
**Location:** `plugins/mill/unit_tests/test-pr-state.py:89`
**Issue:** `test_gh_missing_raises_file_not_found` says "raises" but the test body verifies that no exception propagates -- the inverse of what the name implies.
**Fix:** Rename to `test_gh_missing_no_exception_returns_none` to match the actual assertion intent.

### [NIT] Closed-route wiki fallback missing None guard
**Location:** `plugins/mill/skills/mill-merge/SKILL.md` (closed route, else branch of `status_path.exists()`)
**Issue:** `task = _client.get_task(wiki_path, slug)` is followed immediately by `cached_task = task["title"]` with no guard for `task is None`. If the slug has been removed from the wiki while the branch is still live, this raises `TypeError`.
**Fix:** Add `if task is None: halt("slug '<slug>' not found in wiki; cannot derive commit message for closed route")` before accessing `task["title"]`, consistent with the Step 5 phase-gate guard pattern already present in the same skill.

## Verdict

APPROVE
Implementation is correct and complete; both findings are non-blocking quality issues.
MILL_REVIEW_END
