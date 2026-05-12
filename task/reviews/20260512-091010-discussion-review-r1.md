I have verified the key technical claims. Let me write the review.

# Review: 40 (B) — mill-finalize: lift PR decision out of mill-merge

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: task/discussion.md
date: 2026-05-12
```

## Findings

### [GAP] test-mill-merge-inplace.py has no PR-path tests to remove
**Section:** Testing — "mill-merge phase gate (update existing test)"
**Issue:** The discussion says to "Remove PR-path creation tests from mill-merge" in `test-mill-merge-inplace.py`. Source-verified: the file contains only four `_inplace` module signature smoke tests (`is_inplace`, `prompt_stale_worktree`); there are no PR-path tests. The "remove" instruction is a false premise that will confuse the plan writer.
**Fix:** Drop the "Remove PR-path tests" instruction; confirm whether the phase-gate fallback (absent status.md → Home.md) is backed by any Python helper to test, or mark the unit-test entry as "new tests only, no removals."

### [NOTE] git.parent-branch is also kebab-case but not in rename scope
**Section:** Technical context — Config keys affected by rename
**Issue:** The rationale states "only the `git:` block used kebab-case," but source-verified: `git-pr/SKILL.md` Step 2 reads `git.parent-branch` — also kebab-case in the `git:` block — and it is not listed as a rename target.
**Fix:** Clarify that `git.parent-branch` is intentionally deferred (not this task's scope), so the stated rationale matches the actual scope.

## Verdict

GAPS_FOUND  
One false premise in the test specification needs correction before planning proceeds.