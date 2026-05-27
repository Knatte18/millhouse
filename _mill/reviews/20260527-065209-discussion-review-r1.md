# Review: Audit and clean up stale V2 references

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-27
```

## Findings

### [GAP] Acceptance check #3 won't catch millpy-spawn.py fix
**Section:** Testing
**Issue:** Check #3 grep pattern `"v2 shape\|v2's contract\|valid v2 task"` does not match the stale phrase in `millpy-spawn.py:238` ("v2's Home.md"). After all fixes are applied, check #3 passes even if millpy-spawn.py was never touched, silently leaving the stale comment.
**Fix:** Add `v2's Home` (or `v2's Home\.md`) as a fourth alternative in the check #3 pattern, or add a dedicated fourth check for millpy-spawn.py.

### [NOTE] Skill file count off by one
**Section:** Problem, Scope
**Issue:** Both state "12 SKILL.md files", but grep and the Technical Context's own enumeration (5 simple + 5 medium + 3 high) both yield 13 files.
**Fix:** Change "12" to "13" in both Problem and Scope headings; no impact on the Technical Context list which is already correct.

## Verdict

GAPS_FOUND
One verification check is blind to the millpy-spawn.py fix; pattern needs one more alternate.