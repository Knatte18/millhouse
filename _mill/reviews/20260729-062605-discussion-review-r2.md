MILL_REVIEW_BEGIN
# Review: mill-start: tracked _mill/ files disappear from the working tree mid-review-loop; existing safeguard covers only status.md

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax
reviewed_file: _mill/discussion.md
date: 2026-07-29
```

## Findings

### [GAP] Full-subtree restore can clobber uncommitted status.md writes
**Section:** Decisions: "Detection query and restore granularity" / "Closing the Agent-mode bracketing gap"
**Issue:** mill-go's per-batch Code Review loop appends `reviewing-{batch_name}-r{N}` to status.md (`mill-go/SKILL.md:357`) with no commit before that round's Agent-mode `--stage prepare` dispatch; the new pre-prepare `check_and_restore` bracket lands inside this uncommitted window. An unrelated deletion elsewhere under `_mill/` would trigger `git checkout HEAD -- _mill/`, silently discarding the just-appended, not-yet-committed timeline row — `_status.phase_entry_timestamp` reads this same on-disk file for the crash-recovery freshness check, so the loss is not merely cosmetic.
**Fix:** Require an immediate commit after any `append_phase` call that precedes a bracketing checkpoint, have `check_and_restore` preserve/reapply pre-existing uncommitted tracked diffs around the restore, or explicitly document this as a second accepted residual risk alongside the round-fresh-artifact one.

### [NOTE] Ruled-out-mechanism citation is inaccurate
**Section:** Technical context (ruled-out deletion mechanisms bullet)
**Issue:** The bullet states `clean_ephemeral_scope_violations` "is only reachable from `_implementer_common.py`/`millpy-implement.py`"; neither file calls it (confirmed via grep — zero hits in either). Its only actual call site is `mill-go/SKILL.md`'s Handoff-phase "Scope violations cleanup gate" inline Python.
**Fix:** Correct the citation to mill-go's Handoff phase. The ruled-out conclusion itself still holds — Handoff runs once after all batches complete, which is even less "review-loop" than the cited path.

### [NOTE] Concurrent-session claim overstates lock-free-ness
**Section:** Technical context ("Not ruled out" bullet)
**Issue:** "Nothing in the codebase prevents two orchestrators from running against one task worktree simultaneously" is inaccurate for mill-go specifically — `millpy-builder-lock.py` (mill-go/SKILL.md Entry step 4) guards exactly this case. Only mill-start and mill-plan genuinely lack any lock (confirmed: no lock/acquire hits in either SKILL.md).
**Fix:** Scope the claim to mill-start/mill-plan, since mill-go's builder lock already guards its own concurrent-session case.

## Verdict

GAPS_FOUND
One GAP: the widened restore's interaction with pending-uncommitted status.md writes is unaddressed.
MILL_REVIEW_END
