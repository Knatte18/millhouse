# Review: Green the unit test suite on wiki-v3-adoption so it can merge to main

```yaml
verdict: APPROVE
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-25
```

## Findings

### [NOTE] Scope says "one production-code change" but env var is a second
**Section:** Scope (In) / Idle-timeout plumbing
**Issue:** "One production-code change" describes only `on_stop`, but the Idle-timeout plumbing section establishes that `_server.py __main__` needs a `WIKI_DAEMON_IDLE_TIMEOUT` env-var read — verified: `_client.py:434` never passes `idle_timeout` to the subprocess, and `_server.py:334` reads only `sys.argv[2]`.
**Fix:** Acknowledge the env-var addition as a second (minimal) production-code change, or fold it into the scope bullet to avoid planner confusion.

## Verdict

APPROVE
All four root causes have concrete, grounded decisions; one minor scope-statement undercount does not block planning.