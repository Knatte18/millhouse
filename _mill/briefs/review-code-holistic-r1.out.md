MILL_REVIEW_BEGIN
# Review: _plan_validate.py: Batch Index/batch-file verify: drift, flattened-fence, and large-file-citation gaps — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-09-04
```

## Findings

### [NIT:consistency] Test docstrings say "## Batches" but the actual heading is "## Batch Index"
**Location:** `plugins/mill/unit_tests/test-plan-validate.py:6189-6190`
**Issue:** `test_verify_batch_mismatch_clean_overview_batches_unparseable`'s docstring calls the section "## Batches", but `_make_overview` (and every real plan) writes the heading as "## Batch Index" — the fenced-yaml body starting with `batches:` is what `extract_batch_index` actually keys on, so the test is functionally correct, only the comment's section name is off (inherited from the same wording in `02-validator-tests.md`).
**Fix:** Reword the docstring to "the overview's Batch Index fenced yaml is unparseable" for clarity; no functional change needed.

## Verdict

APPROVE
All three behaviours (verify-batch-mismatch, symmetric indent detection, inline-signature markers) are correctly implemented, tested, and documented end-to-end.
MILL_REVIEW_END
