MILL_REVIEW_BEGIN
# Review: mill-merge: run the deterministic path as one script — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-09-26
```

## Findings

### [NIT:consistency] Mutation flag realised as a class, not a local
**Location:** `plugins/mill/scripts/_merge.py:783-792`
**Issue:** Batch 2 specifies a local `needs_rollback` flag in `step_squash`; the code uses a `_MutationWindow` object passed to helpers.
**Fix:** None required; behaviour matches the batch-local decision (opens before first parent mutation, closes on confirmed push or `reset --hard`).

### [NIT:design] Lock acquired outside the `try`
**Location:** `plugins/mill/scripts/_merge.py:1046-1048`
**Issue:** A SIGTERM landing between `_acquire_lock` and `try:` would leave the lock file behind.
**Fix:** None required; the lock goes stale after 5 minutes and the SKILL documents that recovery.

## Verdict

APPROVE
All batches' cards are realised in `_merge.py`, `millpy-merge.py` and the SKILL, and shared decisions are applied consistently.
MILL_REVIEW_END
