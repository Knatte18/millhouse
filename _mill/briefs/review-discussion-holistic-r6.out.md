MILL_REVIEW_BEGIN
# Review: Blocking phase-wait gate for mill-plan/mill-go chaining

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5 (self-assessed; not independently verifiable)
reviewed_file: _mill/discussion.md
date: 2026-07-30
```

## Findings

### [GAP] entry_wait:false fallback conflicts with the widened mill-go match
**Section:** "Master on/off config switch" vs. "Exact phase-table edit sites"
**Issue:** The switch Decision says disabling `pipeline.entry_wait` reverts "both entry-gates to today's exact hard-halt behavior and message text, unchanged," but "Exact phase-table edit sites" describes widening mill-go's row match (adding `plan-review-r{N}`/`plan-fix-r{N}` regexes) as an edit to the row itself, not conditioned on the switch. Verified against `mill-go/SKILL.md`'s current phase table (lines 76-83): today, `plan-review-r{N}`/`plan-fix-r{N}` fall into the generic "any other → surface + halt" row, not the "finish mill-plan" row. If `matches_wait_trigger`'s widened set applies unconditionally (as the Technical Context's description of that helper implies — it's the single entry-gate check, with no mention of being itself gated by config), disabling the feature would newly route those two phases into the "finish mill-plan" message — a real behavior change, contradicting "unchanged."
**Fix:** State explicitly whether `entry_wait: false` (a) keeps the widened match but only swaps wait→halt, deliberately changing which message those two phases get today, or (b) also narrows the match back to the old exact set at that call site, so `matches_wait_trigger` needs an additional parameter/branch for the disabled case.

## Verdict
GAPS_FOUND
One GAP: config-off fallback behavior for mill-go's widened trigger match is unstated/contradictory.
MILL_REVIEW_END
