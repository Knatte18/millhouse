MILL_REVIEW_BEGIN
# Review: mill-plan SKILL.md: entry, phase-gate, finalize, and re-entry path gaps

```yaml
duration_s: 363.0
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-08-13
```

## Findings

### [BLOCKING:design] `--max-rounds` CLI dispatch in blocked-row is a no-op under Agent-mode
**Section:** Decision "Max-rounds block: add a `blocked` re-entry row (#832)" — round-budget interaction clause.
**Issue:** The clause claims passing `--max-rounds <local_max_review_rounds>` on "every CLI dispatch" "mirrors the exact per-invocation-override pattern mill-start's own `--auto` non-progress-extension already uses." Verified false for mill-plan's primary Agent-mode path: `_review_discussion.py::prepare()` accepts `max_rounds` and enforces `round_n > effective_max` (the mechanism mill-start's precedent actually relies on), but `_review_plan.py::prepare()` (called from `millpy-review-plan.py --stage prepare`, lines 231-235) has no `max_rounds` parameter and performs no round-cap check anywhere in either its batch or holistic branch; `args.max_rounds` is threaded only into the `--stage full` `run()` call (millpy-review-plan.py:345), never into `--stage prepare`. So passing `--max-rounds` on Agent-mode dispatches during blocked-row resume is silently ignored by the CLI — it does real work only for the subprocess/psmux `--stage full` branch, where `run()` genuinely compares `round_n` against `max_rounds` (lines 805-806, 990-992).
**Fix:** Scope the `--max-rounds <local_max_review_rounds>` CLI-dispatch requirement to the subprocess/psmux branch only; state plainly that Agent-mode's round cap is enforced solely by the orchestrator's own `local_max_review_rounds` comparisons in mill-plan/SKILL.md prose, with no CLI-side counterpart, and drop the "direct precedent" claim as applying to Agent-mode.

### [NIT:consistency] Blocked-row writes `plan-review-r{N}` before round N runs, duplicating the timeline entry
**Demoted-from:** BLOCKING
**Section:** Decision "Max-rounds block: add a `blocked` re-entry row (#832)" — "Call `_status.append_phase(status_path, f'plan-review-r{N}', ts)` ... and fall through into the Plan Review loop starting at round `N`."
**Issue:** Everywhere else in mill-plan/SKILL.md, `plan-review-r{N}` is appended only *after* round N produces a verdict (steps 4a and 4d). The blocked-row instead writes this exact phase string *before* round N is dispatched, purely to auto-clear `blocked_reason`. `_status.append_phase` (`_status.py:428-499`) always appends a fresh timeline row — it never dedupes against an existing identical entry — so once round N actually completes and 4a/4d append `plan-review-r{N}` again, `status.md`'s Timeline carries two identical `plan-review-rN <timestamp>` rows with different timestamps, misrepresenting the audit trail (looks like round N happened twice).
**Fix:** Use a distinct marker for the resume step (e.g. re-append `"planning"`, which the Entry table's re-entry row already matches generically) instead of pre-writing the round-N-specific phase string; reserve `plan-review-r{N}` for the round's actual completion as done elsewhere.

## Verdict

REQUEST_CHANGES
Blocked-row's `--max-rounds` precedent claim is unverified against `_review_plan.py` and its status-write duplicates timeline entries.
_Note: 1 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 1._
MILL_REVIEW_END
