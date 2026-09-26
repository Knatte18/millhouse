MILL_REVIEW_BEGIN
# Review: Unify ask-parent into ask-thread: ask any named session, default parent

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-09-26
```

## Findings

### [BLOCKING:design] ListAgents loading mechanism unspecified
**Section:** Reply protocol / Technical context (deferred-tool line).
**Issue:** `--reply-to` requires reading `ListAgents`' self-name line, but Technical context only says "the skill loads `SendMessage`/`TaskStop` via `ToolSearch` (`select:SendMessage,TaskStop`) when their schemas are not loaded" — `ListAgents` is named in the same sentence's "deferred or top-level" grouping but excluded from the stated `ToolSearch` call. No existing skill invokes `ListAgents` (only two doc mentions in `harness-tool-contracts.md`), so there's no precedent to fall back on.
**Fix:** State whether `ListAgents` needs its own `ToolSearch(select:ListAgents)` call before use, or is always top-level/available without one.

## Verdict

REQUEST_CHANGES
One BLOCKING: ListAgents' tool-loading path for --reply-to is left unspecified.
MILL_REVIEW_END
