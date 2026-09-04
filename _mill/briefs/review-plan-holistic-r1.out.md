MILL_REVIEW_BEGIN
# Review: mill-merge-in/mill-finalize/codeguide-update: cleanup-ordering and path-resolution bugs — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: plan/
date: 2026-09-04
```

## Findings

### [BLOCKING:design] Card 2 reorder drops status_path from the override branch
**Location:** batch 1 / Card 2 (mill-merge-in Entry). **Issue:** Today `status_path` is only computed inline as part of step 2's `resolve(...)` call. Card 2 skips that call entirely when a positional `<branch>` override is supplied, but never instructs hoisting the `status_path = _paths.resolve_task_path(...)` assignment to run unconditionally before the branch check — yet the retained Liveness-check paragraph (kept verbatim, "content... not... updating") still claims "status_path already bound at the top of this Entry step" and needs it for the dead-parent rebind, which can fire on either branch. **Fix:** Add a Requirements sentence explicitly hoisting the `status_path` computation above the branch check so it's bound regardless of which path is taken.

### [BLOCKING:design] Batch 2 scan can't reach the citation source its own example names
**Location:** batch 2 / Card 5 (mill-finalize scan) and the `930-scan-and-document-discussion-citations` Shared Decision. **Issue:** The scan runs `git -C <worktree> grep` over the task repo's own git-tracked tree. Both the discussion Decision and Card 6's new CLAUDE.md bullet illustrate the unsafe citation as "a wiki Done entry" — but per this repo's own architecture (CLAUDE.md: "Wiki holds only `Home.md`," a sibling clone resolved via `_paths.resolve_wiki_path`), Home.md is not part of `<worktree>`'s git repository and can never be matched by this grep. The scan can only catch citations in in-repo permanent docs (e.g. `doc/backlog.md`), not the wiki-board scenario the plan itself uses to motivate it. **Fix:** Either scope the scan (or a companion check) to also grep the resolved wiki path, or narrow the batch's/decision's own framing to state explicitly that wiki Home.md citations are out of scan-reach and rely on the CLAUDE.md doc note alone for that case.

### [NIT:consistency] Card 3's unrestricted porcelain check may sweep unrelated dirty state
**Location:** batch 1 / Card 3 (mill-merge-in Step 5.5). **Issue:** Dropping the `-d _mill/briefs` precondition and checking unrestricted `git status --porcelain` correctly fixes #946, but nothing in the Requirements addresses (or asserts is impossible) any other uncommitted change existing at this point being swept into a commit still labeled "mill-merge-in: commit dispatch briefs." **Fix:** Add one sentence noting why the tree is guaranteed to hold only briefs/codeguide-doc changes at this point, or accept the risk explicitly.

### [NIT:consistency] Card 4's "every other call site... already carries" claim is inaccurate
**Location:** batch 1 / Card 4 (mill-merge-in Step 3.5). **Issue:** The Requirements say to add the cwd-guard callout that "every other `millpy-bg` call site in this file family... already carries" — but `mill-merge-in/SKILL.md` and `mill-merge/SKILL.md` currently have zero `millpy-bg` call sites; Card 4's new one is the first in this file family. The only existing precedent is in the different file `mill-go-base/SKILL.md`. **Fix:** Reword to "matching the callout mill-go-base/SKILL.md's 0.5/0.6 already carry" rather than implying sibling sites within this same file.

## Verdict

REQUEST_CHANGES
Two BLOCKING design gaps (undefined status_path path, scan can't reach the wiki case it's framed around) need addressing.
MILL_REVIEW_END
