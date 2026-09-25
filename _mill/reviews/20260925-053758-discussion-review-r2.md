MILL_REVIEW_BEGIN
# Review: Ask the parent session when stuck (parent_thread)

```yaml
duration_s: 277.7
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-09-25
```

## Findings

### [BLOCKING:design] plan-cap ignores mill-plan's own live-override mechanisms
**Section:** Decisions > converted-sites (`plan-cap` row).
**Issue:** `mill-plan/SKILL.md` already has `Live operator-raised round-cap override` (binds `operator_max_review_rounds`, threads `--max-rounds <N>` through every prepare/finalize dispatch site in Phase: Plan Review, including the Step 3.5 retry) and `Live operator waiver of step 6` (flips `approved: true` via direct Edit, commits with `"...(operator waived remaining BLOCKINGs at round cap)"`, proceeds to Handoff) — both built for exactly this in-session approve/extend-cap need. The row instead specs a fresh direct-Edit `approve` with a different commit-message convention, and justifies `retry`'s `--max-rounds <max+1>` as mirroring "the existing non-progress extension round" — that phrase and flag shape belong to mill-start (`Auto mode non-progress-extension round`), not mill-plan; mill-plan's own analogous mechanism binds a session-local `operator_max_review_rounds` and has its own precedence rules against `local_max_review_rounds`.
**Fix:** Point `plan-cap`'s `approve`/`retry` at mill-plan's own `Live operator waiver of step 6` / `Live operator-raised round-cap override` procedures instead of re-describing parallel logic, and drop the mill-start-mechanism citation.

## Verdict

REQUEST_CHANGES
plan-cap's approve/retry duplicate mill-plan's own existing live-override mechanisms instead of reusing them.
MILL_REVIEW_END
