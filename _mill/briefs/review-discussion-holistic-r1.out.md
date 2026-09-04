MILL_REVIEW_BEGIN
# Review: mill-merge-in/mill-finalize/codeguide-update: cleanup-ordering and path-resolution bugs

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

### [BLOCKING:design] #977 fix premise not verified against mill-merge-in's actual resolve() call
**Section:** Decisions/977-explicit-parent-branch. **Issue:** The decision assumes mill-merge-in's Entry step 3 positional `<branch>` override is checked *before* step 2's `_parent_branch.resolve(status_path, interactive=False, ...)` call fires. `_parent_branch.resolve()` (`plugins/mill/scripts/_parent_branch.py:190-230`) takes no branch-override parameter at all and, when `status_path` is absent and `interactive=False`, raises `ParentBranchError` unconditionally — i.e. the exact #977 crash. mill-merge-in/SKILL.md's Entry lists "resolve from status.md" (step 2) before "positional override" (step 3) with no explicit "skip step 2 entirely when `<branch>` is supplied" instruction. **Fix:** State explicitly (in-scope or as a note) that mill-merge-in's Entry must check for the positional override before calling `resolve()`, or add that ordering fix to Scope/In — otherwise the closed-route crash can still reproduce even after mill-merge's Step 2 passes `parent_branch` explicitly.

### [BLOCKING:design] #946 guard broadening leaves the `[ -d _mill/briefs ]` precondition untouched
**Section:** Decisions/946-commit-codeguide-docs. **Issue:** mill-merge-in/SKILL.md:178 gates the whole commit block on `[ -d <worktree>/_mill/briefs ] && [ -n "$(git status --porcelain -- _mill/briefs)" ]`. The decision only widens the second (porcelain) clause to an unrestricted `git status --porcelain`; it never mentions the first (`-d`) clause. On a task where `_mill/briefs/` was never created (e.g. no conflict/verify-fix sub-dispatch ever ran) but inline codeguide docs *were* staged by Step 5, the `-d` check short-circuits the `&&` to false and the commit still never runs — reproducing #946 in exactly the scenario it targets. **Fix:** Decision must also drop or OR-relax the `-d _mill/briefs` precondition so it doesn't gate out a codeguide-only dirty index.

### [BLOCKING:design] #930 citation pattern (`_mill/discussion.md`) is not task-specific and matches the tooling's own docs
**Section:** Decisions/930-scan-and-document-discussion-citations. **Issue:** The scan searches the git-tracked tree for the literal string `_mill/discussion.md`. That path is identical across every task (not slug/branch-qualified), and the literal string already appears in ~30 files repo-wide as generic documentation of the convention itself (e.g. `plugins/mill/skills/mill-start/SKILL.md`, `mill-plan/SKILL.md`, `mill-claim/SKILL.md`, several `unit_tests/*.py`, `templates/mill-config.yaml`) — none of which are "roadmap citations" of any specific task's discussion file. A grep as described will produce noisy false-positive warnings on effectively every mill-finalize run in this repo, and cannot distinguish a genuine stale citation from the tooling's own self-referential mentions, undermining the stated "attribution back to the task that broke it" rationale. **Fix:** Narrow the pattern (e.g. require it inside a markdown link/URL context, or exclude `plugins/**/SKILL.md` and `unit_tests/`), or explicitly acknowledge and bound the false-positive rate as acceptable for an informational-only warning.

## Verdict

REQUEST_CHANGES
Three decisions rest on premises contradicted by the actual source files they cite.
MILL_REVIEW_END
