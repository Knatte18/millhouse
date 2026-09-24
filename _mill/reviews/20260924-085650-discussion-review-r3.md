MILL_REVIEW_BEGIN
# Review: Prefix session names with repo short name; add MH:orch session

```yaml
duration_s: 191.8
verdict: APPROVE
reviewer_model: sonnet
reviewed_file: _mill/discussion.md
date: 2026-09-24
```

## Findings

### [NIT:consistency] Fallback warning excludes millpy-terminal.py without updated rationale
**Demoted-from:** BLOCKING
**Section:** Decisions > Fallback warning
**Issue:** The decision has `millpy-spawn.py` and `millpy-session-tasks.py` print the derived-short-name warning, with rationale "spawn and session-tasks are where the short name gets baked into session names." Scope and Decisions > "Where the prefix is built" both add `millpy-terminal.py` as a third caller that builds a session name (`<short>:<slug>`) via the same `session_prefix` helper, and Q&A justifies including it with "it collides across repos the same way" as spawn/session-tasks — the identical collision risk a wrong derived short name creates.
**Fix:** Either add `millpy-terminal.py` to the warning decision, or state an explicit reason it's exempt (e.g. ephemeral session vs. persisted tasks.json) and correct the rationale sentence so it doesn't claim spawn/session-tasks are the only two bake-in sites.

### [NIT:design] Recommended mill-setup option can fail its own validation regex
**Section:** Decisions > Explicit short_name in mill-setup
**Issue:** Option 1 (marked Recommended) is the value from `resolve_short_name`, validated against `^[A-Za-z0-9]{2,4}$`. `resolve_short_name`'s fallback is `repo_name[:2].upper()` only when `len(repo_name) >= 2`; for a 1-character repo name it returns `repo_name.upper()` (1 char), which fails the regex — the recommended option would immediately re-prompt.
**Fix:** Note the 1-character-repo-name edge case explicitly (accept it as a rare re-prompt, or special-case the derived-value validation).

## Verdict

APPROVE
One BLOCKING consistency gap between the Fallback warning rationale and the Scope/terminal decision.
_Note: 1 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 0._
MILL_REVIEW_END
