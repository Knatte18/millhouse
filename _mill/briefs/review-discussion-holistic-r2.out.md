MILL_REVIEW_BEGIN
# Review: mill-plan SKILL.md: Phase Plan Review gate, convergence, and DAG-validation correctness bugs

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet (environment-reported as "Sonnet 5" / claude-sonnet-5)
reviewed_file: _mill/discussion.md
date: 2026-08-21
```

## Findings

### [BLOCKING:design] #896 fix's insertion point ignores step 4.5's ERROR-retry path
**Section:** Decision `#896` + `mill-plan/SKILL.md` Phase: Plan Review steps 2-4.5.
**Issue:** The decision places the unconditional `plan-review-r{N}` append "right after step 2's dispatch returns and the verdict is known, before the 4a branch text." But step 4.5 (ERROR-only-aggregate retry, current SKILL.md lines 488-525) sits logically between step 2's dispatch and 4a-4d: on an ERROR verdict, absent JSON, or a usage-error, the round is explicitly "not consumed" and 4a-4d are skipped entirely for a retry. An append placed immediately after step 2 fires before this screening, so it would write a Timeline `plan-review-r{N}` row (and overwrite `phase:` to that value, since `append_phase` sets both) for a round that produced no reviewable output and gets retried under the same N — then fire again when the retry actually resolves, producing duplicate `plan-review-r{N}` rows for one logical round. The file itself already warns about exactly this hazard elsewhere (Entry "resuming after a max-rounds block" section: "`_status.append_phase` never dedupes... pre-writing round N's own completion marker before round N has even run would leave two identical `plan-review-r{N}` entries").
**Also:** the claimed precedent — "matching the pattern `mill-go-base/holistic-review.md` already uses" — doesn't actually support this placement: that file's analogous per-round marker (`holistic-reviewing`) is appended *before* dispatch (step 2, unconditionally, every round), and its only post-verdict marker (`holistic-approved`) fires solely inside the APPROVE branch on convergence, never unconditionally after every dispatch. Neither matches "append unconditionally right after dispatch, before any verdict-branch."
**Fix:** State explicitly that the unconditional append happens only after step 4.5's screening determines the round is reviewable (i.e., after ruling out `error_kind: usage`, `verdict: ERROR`, and absent-JSON), not immediately after step 2's dispatch returns.

## Verdict

REQUEST_CHANGES
One BLOCKING: #896's fix placement double-counts/misfires Timeline rows on ERROR-retried rounds.
MILL_REVIEW_END
