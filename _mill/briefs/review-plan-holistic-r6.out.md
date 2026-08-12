MILL_REVIEW_BEGIN
# Review: mill-go-base: remove subprocess/psmux dispatch branches — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; exact minor version not independently knowable)
reviewed_file: plan/
date: 2026-08-12
```

## Findings

### [NIT:consistency] Card 20 miscounts step 6.5's sub-items as two
**Location:** batch 5, card 20 **Issue:** "`6.5` becomes `5.5`, and its two numbered sub-items keep their `1.`/`2.`/`3.` local numbering" says "two" but lists three markers (1/2/3), and the source's step 6.5 genuinely has three numbered sub-items (warm `SendMessage`, `--resume-incomplete` fallback, After recovery). **Fix:** change "two" to "three" (or drop the count word) so the prose doesn't contradict its own enumeration.

### [NIT:consistency] Cards 7 and 11 drop the source's arrow in "verbatim" preserved quotes
**Location:** batch 2, card 7 (NIT-fix trailing sentence) and card 11 (same sentence, holistic copy) **Issue:** both cards quote the trailing sentence to preserve as "...on stuck escalate via the existing Stuck escalation path," but the actual `SKILL.md` text reads "...on stuck → escalate via the existing Stuck escalation path" (with the U+2192 arrow) — the plan's own "must be preserved verbatim" claim doesn't byte-match its illustrative quote. **Fix:** correct the quoted excerpts in cards 7 and 11 to include the arrow, or note explicitly that the implementer preserves the on-disk text rather than the plan's paraphrase.

## Verdict

APPROVE
Plan is internally consistent, source-grounded, and DAG-valid; only two illustrative-quote/count nits remain.
MILL_REVIEW_END
