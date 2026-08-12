MILL_REVIEW_BEGIN
# Review: mill-go-base: remove subprocess/psmux dispatch branches — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; exact point version not independently knowable)
reviewed_file: plan/
date: 2026-08-12
```

## Findings

### [BLOCKING:design] Card 12 bakes an ungrounded "validator-fix" concept into the tree-guard block
**Location:** batch 3 / card 12. **Issue:** the post-dispatch form's Requirements text says it fires "after prepare through finalize, including any validator-fix or retry re-invocation cycle within the same dispatch" — `validator`/`validator-fix` appears nowhere in `mill-go-base/SKILL.md`, nowhere in `_mill/discussion.md` (card 12's only `Context:` entry), and greps of `plugins/mill/scripts/` show "validator" is exclusive to the plan-review/`_plan_validate.py` machinery, unrelated to code-review dispatch. The only actual retry-shaped mechanism near a review dispatch is sub-step 4.5's ERROR-only-aggregate retry, which is a *separate* dispatch point with its own independent pre/post checkpoint pair (current lines 844/849) — not a sub-cycle "within the same dispatch" — so the sentence as written is both unsourced and structurally inaccurate about the file it describes.
**Fix:** drop the "validator-fix" clause; state only that the post-dispatch form fires once per review dispatch, immediately after that dispatch's prepare-through-finalize sequence returns, with the ERROR-only retry (sub-step 4.5) documented as its own separate pre/post pair, as the rest of card 12/13 already correctly does.

## Verdict

REQUEST_CHANGES
Card 12 introduces an unsourced "validator-fix" mechanism into the tree-guard block prose; fix before approval.
MILL_REVIEW_END
