# Batch: skills-docs-claude-md

```yaml
task: 33 (A) -- Working-dir rename + portals redesign + junction cleanup
batch: skills-docs-claude-md
number: 6
cards: 12
verify: null
depends-on: [4]
```

## Batch Scope

Updates all SKILL.md files, CLAUDE.md, and the new task-files-contract.md doc to reflect the canonical `_mill/` working-state directory, revised portal semantics, and the ascii-only output rule. These are documentation-only changes — no Python scripts are touched. Runs in parallel with batch 05 (no shared files).

## Cards

### Card 31: Update `CLAUDE.md`

- **Context:**
  - `CLAUDE.md`
- **Edits:**
  - `CLAUDE.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Update `CLAUDE.md` at the repo root in four areas:
  (1) **Container layout diagram** (the `text` block under "Project shape"): replace `task/` with `_mill/` in the per-worktree listing. Update the junction inventory to show `.wiki`, `.active`, and `.portals` (remove any reference to `.active -> ../../wiki/active/<slug>/` and replace with `.active -> ../../portals/<slug>/`; add `.portals -> ../../portals/`).
  (2) **"Working state is never written to the wiki"** bullet (under Constraints): update the example paths from `task/status.md`, `task/discussion.md`, `task/plan/`, `task/reviews/` to `_mill/status.md`, `_mill/discussion.md`, `_mill/plan/`, `_mill/reviews/`.
  (3) **Path invariants section**: update the bullet "Working state lives in `task/` on the task branch" to say `_mill/`. Update the sentence about mill-merge cleanup (`removes the task/ directory`) to `_mill/`. Update any `task/` occurrences in the path invariants bullet list.
  (4) **Add unicode-output rule** to "Conventions worth carrying": add a new bullet: "**All `print()` and `_log()` output strings use ASCII only.** Em-dash (`—`) -> ` -- `; right-arrow (`->`) -> ` -> `. Docstrings and comments are exempt. Windows cp1252 terminals crash on non-ASCII stdout/stderr."
- **Commit:** `docs(claude-md): update task/ -> _mill/, junction inventory, add unicode output rule`

### Card 32: Create `plugins/mill/doc/task-files-contract.md`

- **Context:**
  - `plugins/mill/scripts/_spawn_core.py`
  - `plugins/mill/scripts/millpy-abandon.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/doc/task-files-contract.md`
- **Deletes:** none
- **Requirements:** Create the file `plugins/mill/doc/task-files-contract.md` with this content (use fenced yaml for frontmatter per convention, not `---` frontmatter):

  ```markdown
  # Per-task working-state contract

  ` ` `yaml
  scope: per-task branch
  owner: mill (spawn, implement, plan, abandon, cleanup)
  ` ` `

  Every task branch carries a `_mill/` subdirectory at the worktree root.
  Scripts write to this directory; the wiki holds only `Home.md` and `config.yaml`.
  mill-merge's cleanup commit removes `_mill/` before squash-merging back to the parent branch.

  ## Files

  | Path | Created by | Purpose |
  |---|---|---|
  | `_mill/status.md` | mill-spawn / mill-claim | Phase timeline, parent branch, slug |
  | `_mill/discussion.md` | mill-start | Problem statement and decisions |
  | `_mill/plan/00-overview.md` | mill-plan | Batch DAG, shared decisions, all files touched |
  | `_mill/plan/NN-<batch-slug>.md` | mill-plan | Per-batch card spec |
  | `_mill/reviews/<YYYYMMDD-HHMMSS>-<scope>.md` | review CLIs | Review output from plan/code review rounds |

  ## Invariants

  - `_mill/` lives on the task branch, never on main.
  - Scripts resolve paths via `_paths.resolve_task_path(worktree_root, "_mill/...")` — never hardcode `_mill/` directly in callers.
  - The compat shim in `_paths.resolve_task_path` transparently redirects `_mill/` lookups to `task/` for worktrees that pre-date this rename.

  ## Legacy

  Before this rename (batch 02 of task 33-A), working state lived in `task/` instead of `_mill/`. The compat shim handles in-flight `task/`-based worktrees automatically; no manual migration is needed.
  ```

  (Remove the extra spaces around backticks in the fenced block above — they are present only to prevent nesting confusion in this plan file.)
- **Commit:** `docs(mill): create task-files-contract.md`

### Card 33: Update `plugins/mill/skills/mill-setup/SKILL.md`

- **Context:**
  - `plugins/mill/skills/mill-setup/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-setup/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Read the full file before editing. Make these structural changes:
  (1) **Remove Phase 3.7** (hub-self-portal creation): mill-setup no longer creates a portal entry for the hub itself — portals are only for task worktrees, created by mill-spawn/mill-claim. Remove the entire Phase 3.7 section.
  (2) **Update Phase 4.5b** (hardlinks in .gitignore): remove any instruction to add hardlink entries to `.gitignore`. The hardlinks section has been removed from the config; if the phase references hardlinks specifically, update it to reflect that the hardlinks block is gone.
  (3) **Add a new step to Phase 4.7** (PYTHONPATH): add an instruction to set `CLAUDE_PLUGIN_ROOT` as a persistent user environment variable (`setx CLAUDE_PLUGIN_ROOT "<plugin-cache-path>"`) alongside the PYTHONPATH setup. Add a note that the variable takes effect in new shell sessions and is required by SKILL.md files for all intra-plugin path references.
  (4) **Update Phase 8 verification**: update any junction or portal verification steps that reference `wiki/active/<slug>/` as a portal target — replace with `wts/<slug>/_mill/`. Update any step that checks for `hardlinks:` in config to note that this block is no longer present. Add a verification step for the `.portals` junction: check that `hub/.portals` exists and resolves to `<container>/portals/`. Add a note: "Operators upgrading a hub from pre-task-33 code may find stale `wiki/active/<slug>/` subdirectories left over from before the portal redesign. These are safe to remove manually with `rmdir /s /q wiki/active/<slug>/` (on Windows) or `rm -rf wiki/active/<slug>/` (on Linux/Mac) after confirming no junction in any worktree points into them. mill-cleanup's orphan portal scan (batch 4) does not cover `wiki/active/` — one-time manual cleanup is sufficient."
  All other phases remain unchanged.
