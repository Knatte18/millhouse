MILL_REVIEW_BEGIN
# Review: mill-go2: fork-based dispatch reliability, shared-skill preloading, and catalog accuracy — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5
reviewed_file: plan/
date: 2026-08-21
```

## Findings

### [BLOCKING:consistency] Card 1's quoted "current value" omits the frontmatter's trailing sentence
**Location:** Batch 1 / Card 1
**Issue:** The actual `description:` field in `plugins/mill/skills/mill-go2/SKILL.md` line 3 ends with an additional sentence, "Invoked only by an explicit /mill-go2.", which Card 1's quoted "current value" does not include. Card 1's proposed replacement text also omits this sentence, so a literal find/replace either fails to match (no exact substring) or silently drops "Invoked only by an explicit /mill-go2." from the frontmatter — content the card explicitly says not to change ("anything else in the frontmatter").
**Fix:** Update Card 1's quoted current value and its replacement text to include the trailing "Invoked only by an explicit /mill-go2." sentence verbatim (or state explicitly that it is intentionally being dropped, if that is the intent).

### [BLOCKING:consistency] Card 2 prescribes an unprecedented `Skill(plugin:name)` call syntax
**Location:** Batch 1 / Card 2
**Issue:** The preload text asks for literal `Skill(mill:code-quality)` / `Skill(mill:markdown)` / `Skill(python:python-build)` etc. calls. No file in `plugins/mill/skills/` uses this parenthesized call form for the Skill tool (confirmed via repo-wide grep for `Skill(`) — the established conventions are the `@plugin:skill-name` reference form (`workflow/SKILL.md`'s Skill Invocation/Language Detection tables) and the prose form mill-go2/SKILL.md itself already uses one line below the Dispatch overrides section ("Load the `mill:mill-go-base` skill via the Skill tool, unconditionally and immediately, before any other action.").
**Fix:** Rewrite the preload bullets using the codebase's existing `@plugin:skill-name` or "Load the `plugin:skill-name` skill via the Skill tool" phrasing instead of inventing new call syntax.

## Verdict

REQUEST_CHANGES
Card 1's quoted current description text is inaccurate (drops a real sentence); Card 2 invents an unused Skill-call syntax.
MILL_REVIEW_END
