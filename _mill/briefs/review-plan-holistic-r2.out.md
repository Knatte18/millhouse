MILL_REVIEW_BEGIN
# Review: Fix codeguide-update scope resolution on stacked branches and resolve_scope.py branch-name parsing — holistic

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-07-09
```

## Findings

### [NIT] Parent resolution ordered before codeguide-initialized check
**Location:** Batch 3 / Card 7
**Issue:** Requirement inserts the `resolve_hub_path()`/`resolve_task_path()`/`resolve_for_codeguide` block *before* the existing `resolve.py --json` `found == false` skip, so every `git-commit` (including non-codeguide and non-mill repos, e.g. `--onmain` on the hub) does mill path resolution that is then thrown away.
**Fix:** Place the parent-resolution prose after the `found == false` skip so it only runs once codeguide is confirmed initialized.

### [NIT] Card 7 degrade path leans on unstated error wrapping
**Location:** Batch 3 / Card 7
**Issue:** `resolve_for_codeguide` (Card 5) only swallows `ParentBranchError`; the `_paths.resolve_hub_path()`/`resolve_task_path` calls the skill performs can still raise outside a mill worktree, yet the requirement only implies ("or the helper errored resolving hub_root/status_path") that this degrades.
**Fix:** State explicitly that the skill must guard those resolutions so a non-hub cwd falls back to the no-arg invocation without aborting the commit.

### [NIT] Scenario 14 setup prose is self-contradictory
**Location:** Batch 1 / Card 3 (Scenario 14)
**Issue:** The setup sentence ("either directly on `mill-checkpoint-feature` advancing it further is wrong; instead ... stay on the same branch line and advance HEAD ...") is garbled and hard to implement unambiguously, though the intended `<base>..HEAD` semantics are correct.
**Fix:** Reword to a clear sequence: commit `base.py` on main, create `mill-checkpoint-feature` at that commit, then commit `a.py`/`b.py` advancing HEAD so the checkpoint is an ancestor of HEAD.

## Verdict

APPROVE
Decisions faithfully implemented against actual signatures; only minor ordering and wording nits remain.
MILL_REVIEW_END