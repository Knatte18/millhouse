Neither `_review_common.py` nor `_reviewers.py` imports `_agent_dispatch`, so placing the directive builder in `_agent_dispatch.py` and importing `_review_common` there would not create a cycle. The discussion appropriately hedges ("mill-plan may choose the exact location"). No blocking concern.

I now have a complete, source-grounded picture. Let me compose the review.

The main genuine gap: both per-batch brief templates have a `## Tools` section that lists available tools as `Read, Edit, Write, Bash, Grep, Glob` (no Skill) and a Banned line — the injected "load these skills" directive will contradict the brief's own self-description of available tools. The session is dispatched WITH Skill, so functionally it works, but the brief text would tell a weak Haiku reader that Skill is not available, undermining the very directive. Discussion does not call out updating the Tools section.

MILL_REVIEW_BEGIN
# Review: Fix batch-name sanitization (colon/slash on Windows) and implementer skill loading

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-15
```

## Findings

### [GAP] Brief Tools sections omit Skill, contradict injection
**Section:** Scope (skill-injection) / Technical context (templates)
**Issue:** Both `implementer-brief.md` (line 98) and `fixer-batch-brief.md` (line 90) `## Tools` sections state `Available: Read, Edit, Write, Bash, Grep, Glob` (no `Skill`); the injected non-optional "load these skills" directive contradicts the brief's own tool list, which a weak Haiku reader may obey over the directive — re-creating #483.
**Fix:** Add `Skill` to the `## Tools` "Available" line in both per-batch brief templates (the session IS dispatched with `Skill` per `_llm_claude.py` line 516 / `millpy-claude-sub.py` line 41), so the brief is internally consistent.

### [NOTE] LANGUAGE_SKILLS token silently no-ops if template not updated
**Section:** Technical context (_render.render)
**Issue:** `_render.render` raises `KeyError` only for template tokens missing from `values`; a `values` key with no matching template token is silently ignored — so if `<LANGUAGE_SKILLS>` is added to only one of the two templates (or misspelled), injection silently does nothing with no error.
**Fix:** Have the injection unit tests assert the rendered directive text appears in BOTH the implementer and fixer briefs (the Testing section already proposes this) and document the token in each template's leading comment token list.

### [NOTE] Directive builder home vs import direction
**Section:** Technical context (_review_common reuse)
**Issue:** Placing `language_skills_directive` in `_agent_dispatch.py` makes it import `_review_common`, which transitively pulls `_render`, `_reviewers`, `_config`, etc. into the previously dependency-free dispatch module.
**Fix:** Confirmed no import cycle exists today (no `_review_common`/`_reviewers` import of `_agent_dispatch`); acceptable as-is, but the plan should state the chosen home explicitly rather than leaving it to mill-plan, since it widens `_agent_dispatch`'s dependency surface.

## Verdict

GAPS_FOUND
Brief Tools sections omit Skill and contradict the injected load-skills directive; resolve before planning.
MILL_REVIEW_END
