MILL_REVIEW_BEGIN
# Review: _plan_validate.py: Batch Index/batch-file verify: drift, flattened-fence, and large-file-citation gaps — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5 (best-effort; cannot self-verify exact model ID)
reviewed_file: plan/
date: 2026-09-04
```

## Findings

### [NIT:design] "docstring backfill" decision misstates which names are already present
**Location:** 00-overview.md, Shared Decision "docstring backfill is out of scope" (applies to cards 2, 8)
**Issue:** The decision lists `verify-not-isolated`, `verify-full-suite`, `verify-malformed-cwd` (and `plugin-manifest-context-missing` for `run()`'s docstring) as "already missing" from `run()`'s own docstring and the unit-test file's "Check coverage" docstring. Reading both sources: `run()`'s docstring (`_plan_validate.py` ~2917-2922) already names `plugin-manifest-context-missing`, `verify-not-isolated`, `verify-full-suite`, `verify-malformed-cwd`; the test file's "Check coverage" block (lines 21-26) already names `context-completeness` and the same three `verify-*` checks. Only `depends-on-batch-mismatch`, `requirements-quote-indent-drift`, and (for the test file) `plugin-manifest-context-missing` are genuinely absent.
**Fix:** Correct the decision's inventory in 00-overview.md for accuracy. No card behavior needs to change — Cards 2 and 8 both already instruct "add only the one new name, leave the rest untouched," which is unaffected by the inaccurate list.

## Verdict

APPROVE
Plan is internally consistent, source-grounded, and well-specified; only a cosmetic decision-text inaccuracy found.
MILL_REVIEW_END
