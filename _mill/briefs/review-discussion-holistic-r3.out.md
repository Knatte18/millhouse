MILL_REVIEW_BEGIN
# Review: Cross-machine resume, wiki-daemon health-check, and hub-in-subdirectory config resolution gaps

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-07-29
```

## Findings

### [GAP] Session cwd invalidated by `git worktree move` mid-repair
**Section:** mill-resume-relocate-then-scaffold, mill-resume-confirmation-gate
**Issue:** mill-resume is invoked "from inside" the off-canonical worktree (per scope's own reactive-detection framing), and the repair phase then runs `git worktree move <old-path> <canonical-path>` on that same directory — but no decision addresses what happens to the running skill/session's own working directory once its anchor is moved out from under it mid-phase (relevant given this repo's own convention that tool calls must use absolute paths, not rely on an implicit cwd).
**Fix:** Add an explicit instruction that all phases following the move (Phase 7/8 equivalents, reporting) must operate against the new canonical path via absolute paths, and confirm whether the agent session itself needs to be told to reorient.

### [GAP] `pull()` failure taxonomy doesn't cover non-fast-forward/diverged state
**Section:** health-check-failure-semantics; Technical context (`wiki/_sync.py:156 pull()`)
**Issue:** `pull()`'s own docstring (verified) states `WikiPushError` is raised both for "git pull --ff-only failed" (e.g. network) and "non-fast-forward state" (local wiki has diverged) — but the decision's binary split only classifies "missing/invalid `.git`" as hard and "network unreachability" as soft, leaving a diverged/non-ff local wiki (a real, non-transient problem, arguably closer to the hard-fail bucket) unclassified, and there's no way to distinguish the two causes from `WikiPushError` alone without inspecting its message string.
**Fix:** Explicitly decide the semantics for a non-fast-forward pull failure, and note how `_handle_health` is meant to distinguish it from a network-only failure given `pull()`'s current single exception type.

## Verdict

GAPS_FOUND
Two new feasibility/ambiguity gaps in the relocate-worktree and health-check failure semantics not raised in prior rounds.
MILL_REVIEW_END
