MILL_REVIEW_BEGIN
# Review: Deactivate codeguide integration in millhouse

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-09-23
```

## Findings

### [BLOCKING:scope] mill-merge-in/SKILL.md has 3 uncovered codeguide mentions
**Section:** Scope > In / "mill-merge-in/SKILL.md: delete Step 5" Decision
**Issue:** The file's own frontmatter `description:` ("...verify + codeguide-update") (L3), its intro paragraph ("...and runs codeguide-update when applicable.") (L9), and Step 1's "No checkpoint, no verify, no codeguide-update." (L56) all describe the deleted call site but are not in the enumerated edit list — only the Step 5.5/"## No-op guarantee" occurrences (L210, L214, L217, L258) are addressed.
**Fix:** Add these 3 spots to the mill-merge-in edit list; otherwise the task's own final verification grep (`grep -rni codeguide plugins/mill/ CLAUDE.md`) will surface unexpected hits in a file not on the documented allowlist.

### [NIT:scope] `resolve_for_codeguide` line range excludes its own body
**Section:** Decisions > "Delete `_parent_branch.resolve_for_codeguide` and its tests"
**Issue:** Cited range "~233-243" covers only the def/docstring; the actual `try/except`/`return` body runs to L248 (confirmed by reading `_parent_branch.py`).
**Fix:** Widen the approximate range or drop it, relying on the correct "whole function including docstring" prose instruction already given.

## Verdict

REQUEST_CHANGES
One BLOCKING: mill-merge-in/SKILL.md's own description/intro/Step-1 codeguide mentions are unaddressed.
MILL_REVIEW_END
