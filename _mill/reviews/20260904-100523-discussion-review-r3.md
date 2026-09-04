MILL_REVIEW_BEGIN
# Review: mill-plan: entry-gate, timeline, and script-portability bugs

```yaml
duration_s: 248.0
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5 (Sonnet 5)
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

### [BLOCKING:design] #938 drift-check site list omits Step 1.5's subprocess-mode validator-fix retry
**Section:** Decisions > discussion-drift-guard-938 **Issue:** The decision enumerates exactly three LLM-dispatch sites needing the drift check (step 2 initial dispatch, step 3.5 ERROR-only retry, Agent-mode "prepare-envelope handling" validator-fix re-invocation ~line 433-438), but `mill-plan/SKILL.md`'s Step 1.5 has its own subprocess/psmux-mode validator-fix retry (`millpy-bg` re-run with slug `plan-validator-fix`, line ~351) that is structurally identical to the Agent-mode site the decision does name — if that second-pass validation succeeds, the same CLI call proceeds to actually dispatch the LLM, consuming a real round without ever being checked. **Fix:** Add this fourth site (Step 1.5's `plan-validator-fix` re-run) to the enumerated drift-check list, mirroring the Agent-mode validator-fix re-invocation coverage.

### [NIT:consistency] Testing section's "no unit-test suite exercises SKILL.md prose" claim is false
**Demoted-from:** BLOCKING
**Section:** Testing **Issue:** The claim "these are markdown instruction files, not executable code" contradicts actual repo state: `plugins/mill/unit_tests/test-skill-helper-drift.py` scans mill-plan/mill-start `SKILL.md` for `_<module>.<fn>(` helper references and asserts each resolves to a real shipped function; `test-brief-commit.py` asserts exact commit-message substrings and a minimum `_mill/briefs/` occurrence count in `mill-start/SKILL.md`; `test-guards.py` and `test-mill-go-variants.py` also grep both files for specific patterns/anchors. **Fix:** Correct the Testing section to name these existing prose-scanning tests as part of the verification strategy for the #938/#919/#939 edits (new helper calls must still resolve; the #919 port must not break the brief-commit count/anchor checks), rather than claiming no such coverage exists.

## Verdict

REQUEST_CHANGES
Drift-check site enumeration has a real gap and the Testing section misstates existing SKILL.md-scanning test coverage.
_Note: 1 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 1._
MILL_REVIEW_END
