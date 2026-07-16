MILL_REVIEW_BEGIN
# Review: Miscellaneous small tooling and doc/template accuracy gaps

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-16
```

## Findings

### [GAP] #640 rebasing omits owned_paths -> reverts in-scope files
**Section:** Decisions / cleanliness-revert-hub-prefix-fix (#640)
**Issue:** The decision rebases only the git-root-relative porcelain paths to hub-relative "before the existing task_dir_str/owned_paths comparison", but `owned_paths` comes from `_parent_diff_names` (`git diff --name-only`, always git-root-relative); rebasing one side breaks the `path in owned_paths` check in nested layouts, so a task-owned modification outside `task_dir` (e.g. `src/csharp/NORCE.Models/foo.cs`) becomes hub-relative `foo.cs`, misses owned_paths, is classed out-of-scope, and gets `git checkout`-reverted — trading the double-prefix bug for silent loss of in-scope work.
**Fix:** State that owned_paths (and task_dir_str) must be brought to the same convention as the porcelain paths — `compute_scope_violations` is not a full analog because it never consults owned_paths; add a nested-hub test asserting an owned out-of-task_dir modification is NOT reverted.

### [GAP] #651/#640 batch-structure contradicts #651 file ownership
**Section:** Decisions / batch-structure
**Issue:** The sequencing rationale claims "#651 and #640 both touch `mill-go/SKILL.md`" (an "escalation-checklist comment") and marks them sequential to avoid a same-file conflict, but #651's own file-ownership list, Scope-In, and the #651 decision name only `millpy-fix.py`, `_reviewers.py`, `mill-config.yaml`, and tests — no `mill-go/SKILL.md` edit.
**Fix:** Resolve which is authoritative — either add the mill-go/SKILL.md edit to #651's scope/ownership, or drop the false premise and note #651 and #640 are file-disjoint (removing the sequential constraint).

### [NOTE] #658 overstates the current detection text
**Section:** Problem #3 / Decisions / golang-build-gopath-fallback (#658)
**Issue:** The discussion says the Tool Installation section "tells the agent to run a bare `which`/`command -v` check" and the fix should add a fallback "before the existing `command -v`/`which` check"; the actual section (SKILL.md lines 35-48) prescribes no detection command at all — only prose "if either tool is not found".
**Fix:** Note that the fix must introduce the full detection snippet (command -v plus GOPATH/bin fallback), not merely append a fallback to a non-existent existing check.

## Verdict

GAPS_FOUND
Two GAPs: #640 owned_paths rebasing risks reverting in-scope files; batch-structure contradicts #651 ownership.
MILL_REVIEW_END
