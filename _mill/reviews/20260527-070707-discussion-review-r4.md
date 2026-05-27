# Review: Audit and clean up stale V2 references

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-27
```

## Findings

### [GAP] mill-setup line 31 stale _wiki.py listing not covered
**Section:** § Technical Context — "Affected SKILL.md files", mill-setup entry
**Issue:** `mill-setup/SKILL.md:31` reads `"${CLAUDE_PLUGIN_ROOT}/scripts/ contains _junction.py, _wiki.py, ..."` — this line contains `_wiki.` and the acceptance-criterion grep (`grep -r "_wiki\." plugins/mill/skills/`) will still match it after all five enumerated sub-changes (a)–(e) are applied.
**Fix:** Add `(f) remove _wiki.py from the Phase 3 scripts/ directory listing` to the mill-setup change list so the plan captures it.

### [NOTE] _wiki.WikiHealthError catch blocks not addressed in mill-go
**Section:** § Technical Context — "Affected SKILL.md files", mill-go entry
**Issue:** `mill-go/SKILL.md:116` and `:339` catch `_wiki.WikiHealthError` — stale references beyond the simple call replacement. Since `_client.health_check` returns a bool (no exception on failure), the try/except pattern must become a conditional, but the discussion doesn't state this explicitly.
**Fix:** Add one sentence clarifying the replacement form: `if not _client.health_check(hub_root): <error handling>` replacing both try/except blocks.

### [NOTE] "four changes" count for mill-setup is wrong
**Section:** § Technical Context — mill-setup description
**Issue:** The text says "four changes" but enumerates five sub-items (a)–(e).
**Fix:** Change "four changes" to "five changes" (or six, once the line-31 fix above is added).

## Verdict

GAPS_FOUND
One substantive gap: the mill-setup line-31 stale listing is not covered by the enumerated changes but will fail the acceptance-criterion grep.