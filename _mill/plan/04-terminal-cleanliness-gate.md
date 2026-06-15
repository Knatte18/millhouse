# Batch: terminal-cleanliness-gate

```yaml
task: "Fix wiki push upstream, cleanliness gate, mojibake, container config, and stacked-branch finalize"
batch: "terminal-cleanliness-gate"
number: 4
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-cleanliness.py
depends-on: []
```

## Batch Scope

Fixes GitHub issue #467: mill-go's Handoff terminal cleanliness gate is a
blanket `git status --porcelain --untracked-files=no` that wedges on unrelated
tracked `_mill/` dirt from another task (common in M2+ repos with a nested
tracked `_mill/`). Add a task-scoped helper to `_cleanliness.py` that returns
only dirt within the task's own scope, and rewire the mill-go Handoff gate to
use it. Task scope = the `task_dir` subtree ∪ paths changed by the task's own
commits vs the parent branch.

## Cards

### Card 8: compute_terminal_dirt helper

- **Context:**
  - `plugins/mill/scripts/_pygit2_util.py`
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/scripts/_cleanliness.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a function
  `compute_terminal_dirt(worktree: Path, task_dir: Path, parent_branch: str) ->
  list[str]` to `_cleanliness.py`. It runs
  `_pygit2_util.status_porcelain(worktree, include_untracked=False)` for current
  dirt, computes the task's owned paths as the union of (a) paths under
  `task_dir` (worktree-relative) and (b) the names from `git diff --name-only
  <parent_branch>...HEAD`, and returns the sorted subset of dirty entries whose
  path falls within that owned set. Factor the path-membership filter as a small
  pure helper (porcelain lines + owned-path set -> in-scope lines) so it is
  unit-testable without git, mirroring how `compute_new_dirt` isolates its
  set-diff. Any added runtime output must be ASCII.
- **Commit:** `feat(cleanliness): add task-scoped compute_terminal_dirt (#467)`

### Card 9: scope mill-go Handoff gate to task paths

- **Context:**
  - `plugins/mill/scripts/_cleanliness.py`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `mill-go/SKILL.md`, replace the Handoff "Terminal
  cleanliness gate" (the blanket `git -C <worktree> status --porcelain
  --untracked-files=no` check) so it calls
  `_cleanliness.compute_terminal_dirt(<worktree>, <task_dir>, <parent_branch>)`
  and halts only when the returned list is non-empty, listing those in-scope
  files in the existing `BLOCKED:` message shape. `task_dir` and
  `parent_branch` are already available in mill-go's Path Setup / status.md.
  Keep the "do not set phase: done when the gate fires" behaviour.
- **Commit:** `fix(mill-go): scope terminal cleanliness gate to task paths (#467)`

### Card 10: compute_terminal_dirt tests

- **Context:**
  - `plugins/mill/scripts/_cleanliness.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-cleanliness.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `test-cleanliness.py`, add tests for
  `compute_terminal_dirt` following the file's existing mock pattern (patch
  `_cleanliness._pygit2_util.status_porcelain`, and mock the parent-diff lookup):
  (1) in-scope dirt (a file under `task_dir`, and a file in the parent-diff set)
  is returned; (2) out-of-scope dirt (e.g. another task's nested `_mill/` path
  not under `task_dir` and not in the parent-diff set) is ignored; (3) clean
  worktree returns an empty list. If the pure membership filter is exposed
  separately, also test it directly with synthetic input.
- **Commit:** `test(cleanliness): cover task-scoped terminal dirt (#467)`

## Batch Tests

`verify:` runs `test-cleanliness.py` only — it already covers `_cleanliness`
and gains the `compute_terminal_dirt` cases. The `mill-go/SKILL.md` edit is
prose wiring with no separate runnable surface; its correctness is reviewed and
backed by the helper's tests.