- **Commit:** `docs(mill-setup): remove Phase 3.7, update 4.5b/4.7/Phase 8 for portal redesign`

### Card 34: Update `plugins/mill/skills/mill-spawn/SKILL.md`

- **Context:**
  - `plugins/mill/skills/mill-spawn/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-spawn/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Read the full file before editing. Update every reference to working-state paths:
  (1) Replace all occurrences of `task/status.md`, `task/discussion.md`, `task/plan/`, `task/reviews/` with `_mill/status.md`, `_mill/discussion.md`, `_mill/plan/`, `_mill/reviews/`.
  (2) Update the section describing portal creation: the portal entry `portals/<slug>` now points at `wts/<slug>/_mill/` (not `wiki/active/<slug>/`). Remove or update any mention of `write_wiki_active_task_md` or creating `wiki/active/<slug>/`.
  (3) Update the junction description: `.active` points at `portals/<slug>` (which in turn points at `wts/<slug>/_mill/`); add `.portals` to the list of junctions created in the new worktree.
- **Commit:** `docs(mill-spawn): update task/ -> _mill/, portal and junction descriptions`

### Card 35: Update `plugins/mill/skills/mill-claim/SKILL.md`

- **Context:**
  - `plugins/mill/skills/mill-claim/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-claim/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Apply the same changes as card 34 but to `mill-claim/SKILL.md`:
  (1) `task/` -> `_mill/` in all working-state path references.
  (2) Portal creation description: `portals/<slug>` points at the hub's `_mill/` directory (since claim uses in-place mode, the hub IS the worktree, so `portals/<slug>` -> `hub/_mill/`).
  (3) Junction list: include `.portals` alongside `.wiki` and `.active`.
  (4) Remove any mention of `write_wiki_active_task_md` or `wiki/active/<slug>/` creation.
- **Commit:** `docs(mill-claim): update task/ -> _mill/, portal and junction descriptions`

### Card 36: Update `plugins/mill/skills/mill-plan/SKILL.md`

- **Context:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Read the full file. Find every operational instruction that references `task/status.md`, `task/plan/`, or `task/reviews/` and update to `_mill/status.md`, `_mill/plan/`, `_mill/reviews/`. Key locations: status update steps ("update `task/status.md`"), plan file creation steps ("render into `task/plan/00-overview.md`"), commit instructions (`git add task/plan/ task/status.md`), re-entry logic checks ("plan state on disk (`task/plan/00-overview.md`)"). Replace all; do not leave partial `task/` references.
- **Commit:** `docs(mill-plan): update task/ -> _mill/ in all path references`

### Card 37: Update `plugins/mill/skills/mill-go/SKILL.md`

