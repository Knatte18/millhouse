MILL_REVIEW_BEGIN
# Review: mill-go/mill-plan/mill-merge: dispatch-classification, watchdog, entry-gate, and implementer-compliance gaps (round 2)

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5
reviewed_file: _mill/discussion.md
date: 2026-08-09
```

## Findings

### [GAP] `--revise` step 0.5 positioned before its own required path state exists
**Section:** Decisions / `mill-plan-revise-reentry` (#786)
**Issue:** The decision places "Entry step 0.5 — Parse arguments" immediately after Step 0 and before Entry step 1, and states its `--revise` validity check reads `phase: planned` via `status_path` and the overview's `approved:` flag directly at that step. But confirmed from `mill-plan/SKILL.md`: `status_path` isn't resolved until the "Path Setup" block (after items 1-3, which themselves resolve `git_root`/config only after Step 0), and `plan_dir` (needed to locate `00-overview.md`) is today derived only inside Phase: Plan / Phase: Plan Review (`plan_dir = worktree_root / cfg['paths']['plan_dir']`, line ~231) — not during Entry at all. A step positioned before Entry step 1 has neither value available.
**Fix:** Either (a) reposition step 0.5's validity check to run after Path Setup (with a note that it also independently derives `plan_dir` early, ahead of its normal Phase-time derivation), or (b) split step 0.5 into "tokenize `--revise` now" (path-independent, stays before step 1) plus "validate phase/approved and halt-or-proceed" folded into Entry step 4's existing branch table (which already has status_path in scope) — matching where the conflicting `approved: true` → "already approved" halt row already lives.

## Verdict

GAPS_FOUND
One GAP: `--revise`'s step-0.5 placement precedes the path resolution its own validity check requires.
MILL_REVIEW_END
