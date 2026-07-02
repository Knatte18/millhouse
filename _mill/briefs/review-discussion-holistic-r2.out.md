MILL_REVIEW_BEGIN
# Review: Fix agent-mode dispatch races and pipeline gaps

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-02
```

## Findings

### [GAP] Transient-worktree cleanup ignores junction-strip invariant
**Section:** Decisions § baseline-aware module-wide verify gate; Constraints
**Issue:** The decision creates junctions from the task worktree's `.venv`/`node_modules`/`vendor` into a transient worktree, then removes that worktree via `git worktree remove` in try/finally — but CLAUDE.md's hard constraint ("Recursive deletion: strip junctions first ... skipping wipes targets through junctions") is not acknowledged; the removal can delete the real dependency dirs through the reused-dependency junctions.
**Fix:** Add a constraint requiring `_junction.strip_all_in_worktree` (or equivalent) on the transient worktree's reused-dependency junctions before `git worktree remove`, inside the same finally.

### [GAP] NITS_ONLY "boolean render token" is infeasible in `_render`
**Section:** Decisions § fixer-brief nits-only carve-out (#592)
**Issue:** `_render.render` (`_render.py`) supports only flat `<TOKEN>` string substitution — no conditional/`if` block grammar. A "boolean NITS_ONLY token" cannot include/exclude a carve-out block, and the strict sentences at `fixer-holistic-brief.md:71,84` / `fixer-batch-brief.md:65,78` are hardcoded prose that stays strict regardless of a boolean value.
**Fix:** Specify the token value is the fully-rendered carve-out text (carve-out prose when `nits_only`, empty string otherwise) computed in `millpy-fix.py`, and require both strict sentences be restructured so that substituted string replaces/augments the hardcoded strict clause.

### [NOTE] No bounded wait after a "running" liveness probe in agent-mode
**Section:** Decisions § liveness probe; Scope step 4
**Issue:** When `TaskOutput(block:false)` reports "running" the orchestrator takes no action and waits for the agent's next notification, but agent-mode has no max-wait guard (line 161's bound is subprocess/psmux-only); a zombie agent that dies without emitting a notification leaves the orchestrator waiting indefinitely.
**Fix:** State the expected behavior for a persistently-"running" probe (a bounded re-check/escalation, or an explicit note that unbounded wait is the accepted harness contract for agent-mode).

## Verdict

GAPS_FOUND
Two mechanism gaps (junction-strip on cleanup, render-token feasibility) must resolve before plan writing.
MILL_REVIEW_END