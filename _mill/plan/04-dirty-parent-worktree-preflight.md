# Batch: dirty-parent-worktree-preflight

```yaml
task: "Merge-in conflict handling: silent marker-verification gaps, mill-config.yaml chicken-and-egg crash, and undocumented dirty-worktree squash failure"
batch: "dirty-parent-worktree-preflight"
number: 4
cards: 2
verify: null
depends-on: []
```

## Batch Scope

Fixes #705: `mill-merge` SKILL.md's Step 5 ("Direct squash") has no documented handling for `git -C <parent-path> merge --squash` failing because the parent worktree has uncommitted tracked changes that would be overwritten. This batch adds a pre-squash `git status --porcelain --untracked-files=no` check with a two-scenario halt message (independent uncommitted edit vs. mid-Step-5-retry) to `mill-merge/SKILL.md` Step 5, scoped to `mode == 'worktree'` only, per `_mill/discussion.md`'s `dirty-parent-worktree-preflight (#705)` Decision, and extends `plugins/mill/integration_tests/test-merge.py` to prove the check's underlying git command actually flags both dirty scenarios. No other batch touches either file.

## Cards

### Card 15: Add the pre-squash dirty-parent-worktree check to Step 5

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `plugins/mill/skills/mill-merge/SKILL.md`'s `### 5. Direct squash` section, "Direct path:" subsection, immediately before the bash block containing `git -C <parent-path> merge --squash "$CHILD_BRANCH"` (currently the first line of that block), add: (1) a preceding instruction to run `git -C <parent-path> status --porcelain --untracked-files=no` and check whether its output is non-empty; (2) if non-empty, halt Step 5 (do not run `merge --squash`) and report to the operator: "the parent worktree is not clean — either (a) this is independent uncommitted work in the parent worktree: commit or stash it, then re-run `/mill-merge`; or (b) this is a partially-applied squash left over from a Step 5 that failed after `merge --squash`/`reset`/`checkout` already staged changes but before `commit` landed: run `git -C <parent-path> commit` to complete it, or `git -C <parent-path> reset --hard` to discard it, then re-run." This check applies only when `mode == 'worktree'` (the `mode` variable bound at Entry step 1, `plugins/mill/skills/mill-merge/SKILL.md` line 21) — skip it entirely when `mode == 'inplace'`, matching the existing in-place bypass pattern documented at line 33 (Step 5 already omits `-C <parent-path>` in that mode, so there is no separate parent worktree to check).
- **Commit:** `docs(mill-merge): add pre-squash dirty-parent-worktree check to Step 5 (#705)`

### Card 16: Extend the Step 5 integration test to prove the dirty-parent check fires in both scenarios

- **Context:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Edits:**
  - `plugins/mill/integration_tests/test-merge.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `plugins/mill/integration_tests/test-merge.py`'s flat-hub scenario, immediately before the existing `git -C str(hub) merge --squash` line (~line 614), add a new sub-scenario using a fresh trio built via `_setup_trio(container)` (the existing helper at `test-merge.py:89`, called a second time with a new container/tempdir so it does not disturb the existing flat-hub scenario's own trio and assertions) — since Step 5's Direct-path check is being tested, not the full teardown sequence, the new sub-scenario only needs to reach the point immediately before Step 5's squash line. Cover two cases:
  1. **Independent uncommitted edit:** after `_setup_trio` returns a fresh `(hub, worktree, child_worktree, child_branch)`, write an uncommitted change to a tracked file already present in `hub` (e.g. modify the file `_setup_trio` commits on `hub`'s own history) without staging or committing it. Run `git -C str(hub) status --porcelain --untracked-files=no` via `_run` and `_assert` the output is non-empty (`_assert(status_output.strip() != "", ...)`). Then `_assert` that `hub`'s dirty file's on-disk content still matches the uncommitted edit (proving nothing further ran that would have touched it) and that `git -C str(hub) log --oneline -n 1` does NOT show a squash-merge commit (proving the documented halt means the squash step is skipped, not attempted-and-rolled-back).
  2. **Mid-Step-5-retry (partially-applied squash):** on a second fresh trio, run `git -C str(hub) merge --squash child_branch` (staging squash content) but do NOT run the subsequent `commit` — simulating a Step 5 that failed between `merge --squash` and `commit`. Run the same `git -C str(hub) status --porcelain --untracked-files=no` and `_assert` the output is non-empty here too — proving the porcelain check flags this state identically to case 1 (which is exactly why `_mill/discussion.md`'s Decision gives the halt message two scenarios rather than trying to auto-distinguish them in the check itself).
  Add an untracked-file negative check: write an untracked file (no `git add`) into a third fresh trio's `hub`, and `_assert` that `git -C str(hub) status --porcelain --untracked-files=no` output is empty for that file alone (proving the `--untracked-files=no` scoping choice — untracked noise must NOT trip this check).
- **Commit:** `test(mill-merge): cover dirty-parent-worktree preflight check for both halt scenarios (#705)`

## Batch Tests

`plugins/mill/integration_tests/test-merge.py` is invoked directly as a script (`uv run --project plugins/mill python plugins/mill/integration_tests/test-merge.py`), not via the unit-test `run-all.py` harness — batch-level `verify:` is `null` per the overview's "Documentation-only batches skip verify:" Shared Decision, and this batch's own verification is the manual invocation of that integration test named here. Card 16's three new assertions (independent-edit halt, mid-retry halt, untracked-noise non-halt) prove the underlying `git status --porcelain --untracked-files=no` check Card 15 documents actually behaves as specified; Card 15 itself is prose with no independent runtime to verify beyond that.
