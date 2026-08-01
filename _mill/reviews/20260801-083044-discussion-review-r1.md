MILL_REVIEW_BEGIN
# Review: Add mill-quick: skip-review pipeline for simple tasks

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-08-01
```

## Findings

### [GAP] "Mirror mill-go's Pre-done gate exactly" contradicts the null-halt decision
**Section:** Decisions/verify-mechanism; Technical context (done_gate bullet)
**Issue:** Technical context says done_gate execution should "mirror mill-go's Pre-done gate exactly." Read source: `mill-go/SKILL.md` "0. Pre-done gate" explicitly does `if not gate_cmd: sys.exit(0)` — i.e. it *skips* verification and proceeds when `done_gate` is null, the opposite of mill-quick's Decision to hard-halt before any edit when null.
**Fix:** State explicitly in Technical context that mill-quick's null-handling deliberately diverges from mill-go's (only the subprocess-construction/non-zero-exit handling is mirrored), so a plan writer doesn't copy mill-go's skip-on-null branch verbatim.

### [GAP] "Each pushed immediately" push-discipline claim is not what mill-go/mill-start actually do
**Section:** Technical context (commit discipline bullet)
**Issue:** Claims phase-timeline commits are "each pushed immediately — matching every other mill skill's push-per-phase-commit discipline." Source check: `mill-go/SKILL.md` Board discipline states plainly "The Builder's own state commits (Prepare, Approve, blocked, done) ... do not push — mill-merge pushes the full task branch at task end." mill-start's own terminal Handoff commit (`mill-start: handoff {slug}`) likewise shows no explicit push in its SKILL.md step. mill-quick's design (single inline session, no CLI/subagent) is architecturally closest to mill-go's Builder role, whose own commits are the ones documented as *not* pushing immediately.
**Fix:** Decide explicitly whether mill-quick pushes every phase commit (implementing/done/blocked) or leaves that to mill-merge like mill-go's Builder commits, and correct the Technical context claim to match whichever source pattern is actually being followed.

### [GAP] No recovery path for a session crash/interrupt while `phase: implementing`
**Section:** Decisions/failure-handling; Scope (intermediate phase bullet)
**Issue:** Only the done_gate-failure path is handled (→ `blocked`). If the invoking session dies or is interrupted between writing `phase: implementing` and reaching the done_gate check (no fixer/retry loop exists to catch this), the task is stuck at `implementing` with no discussion.md/plan/Batches. `mill-go/SKILL.md`'s own entry-gate table treats `implementing`/`reviewing`/`fixing` as "resume" — that resume path assumes a `plan.md`/`## Batches` structure mill-quick's zero-artifacts Decision never creates, so a later `/mill-go` run against an orphaned mill-quick task would likely fail confusingly rather than surfacing a clear error. mill-quick's own entry gate can't resume it either (requires `phase: discussing`).
**Fix:** Either define an explicit recovery/cleanup instruction for this orphaned state (e.g. operator manually calls `_status.set_blocked`), or note the risk and point to `mill-cleanup`/`mill-abandon` as the intended manual escape hatch.

## Verdict

GAPS_FOUND
Three source-grounded contradictions between discussion claims and actual mill-go/mill-start behavior need resolving before plan writing.
MILL_REVIEW_END
