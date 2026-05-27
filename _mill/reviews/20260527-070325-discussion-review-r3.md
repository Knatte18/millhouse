# Review: Audit and clean up stale V2 references

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-27
```

## Findings

### [GAP] Cheatsheet annotates health_check as "triggers auto-start"
**Section:** Technical context — V3 wiki client API cheatsheet
**Issue:** `_client.health_check(wiki_path) # -> bool; triggers auto-start` is factually wrong. Source-confirmed: `health_check` (lines 396–422 of `wiki/_client.py`) reads `.wiki-daemon.json` directly and returns `False` if absent — it never calls `_ensure_daemon` and never spawns the daemon. The `mill-setup-phase6-deletion` Decision correctly rejects it for this reason, but the cheatsheet still carries the wrong annotation, creating a contradiction a plan writer will see before reaching the Decision section.
**Fix:** Change the cheatsheet comment to `# -> bool; does NOT auto-start (probe only)` so the cheatsheet matches both the source and the Decision's rationale.

### [NOTE] Q&A entry Q3 contradicts the Decision and is factually wrong
**Section:** Q&A log, third entry
**Issue:** The answer says "Add a `_client.health_check(wiki_path)` call in Phase 5 post-clone verification." The Decision rejects `health_check` as a startup trigger (correct per source) and places a `list_tasks_brief` call in Phase 6a's position — with no Phase 5 modification. The Q&A entry is stale and uses the wrong function.
**Fix:** Strike or annotate Q3 as superseded, or append "Superseded by mill-setup-phase6-deletion Decision." to avoid an implementer following the Q&A over the Decision.

## Verdict

GAPS_FOUND
One confirmed factual error in Technical Context cheatsheet contradicts the Decision; the Q&A log echoes the same wrong claim.