MILL_REVIEW_BEGIN
# Review: mill-merge-in/mill-finalize/codeguide-update: cleanup-ordering and path-resolution bugs — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5 (self-assessed)
reviewed_file: plan/
date: 2026-09-04
```

## Findings

### [BLOCKING:design] Step 5.5 unrestricted porcelain check can fail with nothing staged
**Location:** Batch 1 / Card 3 (mill-merge-in Step 5.5).
**Issue:** The rewrite gates `git commit` on a repo-wide `git status --porcelain` (no pathspec) being non-empty, but only `git add _mill/briefs/` runs beforehand — codeguide docs are staged earlier in Step 5, not here. The card's safety argument ("every earlier step already commits or rolls back its own changes") only covers dirt introduced by this skill's own steps; it does not rule out pre-existing unrelated dirty/untracked state already present in the worktree when mill-merge-in is invoked. If porcelain is non-empty solely due to such foreign state, `git commit` finds nothing staged and fails, and the card specifies no handling for that outcome.
**Fix:** Either re-scope the check to the two known-legitimate paths (briefs + whatever codeguide-update touches) or explicitly gate the commit on `git diff --cached --quiet` (staged-only) rather than unscoped `git status --porcelain`, and state what happens on an empty-staged/non-empty-porcelain mismatch.

### [BLOCKING:consistency] Imported millpy-bg halt-guard contradicts Step 3.5's "never blocks or fails the merge" contract
**Location:** Batch 1 / Card 4 (mill-merge-in Step 3.5).
**Issue:** Card 4 imports the `mill-go-base/SKILL.md` 0.5/0.6 cwd-guard callout verbatim, which instructs the operator to **halt** when `millpy-bg` rejects cwd as a non-task worktree. Step 3.5's own preserved-verbatim text says this step "never blocks or fails the merge" and "never triggers the Rollback section." The card requires keeping both texts unchanged/verbatim but never reconciles the new halt instruction with the existing no-block guarantee.
**Fix:** Either scope the halt-on-cwd-mismatch to only the dispatch attempt (with recompute treated as skipped/errored, matching the existing fail-safe framing) or explicitly carve out this one guard as an exception to "never blocks."

### [NIT:consistency] Grep exclusion syntax left as prose instead of a literal command
**Location:** Batch 2 / Card 5 (mill-finalize Step 3 scan).
**Issue:** Every other git operation in `mill-finalize/SKILL.md` (Step 3, Step 4) is given as a literal fenced bash block. Card 5's new scan step describes the exclusions ("excluding `<task_dir>` itself and excluding `plugins/**/SKILL.md`, `plugins/**/unit_tests/**`, and `plugins/**/integration_tests/**`") only in prose with an "e.g." hedge on the command itself, not as a concrete pathspec/command matching the file's established style.
**Fix:** Give the literal `git -C <worktree> grep` invocation with pathspec-magic exclusions (e.g. `':!<task_dir>' ':!plugins/**/SKILL.md' ...`), consistent with the rest of the file's bash-block convention.

## Verdict

REQUEST_CHANGES
Two unresolved edge-case/consistency gaps (Step 5.5's commit-scope premise, Step 3.5's halt-vs-never-blocks conflict) need addressing.
MILL_REVIEW_END
