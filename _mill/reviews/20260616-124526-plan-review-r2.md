MILL_REVIEW_BEGIN
# Review: Fix unit test suite failures, spurious review warning, and implementer verify-gate gaps — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-16
```

## Findings

### [BLOCKING] Batch 3 verify diverges between overview and batch file
**Location:** 00-overview.md Batch Index (batch 3) vs 03-implementer-verify-gate.md frontmatter
**Issue:** The overview entry's `verify:` runs `--only test-implementer-common.py test-millpy-implement.py` (two files), but the batch file's `verify:` adds `test-millpy-fix.py` (three files); the overview calls the Index the authoritative, mirrored copy, so the two must match. Card 6 edits `millpy-fix.py`, so its regression test (`test-millpy-fix.py`) must be in whichever verify mill-go runs.
**Fix:** Make both `verify:` strings identical — add `test-millpy-fix.py` to the overview Batch Index entry for batch 3.

### [NIT] Card 7 does not assert commit_sha enrichment on gated success
**Location:** 03-implementer-verify-gate.md card 7 (and card 5)
**Issue:** Card 5 requires the verify-gate stuck dict to carry "the same `commit_sha` enrichment the success path uses where applicable," but card 7's cases only assert `status`/`stuck_type`/`reason`, leaving that enrichment path uncovered.
**Fix:** Add an assertion in case (a) or (d) that the emitted stuck dict includes `commit_sha` (post-drift HEAD), matching card 5's enrichment requirement.

### [NIT] Card 6 verify resolution untested in the CLI test files
**Location:** 03-implementer-verify-gate.md card 6 / Batch Tests
**Issue:** Card 6 threads `_read_batch_frontmatter(...).get("verify")` through both CLIs, but card 7 only tests `_implementer_common`; `test-millpy-implement.py`/`test-millpy-fix.py` are described as re-run for regression, with no new case asserting the resolved `verify_cmd` is actually passed to `finalize_from_output`/`_forward_output`.
**Fix:** Optionally add a case asserting the resolved verify command reaches the finalize call (e.g. holistic fix passes `None`), or explicitly accept the gap as covered by `_implementer_common` unit tests.

## Verdict

REQUEST_CHANGES
Batch 3 overview/batch verify mismatch must be reconciled; remaining items are nits.
MILL_REVIEW_END
