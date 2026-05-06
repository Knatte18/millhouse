# Batch: Skills and documentation

```yaml
task: Restructure hub junction layout
batch: Skills and documentation
number: 4
cards: 5
verify: null
depends-on: [1, 2]
```

## Batch Scope

Update all SKILL.md files and `CLAUDE.md` to reflect the new junction names (`.wiki`, `.portals`), the new `task/` working-state location (`task/status.md`, `task/discussion.md`, `task/plan/`, `task/reviews/`), and the simplified `_gitignore.upsert` call. Pure documentation batch; no production code changes.

## Cards

### Card 13: `CLAUDE.md` — layout diagram and path invariants

- **Context:**
  - `plugins/mill/skills/mill-setup/SKILL.md`
  - `plugins/mill/skills/mill-spawn/SKILL.md`
- **Edits:**
  - `CLAUDE.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. In the container layout diagram (the `text` block starting with `c:/Code/millhouse/`): in the `portals/` section, change the per-slug entry from `<slug>    -> ../wts/<slug>` to `<slug>    -> ../wiki/active/<slug>/` (portal junctions now point to the wiki state dir, not the worktree). Also update the `millhouse -> ../wts/millhouse` entry to reflect that the main worktree portal is unchanged. Add `.wiki -> ../../wiki/` and `.portals -> ../../wiki/active/<slug>/` entries inside the `<slug>/` worktree section (if not already present from the inner-worktree update).
  2. In the inner-worktree layout diagram (the block starting with `c:/Code/millhouse/wts/<slug>/`): add `task/` subdirectory with its contents (`status.md`, `discussion.md`, `plan/`, `reviews/`); update `.others` → `.portals`; update `.millhouse/wiki` → `.wiki`.
  3. In `## Constraints`: update "Junctions and hardlinks are NEVER used by scripts" to list `.wiki`, `.portals`, `.active` (replacing `.others/`, `.active/`, `.millhouse/wiki`).
  4. In `## Path invariants`:
     - Replace "`Junctions are IDE/terminal convenience only. Scripts MUST resolve to the real wiki repo via `_paths.resolve_wiki_path(git_toplevel)`, never by treating `.millhouse/wiki` (or any junction) as a path`" — change `.millhouse/wiki` to `.wiki`.
     - In the "NTFS junctions are followed by `rmdir /s`…" bullet, update the list of junctions to strip: "`.wiki`, `.portals`, `.active`, plus any future entries".
     - Remove the last bullet about "Future `.wiki` junction (introduced by `rename-hub-junctions`)…" entirely — it is now implemented.
  5. In `## Working state lives on the task branch` (or wherever `status.md`, `discussion.md`, `plan/`, `reviews/` are described at worktree root): update all four paths to their `task/` locations.
- **Commit:** `docs(CLAUDE.md): new junction names, task/ working-state dir, remove future-work note`

### Card 14: `mill-setup/SKILL.md` + `mill-spawn/SKILL.md` — infrastructure skills

- **Context:**
  - `plugins/mill/scripts/_gitignore.py`
  - `plugins/mill/scripts/millpy-spawn.py`
  - `plugins/mill/scripts/_spawn_core.py`
