MILL_REVIEW_BEGIN
# Review: code-comments skill: prohibit enumerating current consumers/writers of a shared resource

```yaml
duration_s: 93.0
verdict: REQUEST_CHANGES
reviewer_model: sonnet
reviewer_self_id: claude-sonnet-4.5
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

### [BLOCKING:design] Out-of-scope rationale rests on a false premise for two files
**Section:** Scope > Out
**Issue:** The bullet claims "Those `## Prohibited patterns` sections carry language syntax/mechanics rules only" for all three named files (golang-comments, csharp-comments, python-comments). Read verification: `plugins/csharp/skills/csharp-comments/SKILL.md` and `plugins/python/skills/python-comments/SKILL.md` contain no `## Prohibited patterns` section at all — only `plugins/golang/skills/golang-comments/SKILL.md` has one (confirmed at line 220, single bullet as described).
**Fix:** Correct the claim to state that csharp-comments and python-comments have no `Prohibited patterns` section to begin with (rather than one that is syntax-only); the exclusion decision itself is unaffected, but the stated evidence is fabricated for 2 of 3 files.

## Verdict

REQUEST_CHANGES
Out-of-scope rationale misdescribes source content for two of three named per-language skill files.
MILL_REVIEW_END
