# Review: 24 (A) — mill-misc-fixes — 01-test-fixtures

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: 01-test-fixtures
date: 2026-05-07
```

## Findings

### [NIT] Plan description mildly overstates "stub-queue exhaustion" for test 5
**Step:** Batch Scope
**Issue:** Test 5 seeds 3 responses and 3 are consumed (alpha + beta + gamma all call the reviewer because `parse_batch_refs` returns [] for broken `Reads:` fields) — queue never exhausts; the test fails because no `ReviewError` is raised, not because the queue runs out.
**Fix:** No code change needed; the root-cause diagnosis and the fix are correct. Accuracy note only.

### [NIT] Card 3 fixture field order is non-canonical after rename
**Step:** Card 3
**Issue:** After replacing `Modifies:` → `Edits:` and `Reads:` → `Context:`, the resulting order in `01-core.md` will be `Edits:` before `Context:`, which is the reverse of the canonical sequence defined in `plan-batch.md`. `parse_batch_refs` is order-insensitive so this has no behavioural impact.
**Fix:** Out of scope per the card's explicit constraint ("Do not modify any other line in the file"); acceptable as a NIT.

## Verdict

APPROVE
All four cards are correctly scoped, internally consistent, and sufficient to move the failing-test count from 4 to 0.