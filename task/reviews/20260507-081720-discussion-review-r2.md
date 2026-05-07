# Review: 29 (A) — mill-merge-in: delegate konflikter og verify-feil til sub-agent

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax
reviewed_file: task/discussion.md
date: 2026-05-07
```

## Findings

### [GAP] Verify output token: path vs content contradicts
**Section:** `verify-fail-context` decision + Technical context > Verify output capture
**Issue:** Two contradictory claims — "Passes the path as a token to the verify-fix brief" (path token) vs "The content is embedded in the brief" (content token). These produce materially different brief templates and CLI implementations; the deletion timing is also only safe under one interpretation (content: delete anytime; path: must delete after `run()` returns).
**Fix:** Specify which is intended — either the CLI reads the file and passes content as the token value (`tokens["VERIFY_OUTPUT"] = file.read_text()`), or it passes the path and the sub-agent reads it via `Read`. Remove the contradicting statement.

### [NOTE] SKILL.md update omits stuck-path behavior
**Section:** Scope > In > Updated mill-merge-in/SKILL.md
**Issue:** Scope only says "Steps 3 and 4 now call the new CLI." Doesn't state what the SKILL does on a `{"status":"stuck"}` verdict from conflicts mode — the Out section implies `git reset --hard checkpoint`, but it's unclear whether this is pre-existing behavior or needs to be added.
**Fix:** Add one sentence: whether the checkpoint rollback on stuck is pre-existing (just preserve it) or a new step to add in the SKILL.md update.

## Verdict

GAPS_FOUND  
One GAP blocks the plan: verify output token ambiguity produces different brief templates and CLI code.