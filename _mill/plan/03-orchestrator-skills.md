# Batch: orchestrator-skills

```yaml
task: "Fix nested mill layout paths, whole-repo formatter drift, and stacked-branch PR cleanup"
batch: orchestrator-skills
number: 3
cards: 6
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-mill-finalize-dispatch.py test-finalize-cleanup.py
depends-on: [2]
```

## Batch Scope

Update every orchestrator SKILL that anchors a `_mill/` path on `git_root`, wire
mill-go's cleanliness gate to the batch-2 `revert_out_of_scope_drift` helper, and
land the stacked-branch clean-PR change in mill-finalize. All SKILL.md edits for
the path-resolution fix and the #493 changes are concentrated here so that no
SKILL file is edited by two parallel batches. This batch depends on batch 2
because mill-go's gate wiring (card 10) references
`_cleanliness.revert_out_of_scope_drift`, whose signature is fixed in batch 2.

Batch-local decision: SKILL prose is the deliverable for cards 8–12 (no runnable
surface); the only test edit is `test-mill-finalize-dispatch.py` (card 13), whose
inline boolean mirrors the mill-finalize dispatch decision and must flip for the
stacked case. `test-finalize-cleanup.py` is run as regression (the
`base_tracks_task_dir` helper is reused unchanged) and is not edited.

## Cards

### Card 8: Define worktree_root from the hub root in mill-start

- **Context:**
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In the Entry / Path Setup section, **add** an explicit
  `worktree_root = _paths.resolve_hub_path()` (and `git_root = _paths.resolve_git_root()`
  where the steps reference `git_root`). These steps currently reference
  `worktree_root` without ever assigning it — it is implicitly `git_root`, which
  breaks in a nested layout. State that `resolve_task_path` is fed the hub root.
  Do not change any other behavior.
- **Commit:** `fix(mill-start): anchor worktree_root on hub root for nested layouts`

### Card 9: Define worktree_root from the hub root in mill-plan

- **Context:**
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Same addition as card 8, in the mill-plan Entry / Path Setup
  section: add an explicit `worktree_root = _paths.resolve_hub_path()` (plus
  `git_root` where referenced). `resolve_task_path(worktree_root, …)` then resolves
  `_mill/` paths under the hub root in a nested layout.
- **Commit:** `fix(mill-plan): anchor worktree_root on hub root for nested layouts`

### Card 10: Fix mill-go path callsites and wire the drift-revert guard

- **Context:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_cleanliness.py`
  - `plugins/mill/scripts/_parent_branch.py`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Three edits to `mill-go/SKILL.md`.
  (1) **Per-batch cleanup snippet:** the inline `python -c` block whose body
  contains `status_path = _paths.resolve_task_path(_paths.resolve_git_root(),
  '_mill/status.md')` runs in its own subprocess where `worktree_root` is NOT in
  scope. Replace `_paths.resolve_git_root()` with `_paths.resolve_hub_path()`
  inside that snippet so the status path resolves under the hub root in a nested
  layout. (Do not reference `worktree_root` there — it does not exist in the
  snippet.)
  (2) **Crash-recovery inline helper:** the inline `python -c` block that sets
  `git_root = _paths.resolve_git_root()` then `reviews_dir = git_root / '_mill/reviews'`
  — change the reviews anchor to the hub root, i.e. `hub = _paths.resolve_hub_path()`
  then `reviews_dir = hub / '_mill/reviews'`. Leave the adjacent
  `scratch_dir = git_root / '.scratch'` unchanged (`.scratch` is repo-root scratch,
  not a `_mill/` task-state path).
  (3) **Cleanliness gate (step 2b):** before the existing
  block-on-`compute_new_dirt` flow, derive `parent_branch =
  _parent_branch.resolve(status_path, interactive=False)` and
  `task_dir = status_path.parent` within step 2b (neither is in scope at 2b today;
  `parent_branch` is otherwise resolved only at Handoff). Then call
  `_cleanliness.revert_out_of_scope_drift(<worktree>, task_dir, parent_branch)` to
  revert out-of-scope formatter drift and warn. Decide the block using the helper's
  returned remaining-in-scope dirt (the second element of its return tuple) instead
  of the raw `compute_new_dirt` list — block the batch only if that in-scope
  remaining set is non-empty, preserving the existing blocked-state status writes
  and per-batch cleanup. Keep prose ASCII-only.
- **Commit:** `fix(mill-go): hub-root _mill paths and out-of-scope drift revert in gate`

### Card 11: Anchor git-pr task-branch detection on the hub root

- **Context:**
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/skills/git-pr/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In Step 1.5 (Detect task branch), the config-based resolution
  branch resolves `status_path = _paths.resolve_task_path(git_root, cfg['paths']['status_md'])`
  with `git_root = Path.cwd()`. Change it to resolve against the hub root via
  `_paths.resolve_hub_path()` so the `_mill/status.md` existence check is correct in
  a nested layout. Leave the `MILL_FINALIZE_PR_CLEANUP` skip and the standalone
  literal-`$GIT_ROOT/_mill/status.md` fallback unchanged.
- **Commit:** `fix(git-pr): resolve task-branch status.md against hub root`

### Card 12: Stacked-branch clean PR in mill-finalize

- **Context:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_finalize_cleanup.py`
- **Edits:**
  - `plugins/mill/skills/mill-finalize/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Three coordinated edits. (1) Path: change the Path Setup
  `worktree_root = git_root` to anchor on the hub root (`_paths.resolve_hub_path()`),
  so `task_dir = status_path.parent` is correct in a nested layout. (2) Dispatch
  trigger: change "PR mode activates when `require_pr is True` AND `parent_branch ==
  base_branch`" to activate on `require_pr is True` alone (drop the
  `parent_branch == base_branch` clause). (3) PR invocation (Step 5): change the
  invocation argument from `/git-pr <base_branch>` to `/git-pr <parent_branch>` so
  the PR opens against the parent. Leave Step 3 cleanup
  (`_finalize_cleanup.base_tracks_task_dir(git_root, parent_branch, task_dir)`,
  restore-vs-remove) and the `MILL_FINALIZE_PR_CLEANUP=1` env var unchanged.
- **Commit:** `feat(mill-finalize): clean PR to parent for stacked tasks`

### Card 13: Update finalize dispatch tests for stacked PR mode

- **Context:**
  - `plugins/mill/skills/mill-finalize/SKILL.md`
  - `plugins/mill/unit_tests/test-finalize-cleanup.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-mill-finalize-dispatch.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** The test mirrors the mill-finalize dispatch decision as an
  inline boolean. Update the decision expression from `require_pr and parent_branch
  == base_branch` to `require_pr` alone. Flip the existing "scenario 2"
  (`require_pr_to_base=true, parent != base_branch`) to assert **PR mode** (was
  direct mode), and add a scenario asserting that for a stacked task the PR target
  is `parent_branch` (not `base_branch`). Keep the existing scenarios for
  `require_pr` absent (direct mode) and the kebab-case-key breaking-change guard.
  Preserve the file's PASS/FAIL + `failures` list harness and non-zero exit on
  failure.
- **Commit:** `test(mill-finalize): assert stacked tasks open PR to parent`

## Batch Tests

`verify:` runs `test-mill-finalize-dispatch.py` (the flipped stacked-PR dispatch
scenarios, card 13) and `test-finalize-cleanup.py` as regression for the reused
`base_tracks_task_dir` restore-vs-remove helper. Cards 8–12 edit SKILL prose with
no runnable surface — they are verified by plan/code review, not a test runner.
Scope is limited to the two finalize tests via `--only`; no cross-cutting helper
is touched.
