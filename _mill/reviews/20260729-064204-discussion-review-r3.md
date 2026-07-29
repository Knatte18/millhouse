MILL_REVIEW_BEGIN
# Review: mill-start: tracked _mill/ files disappear from the working tree mid-review-loop; existing safeguard covers only status.md

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax
reviewed_file: /home/knatte/Code/millhouse/wts/mill-start-tracked-files-vanish-mid-review/_mill/discussion.md
date: 2026-07-29
```

## Findings

### [GAP] Subprocess/psmux mid-run deletions still hard-block
**Section:** Scope (Out) / Closing the Agent-mode bracketing gap
**Issue:** `worktree_snapshot_guard`, left unchanged per Scope, still raises `ReviewerOverstepError` and blocks with no auto-restore ("the operator resets manually after investigating," `_review_common.py:108-114`) on a deletion inside its wrapped subprocess/psmux window (`_review_discussion.py:215`, identically `_review_plan.py:643`, `_review_code.py:622`) — exactly the "block on detection" behavior the "Detection behavior: record, don't block" Decision rejects as disproportionate.
**Fix:** Either document this as a second accepted residual risk (parallel to round-fresh artifacts) with rationale, or reconsider excluding `worktree_snapshot_guard` from scope.

### [GAP] write_brief's unlink call omitted from ruled-out mechanisms
**Section:** Scope (Out) / Technical context
**Issue:** `_agent_dispatch.write_brief` (`_agent_dispatch.py:191`) calls `output_path_for(brief_path).unlink(missing_ok=True)` on every prepare-stage call across all three review CLIs — a real delete on the exact code path Technical context calls free of "recursive-delete... logic," so "ruled out every plausible in-repo mechanism" overstates completeness.
**Fix:** Name this call in the ruled-out list (it only ever targets one untracked same-round `.out.md`, so it doesn't explain the full cross-tree incident) and cite it as concrete grounding for the "round-fresh artifacts" residual-risk Decision.

### [GAP] Recovery-log section creation/ownership undecided
**Section:** Detection behavior: record, don't block
**Issue:** The new `## Tracked-file recovery log` status.md section has no designated owner — every existing section (`## Timeline` via `append_phase`, `## Batches` via `init_batches`) has a dedicated `_status.py` function that requires the fence to already exist, but Scope's "In:" list names only `_treeguard.py` as new code.
**Fix:** Decide whether `status-discussing.md` gains the section header at spawn time, or a new `_status.py` helper creates it lazily on first trigger.

## Verdict

GAPS_FOUND
Three GAPs: subprocess/psmux restore asymmetry, an omitted deletion mechanism, and an unresolved status.md section-ownership question.
MILL_REVIEW_END
