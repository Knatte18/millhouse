# Batch: finalize-merge-paths

```yaml
task: 55 (A) -- Fix hardcoded _mill/ paths and mill-setup junction/config bugs
batch: finalize-merge-paths
number: 3
cards: 2
verify: null
depends-on: []
```

## Batch Scope

Fix hardcoded `_mill/` path strings in `mill-finalize/SKILL.md` and `mill-merge/SKILL.md`. Both skills use `status_path = git_root / "_mill" / "status.md"` and `git rm -r _mill/`. The fix adds a Path Setup sub-step that derives `status_path` via `_paths.resolve_task_path` and sets `task_dir = status_path.parent`, then replaces the hardcoded `_mill/` in git add and git rm commands. No Python helper changes.

## Cards

### Card 3: Add Path Setup and replace _mill/ strings in mill-finalize/SKILL.md

- **Context:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/scripts/_parent_branch.py`
- **Edits:**
  - `plugins/mill/skills/mill-finalize/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. **Add Path Setup sub-step** in the Entry section, immediately after the step that resolves `wiki_path` and `worktree_root` (= `git_root`). The sub-step text:
     > **Path Setup.** `cfg = _config.load_config(wiki_path, worktree_root)`. Then `status_path = _paths.resolve_task_path(worktree_root, cfg['paths']['status_md'])` and `task_dir = status_path.parent`.
  2. **Replace existing `status_path` assignment** on line 20 (`status_path = git_root / "_mill" / "status.md"`) with a reference to the new Path Setup: remove that line entirely (or inline-replace it with a note that `status_path` is set in Path Setup). The `data = _status.read_status(status_path)` call and subsequent usage remain unchanged.
  3. **PR-pending code block** (the block containing `git add _mill/status.md` on line 49): replace `_mill/status.md` with `<status_path>`.
  4. **Cleanup commit block** (`git rm -r _mill/` on line 58): replace with `git -C <worktree> rm -r <task_dir>`.
  5. **Idempotency note** (line 62, prose referencing `_mill/`): update to reference `<task_dir>` so it reads: "if `<task_dir>` is already absent (re-run after partial failure), `git rm -r <task_dir>` prints 'did not match any files' — treat as a no-op."
  6. **Step referencing `/git-pr`** (line 73, prose referencing `_mill/status.md` absent): update the sentence so that references to `_mill/status.md` becoming absent are expressed as "`<task_dir>` is absent (cleanup already ran)."
  7. **Board Discipline section** (line 95): update the prose reference `_mill/status.md writes are committed...` to reference `status_path` variable.
- **Commit:** `fix(mill-finalize): replace hardcoded _mill/ paths with config-derived variables`

### Card 4: Add Path Setup and replace _mill/ strings in mill-merge/SKILL.md

- **Context:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/scripts/_parent_branch.py`
  - `plugins/mill/scripts/_tasks_md.py`
- **Edits:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. **Add Path Setup sub-step** in the Entry section after wiki path + slug resolution. Same text as Card 3 step 1.
  2. **Entry step 5** (line 38, `status_path is git_root / "_mill" / "status.md"`): replace the construction with a reference to the Path Setup result: `status_path` is resolved via `_paths.resolve_task_path(worktree_root, cfg['paths']['status_md'])` (set in Path Setup). Add `task_dir = status_path.parent`.
  3. **Conditional status-path check** (line 41, prose "Try `_mill/status.md` first. If `status_path.exists()`..."): the conditional logic `if status_path.exists()` is already correct (it uses the variable). The prose in the surrounding explanation that says "the PR-path cleanup commit already removed `_mill/`" should be rephrased to say "already removed `<task_dir>/`" so it reflects the resolved path.
  4. **Cleanup commit block** (`git rm -r _mill/` on line 82): replace with `git -C <worktree> rm -r <task_dir>`.
  5. **Idempotency note** (line 88): update to reference `<task_dir>`.
  6. **PR-pending branch-protection fallback** (lines 142, 149, both `git add _mill/status.md`): replace `_mill/status.md` with `<status_path>`.
  7. **Board Discipline section** (lines 247–248): update prose "Task state (`_mill/status.md`, `_mill/discussion.md`, `_mill/plan/`, `_mill/reviews/`) lives in `_mill/` on the task branch" → "Task state (`status_path`, `discussion_path`, `plan_dir`, `reviews_dir`) lives in the task directory (`_mill/` or `task/` for legacy worktrees) on the task branch." Update "cleanup commit removes the entire `_mill/` directory" → "cleanup commit removes the entire `task_dir` directory."
- **Commit:** `fix(mill-merge): replace hardcoded _mill/ paths with config-derived variables`

## Batch Tests

`verify: null` — SKILL.md edits; no runnable test surface.
