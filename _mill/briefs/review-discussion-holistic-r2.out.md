MILL_REVIEW_BEGIN
# Review: mill-plan: planning-process documentation/procedure gaps

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5 (Sonnet 5)
reviewed_file: /home/knatte/Code/millhouse/wts/mill-plan-planning-process-documentation-gaps/_mill/discussion.md
date: 2026-09-19
```

## Findings

### [BLOCKING:consistency] "verbatim" blockquote copy mismatches Agent-mode's own phrasing
**Section:** Decision `entry-blocked-reentry-max-rounds-gap`
**Issue:** The decision says to add the blockquote "verbatim wording matching lines 479/530" to the two Agent-mode dispatch sites (~430, ~515). Read: lines 479/530 say "append `--max-rounds <local_max_review_rounds>` to **the inner `millpy-review-plan.py` invocation below**" — subprocess/psmux-specific phrasing. The sibling live-operator-override blockquote already present at those same Agent-mode sites (line 430) instead says "append ... to `<args>`", because Agent-mode has no "inner invocation below" — only `<args>` fed to the shared dispatch pattern.
**Fix:** Decision text should say "adapt" (matching the sibling `<args>` blockquote's phrasing at the same site), not "verbatim wording matching lines 479/530" — otherwise the plan will land prose referencing a subprocess invocation that doesn't exist in the Agent-mode branch.

### [BLOCKING:design] `--revise` on a max-rounds-exhausted block bypasses `local_max_review_rounds` entirely
**Section:** Decisions `revise-from-blocked-max-rounds-every-round` / `entry-blocked-reentry-max-rounds-gap`; Technical Context's two-flows bullet
**Issue:** `revise_from_blocked`'s `--revise` pre-check (SKILL.md line ~60) fires on `phase == "blocked"` for **any** `blocked_reason`, including `"max-rounds exhausted..."`, and takes precedence over the Entry-blocked-reentry table row — so an operator can reach a max-rounds-exhausted block via `--revise` instead of a bare re-invocation. In that case `blocked_resume_round` (≈ `max_review_rounds + 1`, since the blocking round's review already ran) is used with no `local_max_review_rounds`-style extension. The fix as scoped only patches the CLI's `round_n > max_rounds` guard (via per-round `--max-rounds <round>`) — it does not touch the orchestrator-level `round >= max_review_rounds` comparisons (Convergence gate, 4a/4b/4c, step 6), which would immediately be satisfied on the very first resumed round, reproducing the exact "implicit-approve/halt with no real review" bug `local_max_review_rounds` exists to prevent for the bare-reentry path.
**Fix:** Either state explicitly that this overlap case is a known, accepted limitation (out of scope), or extend `blocked_resume_round`'s handling so a `revise_from_blocked` resume on a `"max-rounds exhausted"` reason also gets an extended round-cap budget for the orchestrator-level comparisons, not just the CLI flag.

## Verdict

REQUEST_CHANGES
Two BLOCKING findings: a phrasing/consistency defect in one fix decision and an unaddressed cross-flow interaction gap.
MILL_REVIEW_END
