MILL_REVIEW_BEGIN
# Review: mill-plan SKILL.md: entry, phase-gate, finalize, and re-entry path gaps

```yaml
duration_s: 200.0
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-08-13
```

## Findings

### [NIT:consistency] Q&A log contradicts the revised `verify-full-suite` Decision
**Demoted-from:** BLOCKING
**Section:** Q&A log, "How many fix-table rows are actually missing..." entry (vs. `### Step 1.5 fix table` Decision)
**Issue:** The Decision text (revised after discussion-review round 1) formalizes the "cross-cutting helper" carve-out as a `--skip-check verify-full-suite` escape hatch and explicitly keeps it. The Q&A log entry answering the same question still says the opposite: "Remove the 'cross-cutting helper MAY use unbounded run-all.py' carve-out since the validator rejects it unconditionally with no skip-check escape hatch" — the exact premise the Decision says is false.
**Fix:** Update the Q&A log's answer/rationale to match the current Decision (keep + formalize the carve-out via `--skip-check`), so a plan writer reading only the Q&A log doesn't implement the rejected, premise-false version.

## Verdict

APPROVE
Stale Q&A entry contradicts the revised Step 1.5 Decision on the `verify-full-suite` carve-out.
_Note: 1 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 0._
MILL_REVIEW_END
