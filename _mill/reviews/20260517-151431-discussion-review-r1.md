I have verified all key technical claims. Writing the review now.

---

# Review: 66 (A) — Review sandbox follow-up: guard exceptions + bare-exit + sandbox argv

```yaml
verdict: APPROVE
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-17
```

## Findings

### [NOTE] _review_plan.py already catches parse_verdict internally
**Section:** Scope — `_review_plan.py`
**Issue:** The scope says "apply the same shape to `parse_verdict` failures in both per-batch and holistic paths," implying new code is needed — but `_review_plan.py` already catches `ReviewError` from `parse_verdict` internally in the per-batch path (`except ReviewError` at line 251) and the holistic path (`except ReviewError` at line 607). Both paths already return verdict-ERROR dicts, so `_review_plan.run()` does not currently raise on `parse_verdict` failure, and the CLI already exits 0 for those cases.
**Fix:** Clarify that plan-review changes are verify/adjust (not rewrite): confirm the existing error-entry shape matches the standard, and check the holistic handler writes the raw to a review file (which it does at line 608) — no new implementation needed beyond that.

### [NOTE] Mill-go step numbering inconsistency for dead-worker re-fire
**Section:** Scope vs. Decision — `mill-go-holistic-recovery-dead-bg`
**Issue:** The scope says the dead-worker branch "proceeds straight to step 3 (fire fresh CLI via millpy-bg)," but the decision says "proceed to step 2 (fire fresh CLI)." Against the current SKILL.md, step 2 is `_status.append_phase` and step 3 is `millpy-bg` invocation — so these are behaviorally different. On a resume, step 2 was already executed; re-running it appends a duplicate "holistic-reviewing" phase entry.
**Fix:** Confirm intent is to skip the status-phase append and jump to step 3 directly (scope wording appears correct); update the decision's parenthetical from "(fire fresh CLI)" to "(step 3, fire fresh CLI via millpy-bg)" to eliminate the ambiguity.

## Verdict

APPROVE
Both findings are implementation-detail clarifications; no blocking information gaps exist.