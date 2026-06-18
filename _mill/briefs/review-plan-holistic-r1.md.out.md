MILL_REVIEW_BEGIN
# Review: Fix agent error recovery, implementer/review false-success contracts, VS Code watcher, and plan-validator Deletes — holistic

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-18
```

## Findings

### [NIT] #500 test fixture instruction is internally ambiguous
**Location:** Batch 5 / Card 5 (Tests, #500 regression)
**Issue:** The card says "Mirror the existing parsed-success cases (the ones around the verify-gate demotion tests)... but with `HEAD == start_sha`" — yet those cases (19/20/21) deliberately make a NEW commit so `HEAD != start_sha`; the implementer must instead NOT commit after `_setup_fixture` so `HEAD == start_sha`.
**Fix:** Reword to "set up the fixture as in Case 19/20 but omit the second `commit --allow-empty` so HEAD stays at start_sha"; the Decision-58 "locate by symbol, not line" guard already covers drift, so this is non-blocking.

### [NIT] Card 5 #500 guard placement vs verify-pass path is left implicit
**Location:** Batch 5 / Card 5 (#500 requirement)
**Issue:** The guard is placed "after the verify-gate early-return and before `git rev-parse HEAD`" (line ~310); since the early-return fires only on verify FAILURE, a no-commit success that PASSES verify still reaches the guard — correct, but the card never states this interaction explicitly.
**Fix:** Optionally note that the guard intentionally rejects no-commit success even when verify passes; behaviour is already correct as written, so no change is required.

## Verdict

APPROVE
Plan is source-accurate, DAG-clean, decision-faithful, fully scoped; only two cosmetic test-wording nits.
MILL_REVIEW_END
