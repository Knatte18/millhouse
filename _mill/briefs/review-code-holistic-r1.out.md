MILL_REVIEW_BEGIN
# Review: Migrate mill's generic skills to the shared scribe plugin — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-09-29
```

## Findings

### [BLOCKING:scope] Bare `{lang}-build` references left in git-commit and git-pr
**Location:** `plugins/mill/skills/git-commit/SKILL.md:17`, `plugins/mill/skills/git-pr/SKILL.md:136`
**Issue:** Both lines still delegate to "the matching `{lang}-build` skill" unqualified, contradicting Shared Decision `qualified-skill-names` ("every mill-owned reference to a generic or language skill uses the plugin-qualified name").
Card 7 fixed only git-commit line 19, and the card 11 sweeps grep only `mill:<name>` and `<lang>:<lang>-` forms, so neither bare reference was caught.
`git-pr/SKILL.md` appears in no batch's `Edits:` list.
**Fix:** Change both to `scribe:{lang}-build` (add `git-pr/SKILL.md` to the plan's Edits first), and widen the sweep to cover bare `{lang}-build`.

## Verdict

REQUEST_CHANGES
Two unqualified `{lang}-build` references (git-commit, git-pr) violate the qualified-skill-names decision; everything else verified aligns with the plan.
MILL_REVIEW_END
