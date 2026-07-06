MILL_REVIEW_BEGIN
# Review: Fix nested-hub-layout path resolution bugs across scope violations and review CLIs

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-06
```

## Findings

### [GAP] parse_verify_field contract for malformed verify field
**Section:** Decisions → Verify-cwd explicit field (#604)
**Issue:** The field defines accepted `cwd` values (`hub`/`git_root`) and the absent-default, but leaves undefined what `parse_verify_field` does with an unrecognized `cwd` value (typo like `cwd: worktree`) or a mapping missing the `command` key — a plan writer cannot implement the helper's error path without guessing (silent default vs raise).
**Fix:** State the contract: on invalid `cwd` enum value or mapping missing `command`, fail loud (raise / return an error the caller surfaces) rather than silently defaulting, and note which layer reports it.

### [NOTE] Module-wide verify not covered by _plan_validate command checks
**Section:** Decisions → Verify-cwd explicit field; Technical context (`_plan_validate.py`)
**Issue:** The decision extends the `cwd` field to module-wide (overview) verify, but `_check_verify_not_isolated` / `_check_verify_full_suite` iterate `batch_files` only — so an overview-level verify authored without `PYTHONPATH=` (or in mapping form) is never validated. Pre-existing, but the new mapping form widens the surface.
**Fix:** Either note this as an accepted pre-existing limitation, or extend the two validators to also check the overview frontmatter's extracted `command`.

## Verdict

GAPS_FOUND
One underspecified failure mode (invalid `cwd`/malformed mapping) needs an explicit contract before plan writing.
MILL_REVIEW_END