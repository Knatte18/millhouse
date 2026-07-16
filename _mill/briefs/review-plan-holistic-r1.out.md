MILL_REVIEW_BEGIN
# Review: Batch verify/baseline/completeness gates produce false positives or time out — holistic

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-07-16
```

## Findings

### [NIT] Card 4 wording contradicts Card 3/6 on already_complete
**Location:** Batch 01, Card 4 (vs Card 3, Card 6)
**Issue:** Card 4 says extract `cards_done` and `already_complete` and "pass both through to the `_batch_completeness_stuck`/`_reclassify_verify_failure` calls" — but Card 3's signature and Card 6 both state `_reclassify_verify_failure` must NOT take `already_complete`; passing it literally would raise TypeError.
**Fix:** Reword Card 4 so `already_complete` is threaded only to `_batch_completeness_stuck`, while `cards_done` goes to both functions.

### [NIT] Retiering gate wired on only one of four finalize paths
**Location:** Batch 02, Card 9
**Issue:** `_go_build_tag_retiering_stuck` is inserted only on the explicit-success branch, whereas the sibling verify and completeness gates run on all four `_forward_output` paths (explicit-success plus the three no-JSON inference fallbacks); a Tier-1 build break in a batch that finalizes via inference would go undetected — the exact #642 failure mode.
**Fix:** Either wire the retiering gate into the three inference paths too, or add one sentence in Card 9 justifying explicit-success-only scoping.

## Verdict

APPROVE
Plan is coherent, well-sequenced, and constraint-compliant; two minor wording/coverage NITs only.
MILL_REVIEW_END