- **Context:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Read the file. Replace all operational path references: `task/status.md` -> `_mill/status.md`, `task/plan/` -> `_mill/plan/`, `task/reviews/` -> `_mill/reviews/`. Update any `git add task/` reference in commit instructions to `git add _mill/`. Leave model names, API references, and non-path prose untouched.
- **Commit:** `docs(mill-go): update task/ -> _mill/ in path references`

### Card 38: Update `plugins/mill/skills/mill-start/SKILL.md` and `plugins/mill/skills/mill-resume/SKILL.md`

- **Context:**
  - `plugins/mill/skills/mill-start/SKILL.md`
  - `plugins/mill/skills/mill-resume/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
  - `plugins/mill/skills/mill-resume/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In both files, replace `task/status.md` -> `_mill/status.md`, `task/discussion.md` -> `_mill/discussion.md`, `task/plan/` -> `_mill/plan/`, `task/reviews/` -> `_mill/reviews/`. Update any git commit instructions that stage `task/` paths. If either file mentions the wiki active directory or portal targets, update those to reflect the batch 03 portal redesign.
- **Commit:** `docs(mill-start,mill-resume): update task/ -> _mill/`

### Card 39: Update `plugins/mill/skills/mill-autofix/SKILL.md` and `plugins/mill/skills/mill-finalize/SKILL.md`

- **Context:**
  - `plugins/mill/skills/mill-autofix/SKILL.md`
  - `plugins/mill/skills/mill-finalize/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-autofix/SKILL.md`
  - `plugins/mill/skills/mill-finalize/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Same substitution as card 38: replace `task/` path references with `_mill/` throughout both files' operational instructions and git staging commands. Leave non-path prose untouched.
- **Commit:** `docs(mill-autofix,mill-finalize): update task/ -> _mill/`

### Card 40: Update `plugins/mill/skills/mill-merge/SKILL.md` and `plugins/mill/skills/mill-merge-in/SKILL.md`

- **Context:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Same substitution: `task/` -> `_mill/` in all working-state path references in both files. Note: `mill-merge` includes a cleanup commit that removes the working-state directory before squash-merging — update the instruction to say "remove `_mill/`" (was "remove `task/`"). Update any `git rm -r task/` instruction to `git rm -r _mill/`.
- **Commit:** `docs(mill-merge,mill-merge-in): update task/ -> _mill/`

### Card 41: Update `plugins/mill/skills/git-pr/SKILL.md` and `plugins/mill/skills/workflow/SKILL.md`

- **Context:**
  - `plugins/mill/skills/git-pr/SKILL.md`
  - `plugins/mill/skills/workflow/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/git-pr/SKILL.md`
  - `plugins/mill/skills/workflow/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Replace any `task/` working-state path references with `_mill/` in both files. If `workflow/SKILL.md` contains a high-level overview of the working-state directory layout, update it to say `_mill/`. Leave non-path prose unchanged.
- **Commit:** `docs(git-pr,workflow): update task/ -> _mill/`

### Card 42: Final cross-skill consistency pass — ascii-only rule in skills

- **Context:**
  - `plugins/mill/skills/mill-spawn/SKILL.md`
  - `plugins/mill/skills/mill-go/SKILL.md`
  - `plugins/mill/skills/workflow/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-spawn/SKILL.md`
  - `plugins/mill/skills/mill-go/SKILL.md`
  - `plugins/mill/skills/workflow/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Scan all three SKILL.md files for any instruction that tells the implementer or agent to write output strings. If any instruction models output with an em-dash (`—`) or right-arrow (`→`) in a string that will ultimately go to `print()` or `_log()`, update the example output to use ` -- ` or ` -> ` instead. This is a guard against skill instructions inadvertently training agents to re-introduce unicode in output strings. Docstring and comment examples in skill instructions are exempt; only examples of actual print output strings need the ASCII treatment.
- **Commit:** `docs(skills): enforce ascii-only output examples in spawn, go, workflow SKILL.md`

## Batch Tests

No automated test suite for documentation. After implementing all 12 cards, perform a manual sanity check: search for `task/status.md`, `task/plan/`, `task/reviews/`, and `task/discussion.md` in `plugins/mill/skills/` and `CLAUDE.md` — none should appear in operational instructions (only in comments about legacy or the compat shim). Search for `write_wiki_active_task_md` — should appear nowhere. Search for `wiki/active/<slug>` as a portal target — should appear nowhere.