- **Edits:**
  - `plugins/mill/skills/mill-setup/SKILL.md`
  - `plugins/mill/skills/mill-spawn/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  **mill-setup/SKILL.md:**
  1. Phase 4.5b: replace the inline Python snippet that calls `_gitignore.upsert_split` with one that calls `_gitignore.upsert`. Keep `_wiki.read_hardlinks` to cover hardlink names (e.g. `tasks.md`) which are regular files from git's perspective and must remain gitignored:
     ```python
     from pathlib import Path
     import _wiki, _gitignore
     hub_gi = Path(r'<hub-gitignore>').resolve()
     wiki = Path(r'<wiki-dir>').resolve()
     hardlink_names = [f"/{name}" for name in _wiki.read_hardlinks(wiki).keys()]
     changed = _gitignore.upsert(hub_gi, _gitignore.GLOB_ENTRIES + hardlink_names)
     print('hub .gitignore:', 'updated' if changed else 'already up to date')
     ```
     Note: `_gitignore.upsert` is introduced by batch 01 (batch 04 depends on batch 01). The `ANCHORED_ENTRIES` constant and `upsert_split` function are gone; hardlink names are now passed as anchored patterns (`/tasks.md` etc.) directly in the combined list alongside `GLOB_ENTRIES`. Remove the `repo_gi` / two-path logic and the `repo_changed` / `hub_changed` variables.
  2. Update Phase 4.5b prose: replace "split across two files" description with single-file description. Remove "When different, glob entries go to repo_root_gitignore…" text.
  3. Update any **reference** in the SKILL.md (diagrams, prose bullets, "When to invoke" bullets) that mentions `.millhouse/wiki`, `.others`, or `.active` junction names: replace with `.wiki` and `.portals`. This includes the prose "When to invoke" bullet `"When .millhouse/wiki junction is missing or broken"` → `"When .wiki junction is missing or broken"`.

  **mill-spawn/SKILL.md:**
  4. Update the description paragraph to include: "creates `wiki/active/<slug>/task.md`, creates a portal entry `container/portals/<slug>` pointing to `wiki/active/<slug>/`, creates `.wiki` and `.portals` junctions in the new worktree, and updates the hub's `.active` junction."
  5. Update any **reference** in the SKILL.md (bullet lists, description paragraphs) that mentions `status.md` at root, update to `task/status.md`. Specifically: the description paragraph ends with "writes the initial `status.md`" — change to "writes the initial `task/status.md`".
- **Commit:** `docs(mill-setup/spawn): upsert API; new junction names; task/status.md path`

### Card 15: `mill-start/SKILL.md` + `mill-plan/SKILL.md` + `mill-merge-in/SKILL.md`

- **Context:**
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
  - `plugins/mill/skills/mill-plan/SKILL.md`
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  **mill-start/SKILL.md:**
  1. All occurrences of `status.md` at worktree root → `task/status.md`.
  2. All occurrences of `discussion.md` at worktree root → `task/discussion.md`.
  3. `git add discussion.md` in the commit step → `git add task/discussion.md`.
  4. `git add status.md` → `git add task/status.md`.

  **mill-plan/SKILL.md:**
  1. All occurrences of `discussion.md` at worktree root → `task/discussion.md`. (Specifically: `Read 'discussion.md' at the worktree root` → `Read 'task/discussion.md'`.)
  2. All occurrences of bare `plan/` (as a worktree-root path) → `task/plan/`.
  3. All occurrences of bare `reviews/` (as a worktree-root path) → `task/reviews/`.
  4. All occurrences of `status.md` at worktree root → `task/status.md`.
  5. All git add commands: `git ... add plan/ reviews/ status.md` → `git ... add task/plan/ task/reviews/ task/status.md` (and similar). Update every git add/commit command in the skill to use the `task/` paths.
  6. The `status_path` variable references throughout the skill: `status_path` = `Path("task/status.md")`.
  7. The `plan_dir` and paths like `plan/00-overview.md` → `task/plan/00-overview.md`.

  **mill-merge-in/SKILL.md:**
  1. Line ~14: `_parent_branch.resolve(status_path, ...)` where `status_path` references `status.md` → update `status_path` to `Path("task/status.md").resolve()`.
  2. Line ~55: `plan_dir = <WIKI_PATH>/active/<slug>/plan/` → `plan_dir = Path("task/plan/").resolve()`. Working state is now on the task branch in `task/`, not in the wiki.
- **Commit:** `docs(mill-start/plan/merge-in): task/ paths for working state`

### Card 16: `mill-go/SKILL.md` — builder status and plan paths

- **Context:**
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_plan_dag.py`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. All `status_path = Path("status.md").resolve()` → `status_path = Path("task/status.md").resolve()`.
  2. All `plan/00-overview.md` references → `task/plan/00-overview.md`.
  3. All `plan_dir.glob(...)` references → `task/plan/`.
  4. All `reviews/` references (for review file paths) → `task/reviews/`.
  5. All `git ... add status.md` commands → `git ... add task/status.md`.
  6. All `git ... add status.md <review_file_path>` → `git ... add task/status.md <review_file_path>` (the review file paths themselves already include the `task/reviews/` prefix if they follow the pattern, or update them explicitly).
  7. The line "status.md, reviews/<file>, and plan/<file> writes are committed on the **task branch**" in the Board discipline section → update to reference `task/status.md`, `task/reviews/`, `task/plan/`.
- **Commit:** `docs(mill-go): task/ paths for status, plan, reviews`

### Card 17: `mill-merge/SKILL.md` — teardown paths and junction names

- **Context:**
  - `plugins/mill/scripts/_worktree.py`
  - `plugins/mill/scripts/_junction.py`
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. Step 5 (status_path line): `status_path` is `git_root / "status.md"` in the Entry section (line ~37) → `git_root / "task" / "status.md"`.
  2. Step 4 (Cleanup commit): `git rm -r reviews/ discussion.md plan/ status.md` → `git rm -r task/`. Single-path cleanup removes the entire `task/` directory which contains all four artefacts.
  3. Step 8 (Drop the worktree — description list inside `_worktree.remove_safe` prose): update junction names: `.millhouse/wiki`, `.others`, `.active` → `.wiki`, `.portals`. The inline Python snippet that calls `_worktree.remove_safe` does not change (it reads junctions from the wiki config dynamically).
  4. Step 10 (Legacy wiki cleanup): this step is now the normal cleanup path (not legacy). Rename heading from "Legacy wiki cleanup (conditional)" to "Remove wiki active directory". Update prose to show it is called unconditionally on merge, but preserve the existence guard around the `shutil.rmtree` call — e.g. `if (wiki_path / "active" / slug).exists(): shutil.rmtree(...)`. This is not conditional-legacy logic; it is a defensive guard against racing or partially-migrated states. The heading and surrounding prose should convey "always attempt" while the code uses the guard to avoid `FileNotFoundError`.
  5. Verify after teardown section: update paths listed (`<container>/portals/<slug>` etc.) to remain correct — the portals entry is still removed the same way.
  6. Board discipline section: `status.md`, `discussion.md`, `plan/`, `reviews/` → `task/status.md`, `task/discussion.md`, `task/plan/`, `task/reviews/`. Also update the cleanup commit note ("The cleanup commit removes it from the branch tip").
- **Commit:** `docs(mill-merge): task/ cleanup; .wiki/.portals junction names; wiki active dir is normal not legacy`

## Batch Tests

No runnable verification — this is a pure documentation batch. Review that all SKILL.md files consistently use `task/` paths and the new junction names before approving.
