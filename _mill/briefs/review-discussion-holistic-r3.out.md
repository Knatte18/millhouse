MILL_REVIEW_BEGIN
# Review: Plan review verdict correctness: unverified platform claims and missing nit_count in subprocess dispatch

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax
reviewed_file: _mill/discussion.md
date: 2026-07-28
```

## Findings

### [GAP] Carryforward site leaves blocking_count hardcoded at 0
**Section:** Decisions > nit-count-fix-mechanism (6th site, `_scan_approved_batches`)
**Issue:** The 6th-site fix adds `nit_count` parsing to `_scan_approved_batches()` but leaves `"blocking_count": 0` hardcoded (`_review_plan.py:114`) — unlike every other site, which computes it via `parse_blocking_count` + `count_unrecognized_severity_findings`. A batch APPROVE'd while also carrying an off-vocabulary-severity finding (verdict string and computed counts are never cross-validated in `finalize_scope()`) would have its true nonzero blocking_count silently reset to 0 on carryforward, into the same live aggregate this task is fixing — identical bug class, same site.
**Fix:** Parse `blocking_count` the same way at this site (mirroring the new `nit_count` line), or document why 0 is provably safe to hardcode here.

### [GAP] plugin.json rule checks only Context:, not Edits:
**Section:** Decisions > platform-claim-verification (`_plan_validate.py` rule)
**Issue:** The new rule requires `plugin.json` in a batch's `Context:` whenever `Creates:`/`Edits:` touches `plugins/mill/agents/`. But registering a new agent requires editing plugin.json's `agents` array (per this task's own Problem statement — explicit array disables auto-discovery), so the natural batch that creates a new agent file will list `plugin.json` in `Edits:`, not `Context:` — existing convention never duplicates an `Edits:` file into `Context:` (e.g. review-plan-batch.md:40, "Edits: files are implicitly read — do not repeat them in Context:"). This is the primary expected case, not an edge case, and will false-positive as specified.
**Fix:** Accept `plugin.json` present in either `Context:` or `Edits:` — both are already bulked into the reviewer's prompt.

### [GAP] New validator check has no mill-plan fix-table row
**Section:** Decisions > platform-claim-verification / Scope > Out
**Issue:** All 17 existing `_plan_validate.py` checks have a matching mechanical-fix row in `mill-plan/SKILL.md`'s Step 1.5 table, keyed by `check` id (e.g. `all-files-touched-mismatch`). No row is proposed for the new #714 check, and Scope > Out's "general plan-validator rule authoring... beyond the one new rule" wording doesn't say whether the fix-table row belongs to "the one new rule" (in) or is excluded general authoring (out) — leaving mill-plan's autonomous fix loop with undefined behavior the first time this check fires.
**Fix:** State explicitly whether the fix-table row is in scope (e.g. "add `plugin.json` to the batch's Context:") or the check is deliberately a halt case.

## Verdict

GAPS_FOUND
Three concrete gaps: stale blocking_count hardcode at carryforward site 6, Context-only plugin.json check false-positives on Edits:, missing mill-plan fix-table row.
MILL_REVIEW_END
