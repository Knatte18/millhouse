# Batch: dirty-parent-worktree-preflight

```yaml
task: "Merge-in conflict handling: silent marker-verification gaps, mill-config.yaml chicken-and-egg crash, and undocumented dirty-worktree squash failure"
batch: "dirty-parent-worktree-preflight"
number: 4
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/test-merge.py
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
- **Requirements:** In `plugins/mill/skills/mill-merge/SKILL.md`'s `### 5. Direct squash` section, "Direct path:" subsection, immediately before the bash block containing `git -C <parent-path> merge --squash "$CHILD_BRANCH"` (currently the first line of that block), add: (1) a preceding instruction to run `git -C <parent-path> status --porcelain --untracked-files=no` and check whether its output is non-empty; (2) if non-empty, halt Step 5 (do not run `merge --squash`) and report to the operator: "the parent worktree is not clean — either (a) this is independent uncommitted work in the parent worktree: commit or stash it, then re-run `/mill-merge`; or (b) this is a partially-applied squash left over from a Step 5 that failed after `merge --squash`/`reset`/`checkout` already staged changes but before `commit` landed: run `git -C <parent-path> commit` to complete it, or `git -C <parent-path> reset --hard` to discard it, then re-run." This check applies only when `mode == 'worktree'` (the `mode` variable bound at Entry step 1, `plugins/mill/skills/mill-merge/SKILL.md` line 21) — skip it entirely when `mode == 'inplace'`, matching the existing in-place bypass pattern documented at line 33 (Step 5 already omits `-C <parent-path>` in that mode, so there is no separate parent worktree to check). State explicitly that this new pre-squash halt is exempt from the existing `## Rollback (Steps 1-5 only)` section (`plugins/mill/skills/mill-merge/SKILL.md` line 320, "Any failure between lock acquisition (Step 1) and the squash landing on parent (Step 5) rolls back via ... `git -C <parent-path> reset --hard mill-checkpoint-<name>`") — mirroring that same section's existing Step-4-specific carve-out ("**Cleanup-commit rollback (Step 4):**... `git reset --hard HEAD`", no checkpoint ref). Without this carve-out, a mechanical reading of the generic Steps-1-5 rollback rule would apply `git -C <parent-path> reset --hard mill-checkpoint-<name>` to this halt too, destroying exactly the independent uncommitted parent-worktree work that scenario (a)'s own halt message tells the operator to commit or stash — nothing has been mutated yet at this halt point, so there is nothing to roll back.
- **Commit:** `docs(mill-merge): add pre-squash dirty-parent-worktree check to Step 5 (#705)`

### Card 16: Extend the Step 5 integration test to prove the dirty-parent check fires in both scenarios

- **Context:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Edits:**
  - `plugins/mill/integration_tests/test-merge.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `plugins/mill/integration_tests/test-merge.py`'s flat-hub scenario, immediately before the existing `git -C str(hub) merge --squash` line (~line 614), add a new sub-scenario using a fresh trio built via `_setup_trio(container)` (the existing helper at `test-merge.py:89`, called a second time with a new container/tempdir so it does not disturb the existing flat-hub scenario's own trio and assertions) — since Step 5's Direct-path check is being tested, not the full teardown sequence, the new sub-scenario only needs to reach the point immediately before Step 5's squash line. `_setup_trio` returns `(hub, wiki_path, worktree, slug)` (verified at `test-merge.py:89,264` — there is one worktree, not two, and `slug` is always the literal `"demo-merge"`); derive `child_branch = f"test/{slug}"` (the branch `_setup_trio` creates the worktree on, per line 235) before using it. `hub` carries one tracked file, `README.md` (committed at `test-merge.py:207-209`). Each of the three new `_setup_trio(container)` calls below MUST bind its returned tuple to distinct new names, never reusing the `hub`/`wiki_path`/`worktree`/`slug` identifiers already bound earlier in the same flat-hub `main()` scenario — reusing those names would silently repoint the existing scenario's later assertions (squash, archive tag, Home.md flip, from line ~614 onward) at the wrong trio. Follow the file's own naming convention for extra scenario trios (e.g. `nested_hub` at line 791, `verify_hub_root` at line 881): use `dirty_hub, dirty_wiki_path, dirty_worktree, dirty_slug` for case 1, `retry_hub, retry_wiki_path, retry_worktree, retry_slug` for case 2, and `untracked_hub, untracked_wiki_path, untracked_worktree, untracked_slug` for the untracked-file check, each from its own fresh `_setup_trio(<distinct container path>)` call. Cover two cases:
  1. **Independent uncommitted edit:** using the `dirty_*` trio, write an uncommitted change to `dirty_hub / "README.md"` (already committed by `_setup_trio`) without staging or committing it. Run `git -C str(dirty_hub) status --porcelain --untracked-files=no` via `_run` and `_assert` the output is non-empty (`_assert(status_output.strip() != "", ...)`). Then `_assert` that `dirty_hub`'s dirty `README.md` content still matches the uncommitted edit (proving nothing further ran that would have touched it) and that `git -C str(dirty_hub) log --oneline -n 1` does NOT show a squash-merge commit (proving the documented halt means the squash step is skipped, not attempted-and-rolled-back).
  2. **Mid-Step-5-retry (partially-applied squash):** using the `retry_*` trio, derive `retry_child_branch = f"test/{retry_slug}"` and run `git -C str(retry_hub) merge --squash retry_child_branch` (staging squash content) but do NOT run the subsequent `commit` — simulating a Step 5 that failed between `merge --squash` and `commit`. Run the same `git -C str(retry_hub) status --porcelain --untracked-files=no` and `_assert` the output is non-empty here too — proving the porcelain check flags this state identically to case 1 (which is exactly why `_mill/discussion.md`'s Decision gives the halt message two scenarios rather than trying to auto-distinguish them in the check itself).
  Add an untracked-file negative check: using the `untracked_*` trio, write an untracked file (no `git add`) into `untracked_hub`, and `_assert` that `git -C str(untracked_hub) status --porcelain --untracked-files=no` output is empty for that file alone (proving the `--untracked-files=no` scoping choice — untracked noise must NOT trip this check).
- **Commit:** `test(mill-merge): cover dirty-parent-worktree preflight check for both halt scenarios (#705)`

## Batch Tests

`verify:` runs `plugins/mill/integration_tests/test-merge.py` directly as a script, the same non-`run-all.py` direct-invocation shape batches 1 and 2 already use for their own unit-test files. Card 16's three new assertions (independent-edit halt, mid-retry halt, untracked-noise non-halt) prove the underlying `git status --porcelain --untracked-files=no` check Card 15 documents actually behaves as specified; Card 15 itself is prose with no independent runtime to verify beyond that.
