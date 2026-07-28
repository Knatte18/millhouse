MILL_REVIEW_BEGIN
# Review: Plan review verdict correctness: unverified platform claims and missing nit_count in subprocess dispatch

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax
reviewed_file: _mill/discussion.md
date: 2026-07-28
```

## Findings

### [GAP] Skip-approved carryforward entries never get a nit_count
**Section:** Decisions > nit-count-fix-mechanism; Technical context (5 blocking_count sites)
**Issue:** `_scan_approved_batches()` (`_review_plan.py:70-119`) builds carryforward dicts with `"blocking_count": 0` but no `nit_count` key at all; these merge into `reviews[]` (lines 799-801) and feed the new `aggregate_nit = sum(r.get("nit_count", 0)...)`, so an approved-and-carried-forward batch with real `[NIT]` findings silently contributes 0 post-fix. Test 8 (skip-approved happy path) uses a NIT-free `APPROVE_TEXT` fixture, so this ships untested. Not mentioned anywhere in Scope, Decisions, or Technical context — the site inventory only covers the 5 `blocking_count`-computing sites, missing this 6th reviews[]-populating site.
**Fix:** Add `_scan_approved_batches()` to the site inventory: parse `nit_count` via `parse_blocking_count(raw, severity="NIT")` alongside its existing `parse_verdict(raw)` call, or explicitly justify excluding it the way the resume-disk-scan site's discard is justified.

### [GAP] Testing section's "no dedicated rendering-assertion tests" claim is wrong
**Section:** Testing (Template changes bullet, #717/#714)
**Issue:** Claims prose-only template changes need only "manual read-through" because "these templates have no dedicated rendering-assertion tests to extend" — but `test-review-templates.py`'s `test_kept_prose_stays_kept()` / `test_deleted_prose_stays_deleted()` already loop over all five templates (including `review-plan-holistic.md`/`review-plan-batch.md`) asserting exact phrases are present/absent in the raw source.
**Fix:** Correct the Testing section to extend `test-review-templates.py` with assertions that the new All-Files-Touched-exclusion sentence and platform-claim-verification bullet actually land in both edited templates, rather than relying on manual read-through only.

### [GAP] Platform-claim validator rule has no path pattern for 2 of its 3 stated categories
**Section:** Decisions > platform-claim-verification
**Issue:** The new `_plan_validate.py` check is scoped to batches touching "agent-definition files, slash commands, or hook wiring," but `plugin.json` currently declares only an `agents` array (no `commands`/`hooks` key, and no matching directory exists anywhere in this plugin) — and the Testing section's only worked example is agents-only (`plugins/mill/agents/*.md`). There's no source-grounded path pattern for the other two categories.
**Fix:** Narrow the decision's stated scope to agent-definition files (the one concrete, testable case), or specify the intended detection pattern for slash-commands/hook-wiring before plan-writing.

### [GAP] #720's per-batch regression test likely duplicates #709's Test 29 extension
**Section:** Testing ([MEDIUM]-fold regression bullet); Decisions > medium-severity-regression-test
**Issue:** #709's own testing plan already extends Test 29 (`[MAJOR]`-only per-batch, zero BLOCKING) with a `nit_count` assertion; #720 separately calls for a "new" per-batch test asserting one off-vocabulary finding + zero BLOCKING/NIT findings gives `blocking_count==1, nit_count==0` — the identical scenario Test 29 will already cover once extended (differs only in using MEDIUM vs MAJOR as the off-vocabulary word, which the fold-in logic treats identically).
**Fix:** Note in Testing that Test 29's #709 extension already satisfies #720's per-batch case; scope the genuinely new #720 work to the holistic path and an isolated (zero-BLOCKING/NIT) `finalize_scope()` case, which are not yet covered.

## Verdict

GAPS_FOUND
Four gaps: an nit_count blind spot in carryforward batches, a wrong testing claim, and an underspecified validator rule.
MILL_REVIEW_END
