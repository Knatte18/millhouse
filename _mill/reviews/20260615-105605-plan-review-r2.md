Confirmed. The git-pr guard halts when `_mill/status.md` exists. After Card 12's restore-from-base path, `status.md` exists in the worktree, so when mill-finalize Step 5 invokes `/git-pr`, the guard fires and halts — breaking PR creation on exactly the stacked-branch case batch 5 aims to fix. Card 13's change makes the guard MORE robust at detecting status.md (config-resolved), which makes the conflict worse, not better. Neither card addresses this interaction. This is a BLOCKING cross-card sequencing/consistency defect.

MILL_REVIEW_BEGIN
# Review: Fix wiki push upstream, cleanliness gate, mojibake, container config, and stacked-branch finalize — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-15
```

## Findings

### [BLOCKING] Restored task_dir collides with git-pr guard
**Location:** Batch 5, Cards 12 + 13 vs mill-finalize Step 5
**Issue:** Card 12's True-branch `checkout <base> -- <task_dir>` leaves `_mill/status.md` present in the worktree; mill-finalize Step 5 invokes `/git-pr`, whose Step 1.5 guard halts when `status.md` exists — and Card 13 makes that guard *more* aggressive (config-resolved), so on the stacked-branch case the plan targets, PR creation now halts.
**Fix:** Reconcile the two: e.g. have Card 13's guard skip when invoked from mill-finalize (env flag) on a base-tracked task_dir, and update mill-finalize Step 5's "task_dir is absent" assumption (line 73) to cover the restored-present case.

### [NIT] parent_branch not available in mill-go Path Setup
**Location:** Batch 4, Card 9
**Issue:** Card claims `parent_branch` is "already available in mill-go's Path Setup / status.md," but Path Setup (step 4.5) derives only `worktree_root`/`task_dir`; mill-go never resolves `parent_branch` (unlike mill-finalize, which uses `_parent_branch.resolve`).
**Fix:** Name the derivation explicitly (e.g. `_parent_branch.resolve(status_path, interactive=False)`) and add `_parent_branch` to the card's resolution note.

### [NIT] Card 3 test does not exercise candidate #2 distinctly
**Location:** Batch 2, Card 3
**Issue:** For a plain `_git_init`'d repo, `resolve_main_worktree_root(clone)` returns the clone itself, so candidate #2 (`resolve_main_worktree_root(worktree_root)/mill-config.yaml`) equals candidate #3 (`worktree_root/mill-config.yaml`); the test passes via #3, not #2 as the card states.
**Fix:** To truly cover candidate #2 distinct from #3, place the config at the primary clone while passing a *linked worktree* as `worktree_root`; otherwise drop the "candidate #2" claim.

### [NIT] compute_terminal_dirt path-prefix stripping under-specified
**Location:** Batch 4, Card 8
**Issue:** `status_porcelain` returns `"XY path"` lines; the membership filter must strip the 3-char status prefix before comparing against the owned-path set, but the card only says "porcelain lines + owned-path set -> in-scope lines" without naming this.
**Fix:** State that the pure helper extracts `line[3:]` (path portion) before membership testing.

## Verdict

REQUEST_CHANGES
Batch 5's restored task_dir collides with the git-pr guard, blocking PR creation on stacked branches.
MILL_REVIEW_END