# Review: 3 (A) — codeguide improvements: sibling placement + --branch flag

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: discussion.md
date: 2026-05-05
```

## Findings

### [GAP] git ls-remote exit-code semantics are wrong
**Section:** Technical context → New step 4 / Orphan branch creation decision
**Issue:** The discussion states "`exit 0` (branch exists) → clone; `non-zero` (branch absent) → orphan." This is incorrect: `git ls-remote --heads <url> <branch>` exits **0 whether or not the branch exists** (as long as the remote is reachable). A non-zero exit means a connection/auth error, not a missing branch. A plan writer following these instructions would: always clone when the remote is reachable (because `ls-remote` always exits 0 on success), and silently treat auth/network failures as "branch absent" and spin up a local-only orphan.
**Fix:** Restate the check as: exit 0 + non-empty output → branch exists (clone); exit 0 + empty output → branch absent (orphan); non-zero exit → error, stop with message.

## Verdict

GAPS_FOUND  
One technical error in the `git ls-remote` exit-code logic would produce incorrect plan instructions.