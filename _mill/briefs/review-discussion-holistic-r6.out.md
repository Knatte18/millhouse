MILL_REVIEW_BEGIN
# Review: mill-merge/merge-in: squash non-ff rejection, stale-worktree logic, parent-branch detection, conflict resolution

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed)
reviewed_file: _mill/discussion.md
date: 2026-08-12
```

## Findings

### [NIT:consistency] git-pr/SKILL.md:93 citation doesn't support `--exit-code`
**Section:** Decisions / 817-dead-parent-detection **Issue:** cites `git-pr/SKILL.md:93` as an established precedent for `git ls-remote --exit-code origin <branch>`, but that line actually reads `git ls-remote --heads origin <base>` — no `--exit-code` flag. **Fix:** drop the git-pr citation or correct it; `mill-resume/SKILL.md:222` (`git ls-remote --exit-code origin <branch_name>`) alone already establishes the pattern accurately.

## Verdict

APPROVE
All BLOCKING items from prior rounds verified resolved and source-grounded; one cosmetic citation mismatch only.
MILL_REVIEW_END
