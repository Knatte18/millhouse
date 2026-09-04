MILL_REVIEW_BEGIN
# Review: mill-go: concurrency, silently-ignored fields, and bookkeeping bugs in execution/handoff

```yaml
duration_s: 190.0
verdict: REQUEST_CHANGES
reviewer_model: sonnet
reviewer_self_id: Claude Sonnet 5 (claude-sonnet-5)
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

### [BLOCKING:design] #906 collision "bump past" resolution breaks its own gap-free guarantee
**Section:** Scope bullet #906 / Decision `906-reuse-existing-plan-validate-helper`
**Issue:** N is defined as `max(existing card numbers in target batch) + 1` specifically to preserve the target batch's gap-free numbering (required by `_check_card_numbering`'s within-batch check, `_plan_validate.py:924-955`), but the same passage then says N gets "bumped past any collision" when the batch-relative number is already used by another batch. Bumping N past `max+1` while the target batch's cards stay at `{1..max}` leaves `max+1` unfilled — a gap the within-batch check (lines 924-955) will itself flag, directly contradicting the stated preservation goal.
**Fix:** Specify what "bumped past" actually does on collision — e.g. fill every intermediate number up to the bumped value with additional cards, renumber the colliding batch instead, or pick a different target batch — so the resolution doesn't reintroduce the exact gap the target-batch-relative rule exists to avoid.

### [BLOCKING:design] #906 gives no target-batch selection rule for holistic self-resolve
**Section:** Scope bullet #906 / `plugins/mill/skills/mill-go-base/holistic-review.md:185-189`
**Issue:** The fix instructs the Builder to append `### Card N:` to "the target batch's own `## Cards` list," applied identically to both the per-batch (SKILL.md:853-856, target batch = batch_name in scope, unambiguous) and holistic occurrences. But holistic-review.md's own existing text (line 186, unchanged by this discussion) says the stuck-JSON reason may name "a specific batch, span several, or name none at all" — so a single target batch is not always identifiable in the holistic case.
**Fix:** State what the Builder does when the holistic failure reason names zero or multiple batches — e.g. fall back to the plain `## Prior failure` bullet only (no card insertion) in that case, or require the reason to name exactly one batch before attempting card insertion.

## Verdict

REQUEST_CHANGES
#906's card-numbering collision handling and its holistic-scope target-batch selection are both underspecified/self-contradictory.
MILL_REVIEW_END
