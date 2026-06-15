MILL_REVIEW_BEGIN
# Review: Fix millpy-review-plan validator gaps and resolve_ref_paths path-doubling — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-06-15
```

## Findings

### [NIT] Import ordering deviation in millpy-review-plan.py
**Location:** `plugins/mill/scripts/millpy-review-plan.py:98`
**Issue:** Card 6 requires alphabetical order preserved in the import; `_load_root_from_overview` (underscore prefix, ASCII 95) sorts before `ReviewError` (ASCII 82 for `R`), but as written `ReviewError` appears first.
**Fix:** Reorder to `_load_root_from_overview, ReviewError, find_active_slug, load_config, resolve_path` or accept that underscore-prefixed names conventionally trail public names in groupings — no correctness impact, cosmetic only.

### [NIT] test-plan-validate.py negative case is a doc comment, not an assertion
**Location:** `plugins/mill/unit_tests/test-plan-validate.py:2262`
**Issue:** Card 5 allows documenting the negative case via comment rather than assertion; the chosen implementation calls `run(..., root="", git_root=None)` (no root set), which avoids the doubling scenario rather than demonstrating it with `root="subproject"` and no `git_root`.
**Fix:** The plan explicitly permitted "assert only the positive case and note the negative in a comment," so this is acceptable as-is; a future revision could add a `root="subproject", git_root=None` assertion to pin the doubling absence.

## Verdict

APPROVE
Implementation is complete, correct, and well-tested across all four batches.
MILL_REVIEW_END
