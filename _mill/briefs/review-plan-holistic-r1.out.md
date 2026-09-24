MILL_REVIEW_BEGIN
# Review: Entry-gate wait: drop nonexistent Monitor persistent:true — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/
date: 2026-09-24
```

## Findings

### [NIT:consistency] Poll script TIMEOUT text is orch-wait specific
**Location:** Batch 1 / Card 2 **Issue:** Card 2 reuses "the same inline poll" from card 1, whose TIMEOUT echo hard-codes "waiting for orch-review.md", but orch-review polls `discussion.md`. **Fix:** State that the echoed filename is substituted with `discussion.md` for orch-review.

### [NIT:consistency] Card 3 "Six skill files" count unverified
**Location:** Batch 1 / Card 3 **Issue:** harness-tool-contracts.md line 5 says "Four skill files already carry inline copies"; the plan bumps it to six without confirming that the orch skills carry copies of this material rather than references. **Fix:** Word the count as the four inline copies plus two orch consumers, or state that it counts the consumers.

## Verdict

APPROVE
Plan is sound and source-consistent; only two minor wording nits.
MILL_REVIEW_END
