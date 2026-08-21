MILL_REVIEW_BEGIN
# Review: mill-go: baseline-stage timeout/cold-build cost and finalize dirty-tree false positive

```yaml
duration_s: 162.5
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5
reviewed_file: _mill/discussion.md
date: 2026-08-21
```

## Findings

### [NIT:consistency] "Sole precedent" claim for millpy-bg pattern is false
**Demoted-from:** BLOCKING
**Section:** `baseline-dispatch-background` Decision, "Precedent (corrected)" bullet.
**Issue:** The discussion asserts mill-start/SKILL.md's Subprocess/psmux branch is "the actual, sole precedent for the background-dispatch-and-poll pattern in this codebase." Grep-verified false: `plugins/mill/skills/mill-plan/SKILL.md` independently implements the identical `millpy-bg.py --slug ... -- ...` / poll `[mill-bg] EXIT` / `grep '^{' <log-path>` pattern at least twice (plan-review dispatch ~line 447-457, plan-validator-fix re-run ~line 332), including a pwd/cwd-guard step ("Before invoking millpy-bg: verify pwd...") this discussion's own description of the pattern to replicate never mentions.
**Fix:** Correct the precedent claim to acknowledge mill-plan/SKILL.md as a second, more elaborate precedent, and state explicitly whether the pwd/cwd-guard convention should also be replicated for the baseline pre-flight dispatch (a plan writer copying only the mill-start version will silently omit it).

### [NIT:scope] No verification plan for the SKILL.md dispatch-mechanism edit
**Section:** Testing.
**Issue:** All three named test additions cover the two code fixes; the third in-scope item (switching "0.5"/"0.6" from foreground Bash to `millpy-bg` background+poll) has no stated verification approach at all.
**Fix:** Add a line noting how the SKILL.md prose/mechanism change will be checked (e.g. manual dry-run on next real mill-go baseline pre-flight, or explicitly state prose-only changes are unverified by design).

## Verdict

APPROVE
Fix the false "sole precedent" claim before plan writing proceeds.
_Note: 1 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 0._
MILL_REVIEW_END
