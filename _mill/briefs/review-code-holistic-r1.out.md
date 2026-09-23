MILL_REVIEW_BEGIN
# Review: compute_baseline: use the task worktree's own pre-edit state, not a parent-branch checkout — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-09-23
```

## Findings

### [NIT:consistency] Dirt-warning coverage differs between the two halves on the error path
**Location:** `plugins/mill/scripts/millpy-implement.py:314-331` (`_run_module_wide_standalone`) vs. `:436-457` (`_run_per_batch_baseline_standalone`)
**Issue:** The per-batch half always takes its after-snapshot and calls `_warn_new_dirt` regardless of any individual batch's failure (failures are caught inline, inside the loop). The module-wide half's `except Exception` branch returns before the after-snapshot/warn call, so a `compute_baseline` exception (e.g. a timeout that left build artifacts behind) silently skips the advisory warning — not fully "reused verbatim by both halves" per Card 11's framing.
**Fix:** Optional — move the after-snapshot/warn call into a `finally` (or duplicate it in the except branch) in `_run_module_wide_standalone` for parity, if the asymmetry was not intentional.

## Verdict

APPROVE
End-to-end plan alignment, cross-batch contracts, and test coverage verified against source; only one non-blocking asymmetry found.
MILL_REVIEW_END
