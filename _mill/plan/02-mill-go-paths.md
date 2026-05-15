# Batch: mill-go-paths

```yaml
task: 55 (A) -- Fix hardcoded _mill/ paths and mill-setup junction/config bugs
batch: mill-go-paths
number: 2
cards: 1
verify: null
depends-on: []
```

## Batch Scope

Fix all hardcoded `_mill/` path strings in `plugins/mill/skills/mill-go/SKILL.md`. The file has ~19 occurrences. Add a "Path Setup" sub-step in the Entry section that derives all path variables from config. Replace every hardcoded `_mill/` string with the corresponding variable — except the cleanliness snapshot path (one occurrence, line 136), which must keep its `_mill/` literal because `millpy-implement.py` writes it unconditionally to `_mill/` and is out of scope. No Python helper changes. No changes to any other file.

## Cards

### Card 2: Add Path Setup and replace _mill/ strings in mill-go/SKILL.md

- **Context:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_config.py`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. **Add step 4.5 "Path Setup"** after step 4 (acquire builder lock) and before step 5 (entry phase gate) in the Entry section. First read mill-go/SKILL.md steps 1–4 to confirm whether `worktree_root` and `cfg` are already assigned. If mill-go's entry steps already load config via any call (e.g., `_review_common.load_config` or `_config.load_config`), reuse that `cfg` and do not reload. If `worktree_root` is not already assigned, set `worktree_root = _paths.resolve_git_root()`. Then derive the path variables:
     ```python
     # If worktree_root not already set in prior steps:
     worktree_root = _paths.resolve_git_root()
     # If cfg not already set in prior steps:
     cfg = _config.load_config(wiki_path, worktree_root)
     # Path derivations (always add these):
     status_path   = _paths.resolve_task_path(worktree_root, cfg['paths']['status_md'])
     plan_dir      = _paths.resolve_task_path(worktree_root, cfg['paths']['plan_dir'])
     overview_path = plan_dir / "00-overview.md"
     reviews_dir   = _paths.resolve_task_path(worktree_root, cfg['paths']['reviews_dir'])
     task_dir      = status_path.parent
     ```
     Follow the block with the note: "Use these variables for all subsequent path references. Exception: the cleanliness snapshot path `_mill/.cleanliness-snapshot-<batch_name>.txt` keeps its `_mill/` literal — `millpy-implement.py` writes it unconditionally to `_mill/` and is out of scope."
  2. **Step 5 (entry phase gate):** Remove the line `status_path = Path("_mill/status.md").resolve()` — it is now set in step 4.5.
  3. **Step 6 (read plan overview):** Remove `overview_path = Path("_mill/plan/00-overview.md").resolve()` and the inline `plan_dir = Path("_mill/plan/").resolve()` expression within the `_plan_dag.validate` call. Replace the `plan_dir` reference in the validate call with the `plan_dir` variable from step 4.5.
  4. **All `git -C <worktree> add _mill/status.md` occurrences** (there are approximately 10, scattered across Prepare, Execute, Resume, Holistic Review, and Handoff sections): replace `_mill/status.md` with `<status_path>`. Preserve the surrounding commit message and context unchanged.
  5. **Crash-recovery scan (line 157):** Replace `Path("_mill/reviews").resolve()` with `reviews_dir`.
  6. **Board Discipline section (near end of file):** Update the prose line that reads `_mill/status.md`, `_mill/reviews/<file>`, and `_mill/plan/<file>` to reference the path variables (`status_path`, `reviews_dir`, `plan_dir`) rather than hardcoded strings.
  7. **Do NOT change** the cleanliness snapshot line (contains `<worktree>/_mill/.cleanliness-snapshot-<batch_name>.txt`). Leave it exactly as-is.
- **Commit:** `fix(mill-go): replace hardcoded _mill/ paths with config-derived variables`

## Batch Tests

`verify: null` — SKILL.md is a markdown instruction file; no runnable test surface. Correctness is verified by the plan reviewer checking that all hardcoded `_mill/` strings (except the cleanliness snapshot) have been replaced and the Path Setup block is present and complete.
