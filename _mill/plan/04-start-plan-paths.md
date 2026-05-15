# Batch: start-plan-paths

```yaml
task: 55 (A) -- Fix hardcoded _mill/ paths and mill-setup junction/config bugs
batch: start-plan-paths
number: 4
cards: 2
verify: null
depends-on: []
```

## Batch Scope

Fix hardcoded `_mill/` path strings in `mill-start/SKILL.md` and `mill-plan/SKILL.md`. Both skills need a Path Setup sub-step at entry. Mill-start creates new task state (write uses config-canonical path directly, not compat fallback). Mill-plan reads existing state (use `resolve_task_path`) and also creates new plan files (write uses config-canonical path). The `_status.update_field` call for the plan pointer must use `cfg['paths']['plan_dir']` instead of the hardcoded string `"_mill/plan"`. No Python helper changes.

## Cards

### Card 5: Add Path Setup and replace _mill/ strings in mill-start/SKILL.md

- **Context:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_marker.py`
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. **Add Path Setup sub-step** in the Entry section, after step 3 (load config) and before Phase: Color. The sub-step:
     > **Path Setup.** `cfg` is already loaded. Derive: `status_path = _paths.resolve_task_path(worktree_root, cfg['paths']['status_md'])`. For new discussion file creation (Phase: Discussion File), use `discussion_path = worktree_root / cfg['paths']['discussion_file']` (config-canonical; no compat fallback on write). For reviews: `reviews_dir = worktree_root / cfg['paths']['reviews_dir']`. Use these variables for all subsequent path references.
  2. **Phase: Active** (line 63, prose "The initial `_mill/status.md`..."): update to say "The initial status file (at `status_path`) was written by `mill-spawn`..." — i.e., reference the variable, not the hardcoded path.
  3. **Phase: Discussion File** (line 92, prose "Render ... into `_mill/discussion.md`"): change to "Render ... into `discussion_path`" (which equals `worktree_root / cfg['paths']['discussion_file']`).
  4. **Phase: Discussion File git commit** (line 94, `git -C <worktree> add _mill/discussion.md`): replace `_mill/discussion.md` with `<discussion_path>`.
  5. **Auto-mode NOTE path** (line 36, prose in auto-mode section): the reference `_mill/discussion.md` in the "auto-resolve each NOTE by editing `_mill/discussion.md`" instruction → replace with `<discussion_path>`.
  6. **Auto-mode NOTE commit** (line 36, "single commit covering `_mill/discussion.md` + `_mill/reviews/` + `_mill/status.md`"): replace with `<discussion_path>`, `<reviews_dir>/`, `<status_path>`.
  7. **Auto-mode BLOCKED commit** (line 37, `git -C <worktree> add _mill/status.md`): replace with `<status_path>`.
  8. **Phase: Discussion Review 4b** (line 117, `_mill/discussion.md` directly, `_mill/reviews/<path>`, `_mill/status.md`): replace with `<discussion_path>`, `<reviews_dir>/<path>`, `<status_path>`.
  9. **Phase: Discussion Review 5** (line 119, `git -C <worktree> add _mill/discussion.md`): replace with `<discussion_path>`.
  10. **Phase: Handoff** (line 125, `git -C <worktree> add _mill/status.md`): replace with `<status_path>`.
  11. **Board Discipline section** (line 143): update `_mill/status.md`, `_mill/discussion.md` prose to reference `status_path`, `discussion_path`.
- **Commit:** `fix(mill-start): replace hardcoded _mill/ paths with config-derived variables`

### Card 6: Add Path Setup and replace _mill/ strings in mill-plan/SKILL.md

- **Context:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_plan_dag.py`
  - `plugins/mill/templates/plan-overview.md`
  - `plugins/mill/templates/plan-batch.md`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. **Add Path Setup sub-step** in the Entry section, after step 3 (load config) and before step 4 (read status.md entry branch). The sub-step:
     > **Path Setup.** Derive from config: `status_path = _paths.resolve_task_path(worktree_root, cfg['paths']['status_md'])`. `plan_dir` and `reviews_dir` will be derived during Phase: Plan (writes) or Phase: Plan Review (reads) as appropriate — see those phases for details.
  2. **Entry step 4** (line 19, "Read `_mill/status.md`"): update to "Read `status_path`". The conditions in the entry table (lines 23–24) that mention `_mill/plan/` or `_mill/plan/00-overview.md` as filesystem checks: keep them as filesystem checks but express as "no `plan_dir` dir at worktree root" (using the config-canonical `cfg['paths']['plan_dir']`) in the descriptive prose, not as code — these are matching conditions, not literal path arguments.
  3. **Phase: Plan — "Update `_mill/status.md`" block** (lines 63–69):
     - Remove `status_path = Path("_mill/status.md").resolve()` (now in Path Setup at entry).
     - In the same block, add before the `_status.update_field` line: `plan_dir = worktree_root / cfg['paths']['plan_dir']` (config-canonical; write path).
     - Change `_status.update_field(status_path, "plan", "_mill/plan")` → `_status.update_field(status_path, "plan", cfg['paths']['plan_dir'])`.
     - Change the commit command `git -C <worktree> add _mill/plan/ _mill/status.md` → `git -C <worktree> add <plan_dir> <status_path>`.
  4. **Phase: Plan — DAG self-validate block** (line 61, `plan_dir = Path("_mill/plan/").resolve()`): remove this inline assignment — `plan_dir` is now set in the "Update `_mill/status.md`" block above (or move that assignment earlier if needed to satisfy the validate call ordering). Replace the `plan_dir.glob` call with the `plan_dir` variable.
  5. **Phase: Plan Review — skip block** (line 73, `git -C <worktree> add _mill/plan/`): replace `_mill/plan/` with `<plan_dir>`.
  6. **Phase: Plan Review — all `git -C <worktree> add _mill/plan/ _mill/reviews/ _mill/status.md` occurrences** (lines 119, 121, 137, 146): replace each path segment with the corresponding variable: `<plan_dir>`, `<reviews_dir>` (= `_paths.resolve_task_path(worktree_root, cfg['paths']['reviews_dir'])` — derive this in Phase: Plan Review entry or reuse from the path setup block if you choose to expand it), `<status_path>`.
  7. **Phase: Plan Review — validator-fix commit** (line 101, `git -C <worktree> add _mill/plan/`): replace with `<plan_dir>`.
  8. **Phase: Plan Review — fixer report paths** (lines 121, 137, 143): prose referencing `_mill/reviews/<timestamp>-plan-fix-r<N>.md` → replace with `<reviews_dir>/<timestamp>-plan-fix-r<N>.md`.
  9. **Phase: Plan Review — non-progress and max-rounds commits** (lines 148, 150, `git -C <worktree> add _mill/status.md _mill/reviews/`): replace path literals with variables.
  10. **Board Discipline section** (line 183): update prose to reference path variables.
- **Commit:** `fix(mill-plan): replace hardcoded _mill/ paths with config-derived variables`

## Batch Tests

`verify: null` — SKILL.md edits; no runnable test surface.
