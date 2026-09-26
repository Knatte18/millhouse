MILL_REVIEW_BEGIN
# Review: Ask the parent session when stuck (parent_thread)

```yaml
duration_s: 308.9
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-09-26
```

## Findings

### [NIT:scope] `*Blocked*` funnel is wider than `go-batch`'s stated coverage
**Demoted-from:** BLOCKING
**Section:** `converted-sites` (`go-batch` row), `escalate-before-recording-block`
**Issue:** `mill-go-base/SKILL.md`'s step 2b Cleanliness gate has four more halts that also `set_batch_field(..., "state", "blocked")` and "Go to *Blocked*" — out-of-scope untracked file(s) mid-batch, dead parent branch (fallback/cycle), parent diff unresolvable, and dirty tree after implementer report — none of them a `### Stuck escalation` branch. `go-batch`'s row claims coverage of "every `### Stuck escalation` branch" only, but `escalate-before-recording-block` proposes giving the shared `### Blocked` section itself a 3-parameter escalating signature, which every caller into `*Blocked*` — including these four — would then hit.
**Fix:** Name these four cleanliness-gate halts explicitly: either add them to `converted-sites` as escalating, or specify how `*Blocked*` supports a non-escalating call alongside the escalating one.

### [NIT:scope] mill-plan step 5 non-progress halt has no disposition
**Demoted-from:** BLOCKING
**Section:** `converted-sites`, "User-only (unchanged)" list
**Issue:** `mill-plan/SKILL.md` step 5's Non-progress check (`_status.set_blocked(status_path, f"non-progress round {N}", ...)`, fired on a stable planner/reviewer disagreement) is a third, distinct mill-plan halt — separate from `plan-cap` (step 6 max-rounds escape, escalated) and from `"plan-validate non-progress"` (explicitly listed user-only). It appears in neither the `converted-sites` table nor the user-only list.
**Fix:** State explicitly whether step 5's non-progress halt escalates to the parent or stays user-only, and why.

### [NIT:consistency] `millpy-fix.py` flag enumeration is incomplete
**Section:** `fixer-guidance-channel`
**Issue:** Rationale says `millpy-fix.py` "accepts only `--review-file`, `--round`, `--nits-only`, `--prior-blocking` today," but it also has `--scope`, `--stage`, `--agent-output`, `--start-sha`, `--session-id`. The "no free-text slot" conclusion still holds since none of those carry free text.
**Fix:** Reword to "accepts no free-text flag today" instead of an incomplete enumeration.

## Verdict

APPROVE
Two halt sites reachable via existing shared/adjacent code paths have no stated escalation disposition.
_Note: 2 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 0._
MILL_REVIEW_END
