MILL_REVIEW_BEGIN
# Review: mill-plan: entry-gate, timeline, and script-portability bugs

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; distinct from the dictated reviewer_model label)
reviewed_file: /home/knatte/Code/millhouse/wts/mill-plan-entry-gate-and-misc-bugs/_mill/discussion.md
date: 2026-09-04
```

## Findings

### [BLOCKING:consistency] #938 drift-guard halt message promises a recovery the Entry table can't deliver
**Section:** Decision `discussion-drift-guard-938`, cross-checked against `mill-plan/SKILL.md`'s Entry step-4 table and "Entry: resuming after a max-rounds block".
**Issue:** `discussion_sha:` is captured only at Phase: Plan (the decision states this explicitly: "Phase: Plan is the only site that ever creates `00-overview.md`... no separate capture is needed"). Once a drift mismatch fires `_status.set_blocked` with reason `"discussion.md changed after Phase: Plan entry (blob sha drift)"`, the operator message says "re-run `/mill-plan` to pick up the current discussion.md" — but per the Entry table a re-invocation now lands on `phase: blocked` with a `blocked_reason` that does NOT start with `"max-rounds exhausted"`, so "Entry: resuming after a max-rounds block" hard-stops it ("surface `blocked_reason`... Manual `status.md` intervention is required") without ever re-entering Phase: Plan or recapturing `discussion_sha`. A bare re-run therefore reproduces the same halt indefinitely; the promised fix is unreachable through the documented entry logic. (Worse for the pre-plan-commit check specifically: firing there leaves `plan_dir` written-but-uncommitted while `status.md` alone is committed as `blocked` — a dirty, partially-written plan tree with no described cleanup.)
**Fix:** Either (a) specify an actual recapture/recovery mechanic (e.g., an explicit operator step to delete `plan_dir` and force a fresh Phase: Plan entry, or a `--revise`-style override that re-derives `discussion_sha`), or (b) replace the halt message with accurate guidance matching the file's existing pattern for non-max-rounds blocked states ("operator investigates and clears `blocked_reason` themselves") instead of implying a bare re-run resolves it.

## Verdict

REQUEST_CHANGES
#938's drift-guard recovery message contradicts the Entry table's own blocked-resume logic; needs a real fix path or corrected wording.
MILL_REVIEW_END
