MILL_REVIEW_BEGIN
# Review: Track _mill/briefs/ instead of gitignoring them -- holistic

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: plan/
date: 2026-06-08
```

## Findings

### [NIT] review-output.schema.md table still cites sonnetmax_tool
**Location:** Batch 1, Card 2
**Issue:** Card 2 updates the example block (`reviewer_model: sonnetmax_tool` -> `sonnetmax`) but the metadata-fields table still shows `(e.g. sonnetmax, sonnetmax_tool)` in the `reviewer_model` row description.
**Fix:** In Card 2's edits to `plugins/mill/templates/review-output.schema.md`, also update the table row to remove `sonnetmax_tool` from the example list, e.g. `(e.g. sonnetmax, sonnethigh)`.

### [NIT] haiku gets tooluse: true under the convention, which is semantically surprising
**Location:** Batch 1, Card 1 and Card 5
**Issue:** The symmetric-pair rule applies to all 10 combos including `haiku`. Under the convention the unsuffixed `haiku` entry gets `tooluse: true`, yet `haiku` is used exclusively as `roles.implementer.model` and `merge.model` -- never as a reviewer. The Card 5 convention test will then require `haiku["tooluse"] is True`.
**Fix:** Either (a) document that the `tooluse` flag is only consumed by reviewer dispatch and is irrelevant for implementer/merge entries, or (b) carve out `haiku` from the convention test. Option (a) is lower-risk.

## Verdict

APPROVE
Plan is coherent, all shared decisions are faithfully implemented, test coverage is appropriately scoped, and no structural gaps found.
MILL_REVIEW_END
