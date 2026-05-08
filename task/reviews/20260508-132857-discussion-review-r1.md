Verified source files. Now writing the review.

# Review: 32 (A) — Bug-fix batch 2

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: task/discussion.md
date: 2026-05-08
```

## Findings

### [GAP] Scope omits SKILL.md callers for #202
**Section:** `## Scope — In:`
**Issue:** `mill-autofix/SKILL.md` and `mill-ghissues-to-tasks/SKILL.md` are not listed as in-scope files even though the Decision block says the two in-tree callers MUST pass `git_root` explicitly, and Technical Context gives exact line numbers (45, 377 / 27, 127). A plan writer reading the Scope list alone would omit these files and ship an incomplete fix — the cwd bug would survive in the callers.
**Fix:** Add both SKILL.md files to the Scope **In:** block, referencing the Decision's "MUST" requirement as the reason.

### [NOTE] Error message text will be stale after Deletes fix
**Section:** `## Scope / ### deletes-counted-in-all-files-touched`
**Issue:** `_plan_validate.py:688–695` error message reads "not in any card's Edits: or Creates:" — after the fix unions `_parse_deletes_only`, this string is outdated.
**Fix:** Note in the scope entry or decision that the error message string should also be updated to include "Deletes:".

## Verdict

GAPS_FOUND  
The SKILL.md callers for #202 are missing from Scope and would be silently skipped by a plan writer.