MILL_REVIEW_BEGIN
# Review: mill-go2: opt-in skill scaffold cloned from mill-go (no fork yet)

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5 (self-assessed; cannot confirm with certainty)
reviewed_file: /home/knatte/Code/millhouse/wts/mill-go2-scaffold/_mill/discussion.md
date: 2026-08-11
```

## Findings

### [NIT:scope] Generic orchestrator-name lists outside the cross-reference enumeration
**Section:** Technical context > Cross-references that must be repointed
**Issue:** `plugins/mill/skills/cli/SKILL.md:40` and `plugins/mill/skills/conversation/SKILL.md:74` list `mill-go` among orchestrators subject to a Bash-convention rule (resolved-`${CLAUDE_PLUGIN_ROOT}`-verbatim, Bash-call scope) without mentioning mill-go2; the discussion's repoint enumeration is scoped only to literal `mill-go/SKILL.md` path citations, so these two generic name-lists fall outside it and go stale once mill-go2 exists.
**Fix:** Note in-plan whether these two prose lists should gain "mill-go2" or are intentionally left as-is (the underlying rule is already enforced by the base's own Step 0, so this is cosmetic, not a behavior gap).

## Verdict

APPROVE
Verified line counts, cross-references, and code citations against source; all checked out accurate.
MILL_REVIEW_END
