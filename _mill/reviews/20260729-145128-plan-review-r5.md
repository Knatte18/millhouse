MILL_REVIEW_BEGIN
# Review: Cross-machine resume, wiki-daemon health-check, and hub-in-subdirectory config resolution gaps — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; exact point version not directly knowable)
reviewed_file: plan/
date: 2026-07-29
```

## Findings

### [BLOCKING] Phase 1b has no recovery path for a partial `relocate_and_scaffold` failure
**Location:** Batch 2 / Card 8 (`_resume_repair.relocate_and_scaffold`), Card 10 (Phase 1b Step 4), Card 11 (integration test coverage)
**Issue:** `relocate_and_scaffold` runs `move()` then `copy_millhouse()` then `_junction.create()` in sequence and lets `WorktreeError`/`OSError`/`ValueError` from the *later* two steps propagate uncaught. If `move()` succeeds but `copy_millhouse`/`_junction.create` fails, the worktree has *already* been physically relocated to `<canonical>` (the operator's own shell cwd, still pointed at the now-nonexistent `old_worktree`, is stale), yet Card 10's Step 4 failure message says "report the printed stderr and stop. No further mutation is attempted" — which is only accurate when `move()` itself is what failed. On any retry of `mill-resume`, Step 2's collision check now reports `EXISTS` at `<canonical>` (a real, half-scaffolded worktree) with the message "stale entry or another worktree... resolve manually," giving the operator no way back into the repair flow. Card 11's scenario (d) only covers the pre-move collision case, not this post-partial-failure retry state.
**Fix:** Either make `relocate_and_scaffold` best-effort-idempotent on retry (detect `canonical` already registered as the worktree and skip straight to the scaffold steps), or have Step 4's exception handler distinguish "move failed" (nothing moved) from "scaffold failed after move" (tell the operator the worktree now lives at `<canonical>` and to re-run scaffold-only, or manually complete `.millhouse`/`.wiki`) — and add an integration-test scenario exercising the post-move-scaffold-failure retry path.

## Verdict

REQUEST_CHANGES
Batch 2's off-canonical repair has no recovery path when relocation succeeds but scaffolding fails partway.
MILL_REVIEW_END
