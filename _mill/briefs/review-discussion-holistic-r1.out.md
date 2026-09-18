MILL_REVIEW_BEGIN
# Review: mill-plan: entry-gate wait for upstream mill-start misses discussion-gap-fix-r{N} and races the pinning commit

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: /home/knatte/Code/millhouse/wts/mill-plan-entry-gate-wait-trigger-gaps/_mill/discussion.md
date: 2026-09-18
```

## Findings

### [BLOCKING:consistency] Testing §'s "no subprocess execution" premise is false
**Section:** ## Testing, "New (optional, integration-flavored...)" bullet
**Issue:** The bullet claims the end-to-end execution test is "not required if `test-phase-wait.py`'s existing convention is purely string-content assertions with no subprocess execution." `plugins/mill/unit_tests/test-phase-wait.py` Case 13 (lines 115-146) already writes a real CRLF file and runs `subprocess.run(["bash", "-c", crlf_cmd], ...)` end-to-end — the premise this escape hatch relies on is contradicted by the file it cites.
**Fix:** Since this file's own established convention already includes real bash execution for exactly this kind of race/timing behavior, state the end-to-end dirty-then-clean execution test as required, not optional, mirroring Case 13's pattern.

### [NIT:consistency] "interactive/auto gap-resolution path" mischaracterizes step 5
**Section:** ## Problem, item 1
**Issue:** `discussion-gap-fix-r{N}` is written only by mill-start's plain-interactive step 5 (`mill-start/SKILL.md:406`). Under `--auto`/`--orch`, step 5 is explicitly skipped in its entirety (`mill-start/SKILL.md:390`) and replaced by "Phase: Discussion Review — `--auto` changes", whose REQUEST_CHANGES branch (lines 46, 51-57) never calls `_status.append_phase` with `discussion-gap-fix-r{N}` — phase stays `discussing` through that loop. Calling step 5 "the interactive/auto gap-resolution path" overstates when this phase value can actually appear.
**Fix:** Reword to "the plain-interactive gap-resolution path" — does not change the trigger-widening fix itself, which remains correct regardless.

## Verdict

REQUEST_CHANGES
Testing section's subprocess-execution premise is factually wrong and understates required test coverage.
MILL_REVIEW_END
