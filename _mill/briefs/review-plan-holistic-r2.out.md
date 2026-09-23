MILL_REVIEW_BEGIN
# Review: compute_baseline: use the task worktree's own pre-edit state, not a parent-branch checkout — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: plan/
date: 2026-09-23
```

## Findings

### [BLOCKING:design] Batch 1 deletes an accessor while its only unguarded caller survives until Batch 4
**Location:** Batch 1 / Card 1 vs. Batch 4 / Card 21 (`plugins/mill/scripts/_implementer_common.py:1177`)
**Issue:** Card 1 deletes `_status.get_baseline_parent_sha`/`set_baseline_parent_sha`. Batch 4 (Card 21) is the only batch that removes the on-demand-compute prelude in `_run_verify_gates` that calls `baseline_parent_sha = _status.get_baseline_parent_sha(status_path)` at line 1177 — verified in current source, this call sits directly inside the `if (not batch_verify_baseline and replay_signatures and status_path is not None and verify_cmd is not None):` block with **no surrounding try/except** (unlike the guarded `compute_batch_baseline_on_demand` call two lines below it, which IS wrapped in `try/except Exception`). Since Batch 4 depends on Batch 3, which depends on Batch 1, the DAG guarantees Batch 1's deletion lands strictly before Batch 4's caller-removal. For the entire window in between (Batch 1's own later cards, all of Batch 2, all of Batch 3, and the start of Batch 4 before Card 21 commits), any batch-level verify-gate failure with no cached baseline raises an unguarded `AttributeError` inside `_run_verify_gates`, crashing that batch's `--stage finalize`/`--stage full` call instead of producing the intended "stuck"/gate-strictly JSON. Card 1's own rationale ("deleting them here does not break batch 4's own diff") addresses patch/diff safety only, not this runtime window — it does not establish that no verify-gate failure will occur in Batches 1–3's own dispatches, which is the very case this gate exists to handle.
**Fix:** Move the deletion of `get_baseline_parent_sha`/`set_baseline_parent_sha` out of Batch 1 Card 1 and into Batch 4 (alongside Card 21, which is where the last caller is actually removed), or otherwise ensure no batch lands before Batch 4 while this unguarded caller still exists.

## Verdict

REQUEST_CHANGES
Batch-1 deletes a `_status` accessor whose only unguarded caller isn't removed until Batch 4, an unsafe runtime window.
MILL_REVIEW_END
