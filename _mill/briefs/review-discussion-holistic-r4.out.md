MILL_REVIEW_BEGIN
# Review: Self-discovered mill pipeline bugs: silent archive-tag push failure, ignored --max-rounds override, dead test-registry helper, truncated commit_sha in implementer reports

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: Claude (Sonnet-class; exact point version not independently confirmable)
reviewed_file: _mill/discussion.md
date: 2026-07-29
```

## Findings

### [GAP] write_local_overlay caller list in Technical Context is wrong
**Section:** Technical context — `_test_registry.py` paragraph
**Issue:** Claims `write_local_overlay` "is used by `test-reviewers.py`'s `reviewer_override` tests and referenced in `test-review-discussion-flow.py`'s comments" — verified false on both counts: `test-reviewers.py` never calls `write_local_overlay` (it writes `.millhouse/agents.local.yaml` inline directly, ~14 sites), and `test-review-discussion-flow.py` calls it directly 6 times (not merely "in comments"). The paragraph also omits `test-review-plan-flow.py`, which is the heaviest actual caller (7 direct calls) and isn't named anywhere in this sentence.
**Fix:** Correct the sentence to name the true two callers (`test-review-plan-flow.py`, 7 call sites; `test-review-discussion-flow.py`, 6 call sites) so a plan writer scoping the consolidation (Decisions §"test_registry redirected...") isn't misdirected toward `test-reviewers.py` or led to underestimate `test-review-plan-flow.py`'s footprint. Note the Decision's own "~2 files" figure happens to be numerically correct despite this misattribution.

## Verdict

GAPS_FOUND
One technical-context citation misattributes write_local_overlay's actual call sites across three files.
MILL_REVIEW_END
