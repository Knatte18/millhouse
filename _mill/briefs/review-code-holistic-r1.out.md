MILL_REVIEW_BEGIN
# Review: Remove batch review (plan-review.batch / code-review.batch) — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-09-24
```

## Findings

No blocking findings.
Scope of verification: repo-wide grep for the deleted artefacts (`review-code-batch`, `review-plan-batch`, `fixer-batch-brief`, `_moves_check`) and removed config keys/flags found no live references in `plugins/`.
Remaining "per-batch" mentions are the legitimate implementer/verify concept, or deliberate stale-key handling (`_config.py` removal hints, tolerated leftover files in `_review_common.py` and `millpy-review-summary.py`) with matching tests.
I did not read every source file line by line; the approval rests on this grep-level cross-check.

## Verdict

APPROVE
Batch-review removal is consistent across code, config, templates, tests and skill text; no dangling references found.
MILL_REVIEW_END
