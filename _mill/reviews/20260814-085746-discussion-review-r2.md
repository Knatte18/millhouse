MILL_REVIEW_BEGIN
# Review: mill-plan SKILL.md: step 6 max-rounds escape bugs, self-run validator citation errors, and Step 1.5 fix-table wrong remedies

```yaml
duration_s: 269.0
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5
reviewed_file: _mill/discussion.md
date: 2026-08-14
```

## Findings

### [BLOCKING:design] `--revise`-resume keys on `phase: blocked`, but not every halt sets it
**Section:** Decision `revise-blocked-resume` (#852). **Issue:** The widened `--revise` pre-check and the new Entry-table `blocked` row both gate exclusively on `phase == "blocked"`. Per `mill-plan/SKILL.md` itself, only step 5 (non-progress) and step 6 (max-rounds escape) are documented as calling `_status.set_blocked` (lines 12, 359 explicitly enumerate just these two). Step 1.5's validator two-pass cap (`halt with BLOCKED: plan-validate non-progress`, line ~300) and step 4.5's non-reviewable-round two-pass cap (`BLOCKED: plan review no-JSON round {N}` / `BLOCKED: review ERROR-only round {N}`, lines ~478-479) never mention `_status.set_blocked`, and the Handoff guard (line 525-527) *explicitly* states its failure "leaves status.md untouched" — i.e. these halts do not set `phase: blocked`. A run stuck on any of these paths would have `phase` stay at whatever it was (e.g. `planning`), satisfying neither `--revise` condition, so the operator would hit the unchanged "condition not met" halt and gain no resume path. **Fix:** State explicitly whether these other halt sites are in scope for #852 (and if so, decide whether they also need a `_status.set_blocked` call added) or record why they're deliberately excluded.

### [NIT:consistency] Entry-gate-wait BLOCKED branch text becomes stale once #852 lands
**Section:** Technical context / `mill-plan/SKILL.md` "Entry-gate wait for upstream mill-start" (~line 98). **Issue:** That branch's text says "mill-plan's phase table has no pre-existing `blocked` row to reuse the exact message shape from (unlike mill-go's side)" — but #852's own decision adds exactly such a row to the Entry-table. The discussion doesn't flag this now-superseded sentence for update. **Fix:** Note in the Decision that this cross-reference should be revisited (either point it at the new row or drop the "no pre-existing row" caveat) when the plan touches Entry step 4.

## Verdict

REQUEST_CHANGES
One BLOCKING: #852's blocked-resume premise doesn't cover all halt paths that leave `phase` un-set to `blocked`.
MILL_REVIEW_END
