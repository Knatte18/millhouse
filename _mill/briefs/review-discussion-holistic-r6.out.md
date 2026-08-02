MILL_REVIEW_BEGIN
# Review: Improve diagnosability of plan-validate errors and finalize verify-replay failures

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 5 (claude-sonnet-5)
reviewed_file: _mill/discussion.md
date: 2026-08-02
```

## Findings

### [GAP] Shared-checkout mechanics for module-wide vs per-batch baselines unresolved
**Section:** Decisions: `gap2-shared-transient-checkout` vs `gap2-baseline-stage-independent-of-module-wide-early-returns`; Technical context `_verify_baseline.py`
**Issue:** `gap2-shared-transient-checkout` says the module-wide command runs inside the *same* shared checkout as every batch command, but the new function's stated contract (`dict[name, list[str]]` of signatures, per Technical context) doesn't match `compute_baseline`'s preserved binary `"clean"|"pre-existing-failures"` contract and its distinct 3-run (retry + task-worktree control) corroboration algorithm (Scope explicitly keeps that contract "reused/extended, not replaced" and unchanged). Nothing specifies whether `compute_baseline` is refactored to accept an externally-supplied checkout, whether module-wide's run is recomputed via the new signature-returning function and its binary verdict derived from that, or whether two separate checkouts are actually created despite "single shared checkout ... rather than one checkout per command."
**Fix:** Add a Decision stating exactly how `compute_baseline`'s existing 3-run/control-check algorithm is threaded through the same checkout as the new per-batch 2-run/union algorithm (e.g., checkout setup/teardown extracted into a shared context manager both algorithms call into), and update the Testing section's multi-command test to cover the module-wide command's inclusion.

## Verdict

GAPS_FOUND
One unresolved architectural conflict between two Decisions on baseline-checkout sharing.
MILL_REVIEW_END
