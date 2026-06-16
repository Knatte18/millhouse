MILL_REVIEW_BEGIN
# Review: Fix unit test suite failures, spurious review warning, and implementer verify-gate gaps — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-16
```

## Findings

### [BLOCKING] Batch 4 verify depends on batch 2's arrow fix
**Location:** 00-overview.md Batch Index / batch 4 (implementer-guardrail)
**Issue:** Batch 4's `verify: ... --only test-guards.py` runs `_check_no_unicode_arrow`, which scans ALL `test-*.py` including `test-claude-sub.py` whose U+2192 arrows (lines 775/787, still present) are only removed by batch 2; with both batches at `depends-on: []` batch 4 can be scheduled/verified before batch 2 lands and its verify gate will fail through no fault of its own edits.
**Fix:** Add `depends-on: [ascii-arrow-fix]` to batch 4 in both the Batch Index and `04-implementer-guardrail.md` frontmatter.

### [NIT] Card 7 fixture batch file has no frontmatter verify
**Location:** 03-implementer-verify-gate.md card 7
**Issue:** The threading assertion reads verify via `_read_batch_frontmatter(batch_file)` (the per-batch `.md`), but `test-millpy-implement.py`'s fixture writes `01-test-batch.md` as a bare `# Batch:` line with no fenced-yaml `verify:`; the card must have the test add that frontmatter or the resolved `verify_cmd` will be `None`.
**Fix:** Note in card 7 that the test must write a `verify:` into the batch file's frontmatter (not the overview, whose entry is `verify: null`).

## Verdict

REQUEST_CHANGES
Batch 4's guard verify will fail until batch 2 lands; add the cross-batch dependency.
MILL_REVIEW_END
