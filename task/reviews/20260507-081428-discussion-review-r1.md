# Review: 29 (A) — mill-merge-in: delegate konflikter og verify-feil til sub-agent

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax
reviewed_file: task/discussion.md
date: 2026-05-07
```

## Findings

### [GAP] Verify-fix round loop ownership unspecified
**Section:** Decisions › verify-fix-rounds-config / Scope
**Issue:** `merge.verify_fix_rounds` is defined but the discussion doesn't say whether the round loop runs inside the CLI (N calls to `_implementer_sonnet.run`) or is SKILL-driven (SKILL calls the CLI once per round and checks JSON verdict). The SKILL update is in scope but describes no loop logic.
**Fix:** State explicitly: the CLI is single-shot; the SKILL calls it up to `merge.verify_fix_rounds` times, halting on `success` or after N rounds exhausted.

### [GAP] Conflict sub-agent commit boundary unspecified
**Section:** Decisions › conflict-context-to-sub-agent / Technical context › Conflict detection
**Issue:** After the sub-agent stages resolved files with `git add`, it's unspecified whether the sub-agent also runs `git commit`/`git merge --continue` or whether the SKILL step issues that command after receiving `{"status":"success"}`. Affects the conflict brief template and the SKILL step that follows.
**Fix:** Specify whether the conflict sub-agent is responsible for completing the merge commit, or whether the SKILL runs `git merge --continue` after the sub-agent returns success.

### [NOTE] Temp file cleanup ownership ambiguous
**Section:** Technical context › Verify output capture
**Issue:** "Cleaned up by the Builder after the sub-agent returns" is ambiguous between the CLI deleting on exit and a named SKILL.md step performing deletion.
**Fix:** Clarify in the plan: the CLI deletes the temp file before returning (or a specific SKILL step does it and is named).

## Verdict

GAPS_FOUND
Two GAPs block unambiguous plan writing: verify-fix round loop owner and conflict commit boundary.