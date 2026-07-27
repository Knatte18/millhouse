MILL_REVIEW_BEGIN
# Review: Plan review verdict correctness: unverified platform claims and missing nit_count in subprocess dispatch

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax
reviewed_file: _mill/discussion.md
date: 2026-07-27
```

## Findings

### [GAP] Resume-disk-scan "5th site" nit_count patch is a no-op
**Section:** Decisions > nit-count-fix-mechanism (bullet 2); Technical context resume-round disk-scan (~738-749)
**Issue:** `_disk_reviews`, built by this block in `_review_plan.py`, is never merged into `reviews` (no `reviews.extend`/`append(_disk_reviews)` anywhere in `run()`) — only its `len()` reaches a log line, and `test-review-plan-flow.py` Test 17 confirms `reviews` is holistic-only after resume ("reviews has 1 entry (holistic only, bug C fix #184)"), so the proposed `nit_count` line patches a value that never reaches `ReviewResult`.
**Fix:** State that only 4 of the 5 sites are live for the actual bug, and either drop the 5th-site patch or explain why a computation that never reaches the return value still needs the extra line.

### [GAP] Testing section cites the wrong test for holistic NEED_CONTEXT coverage
**Section:** Technical context (`test-review-plan-flow.py` citation); Testing
**Issue:** Line 1691 is inside Test 29 (`[MAJOR]` per-batch fold-in regression), not a holistic NEED_CONTEXT test; the actual holistic-NEED_CONTEXT-retry-success test (Test 7, ~561-580) never asserts `blocking_count` at all, and no existing test covers the holistic NEED_CONTEXT no-resolve branch.
**Fix:** Correct the citation and state that both named NEED_CONTEXT branches need net-new test cases, not an assertion added "alongside" pre-existing coverage that doesn't exist.

### [NOTE] Problem section overstates mill-plan's current reliance on nit_count
**Section:** Problem
**Issue:** "orchestrators (mill-plan) branch directly on blocking_count/nit_count" is only half accurate — grep of `mill-plan/SKILL.md` shows zero references to `nit_count`; step 4a instead re-reads the review file directly for `[NIT]`-prefixed findings, so only `blocking_count` (already correct in `run()`) is branched on today.
**Fix:** Reframe the rationale as restoring schema consistency with code-review's already-correct `nit_count` flow, not as fixing an active mill-plan mis-read.

### [NOTE] Platform-claim criteria bullet names claim categories the concrete fix can't verify
**Section:** Decisions > platform-claim-verification
**Issue:** The bullet's example categories ("tool-call parameter shapes," "subagent resolution") have no corresponding local manifest/doc file to check against (`claude-code-guide` appears nowhere in-repo outside this discussion), yet the only concrete enforcement (the new `_plan_validate.py` rule) covers plugin.json for agent/command/hook-touching batches only — bulk-mode reviewers hitting any other platform claim have no stated fallback.
**Fix:** Add a caveat scoping "must verify" to claims a manifest actually present in context can answer, rather than implying uniform coverage across all listed example categories.

## Verdict

GAPS_FOUND
Two GAPs undermine the discussion's own technical-context accuracy: a dead-code fix site and a mis-cited test line.
MILL_REVIEW_END
