# Discussion: 33 (A) — Working-dir rename + portals redesign + junction cleanup

```yaml
task: 33 (A) — Working-dir rename + portals redesign + junction cleanup
slug: mill-paths-cleanup
status: discussing
parent: main
```

## Problem

Mill's working-state directory has been named `task/` since early development, which is vague and easy to confuse with the user's own task-related files. The portals mechanism, which lets operators navigate active tasks via `<container>/portals/<slug>/`, was redesigned in mid-2025 to route through `wiki/active/<slug>/` — a detour through the wiki that serves no purpose and introduces a dependency between portals and the wiki repo. Several hub junctions have accumulated legacy entries (`.others`, hub-self-portal) that are no longer used or named consistently. Finally, Windows cp1252 terminals crash on the non-ASCII characters (em-dashes, arrows) that appear in mill script output, and `CLAUDE_PLUGIN_ROOT` is not set as a Windows user env var, so it is empty in most Bash subshells.

These ten related issues are consolidated into one task because they all touch the same surface: mill-spawn, mill-merge, mill-cleanup, wiki/config.yaml, CLAUDE.md, and every SKILL.md. A piecemeal approach would require the same files to be touched multiple times.

## Scope

**In:**
- Rename working-state directory `task/` → `_mill/` across all scripts, SKILL.md files, unit tests, integration tests, wiki/config.yaml `paths:` block, templates/wiki-config.yaml, and CLAUDE.md.
- Add compat shim covering all three config-driven paths: a `resolve_task_path(worktree_root, cfg_relative_path)` helper that, given a config path like `_mill/discussion.md`, checks if the `_mill/` target exists; if not but the equivalent `task/` path does, returns the `task/` path with a deprecation log. Callers of `cfg["paths"]["discussion_file"]`, `cfg["paths"]["plan_dir"]`, and `cfg["paths"]["reviews_dir"]` (and `status.md`) go through this helper. Allows all in-flight worktrees to continue through mill-go, review, and mill-merge without a forced `task/` → `_mill/` rename.
- Portals redesign: `portals/<slug>` now points directly at `wts/<slug>/_mill/` (not `wiki/active/<slug>/`). Remove wiki/active mechanism entirely — stop creating `wiki/active/<slug>/task.md`, remove existing `wiki/active/` content from the wiki repo, remove wiki/active from cleanup.
- Hub junction inventory cleanup: drop `.others` (legacy), drop hub-self-portal `portals/<repo>` from mill-setup Phase 3.7, add `.portals` junction (hub-scope and per-worktree) pointing at `<CONTAINER_PATH>/portals/`.
- Update per-worktree `.active` junction target from `<WIKI_PATH>/active/<SLUG>/` to `<CONTAINER_PATH>/portals/<SLUG>/`.
- Mill-merge SKILL.md: add step that clears hub's `.active` junction if it points at the task being merged (handled in mill-cleanup's done-record teardown).
- Drop `tasks.md` hardlink: remove `hardlinks:` block from wiki/config.yaml and templates/wiki-config.yaml; remove `/tasks.md` from `.gitignore` mill-managed block; update mill-setup Phase 4.5b/Phase 8 verification.
- Mill-cleanup extension: orphan-scan of `portals/` — remove any entry `portals/<X>` where X is not an `[active]` slug in Home.md OR the portal target path does not exist. Covers stale hub-self-portals, slugs removed from Home.md without cleanup, and worktrees deleted out-of-band.
- Unicode-in-output cleanup: replace all non-ASCII characters (em-dashes, arrows, etc.) in `print()`/`_log()` output strings across all `plugins/mill/scripts/` files. Add CLAUDE.md rule banning Unicode in stdout/stderr/log output.
- Write `plugins/mill/doc/task-files-contract.md` formalising the invariant: per-task working state is git-tracked on the task branch, never merged to main, never written to the wiki. Pin from mill:workflow and mill:mill-merge SKILL.md.
- Mill-setup Phase 4.7: also set `CLAUDE_PLUGIN_ROOT` as a Windows user env var (alongside PYTHONPATH). Update SKILL.md examples to use `PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(dirname "$PYTHONPATH")}"` as fallback pattern.

**Out:**
- No change to how mill-spawn chooses tasks or writes status.md content.
- No change to the `_paths.py` `resolve_path` / `resolve_wiki_path` / `resolve_active_worktree` APIs (only internal path segment strings change).
- No forced migration of existing in-flight worktrees' `task/` dirs — the compat shim transparently falls back to `task/` for all config-driven paths until the operator renames.
- No change to millpy-migrate-layout.py layout-migration logic for the old→new container-form restructuring.
- No change to the review subsystem (templates, reviewers, LLM providers).
- No change to the wiki sidebar, color assignment, or VS Code integration.
- No change to other plugins (codeguide, weblens).

## Decisions

### task/ → _mill/ rename strategy

- **Decision:** Mechanical string-replace throughout scripts, skills, tests, templates, and docs. Add `resolve_task_path(worktree_root: Path, cfg_relative_path: str) -> Path` to `_paths.py` (or `_status.py`): given a config path beginning with `_mill/`, if `worktree_root / cfg_relative_path` does not exist but the equivalent `task/` path does, return the `task/` path with a `[compat] falling back to task/ for <path>` log line. All callers of the three config-driven paths (`discussion_file`, `plan_dir`, `reviews_dir`) and `status.md` go through this helper. The shim covers all four paths so mill-go, review, and mill-merge all continue to work against in-flight branches.
- **Rationale:** The underscore prefix signals "system-managed" to any reader who opens the worktree. The extended shim (all four paths) ensures no in-flight task breaks at any mill operation boundary, not just mill-merge.
- **Rejected:** Config-key gate (`paths.task_dir`) — adds complexity for a one-time transition. Clean break (no shim) — operational risk during the transition window. Shim for `status.md` only — leaves review and plan operations broken for in-flight tasks.

### portals redesign — target

- **Decision:** `portals/<slug>` → `wts/<slug>/_mill/` directly. Wiki/active mechanism removed entirely: `write_wiki_active_task_md` function deleted, existing `wiki/active/` content removed from the wiki repo, wiki/active cleanup paths removed from millpy-cleanup.py.
- **Rationale:** Wiki involvement in portals was incidental — portals were designed to provide IDE navigation to task working state, not wiki metadata. Routing through `_mill/` directly removes the wiki repo from the critical path for portal creation/teardown.
- **Rejected:** Keep wiki/active as read-only metadata store — no consumer currently reads it for any operational purpose.

### .active junction target after redesign

- **Decision:** Per-worktree `.active` changed from `<WIKI_PATH>/active/<SLUG>/` to `<CONTAINER_PATH>/portals/<SLUG>/`. Hub-scope `.active` (singleton, pointing at last-spawned task) continues to point at `<CONTAINER_PATH>/portals/<SLUG>` (no `<SLUG>` token — set to the specific slug by mill-spawn/claim). Since hub's `.active` is not in wiki/config.yaml junctions but in spawn code, this is handled in `_spawn_core.recreate_active_junction`.
- **Rationale:** Routing through portals keeps the chain consistent: any worktree's `.active` navigates through `portals/<slug>` → `_mill/`, same as the hub's `.active`. Two-hop navigation is fine; the junction semantics are transparent.
- **Rejected:** Remove `.active` from per-worktree junctions — useful for operators who want to navigate from inside a task worktree without knowing the portals path.

### hub junction inventory after redesign

- **Decision:**
  - Drop `.others` from all junction config and code (already absent from wiki/config.yaml; remove from millpy-spawn.py exclude list if still referenced).
  - Drop hub-self-portal: remove Phase 3.7 from mill-setup SKILL.md and `_setup_hub_portal()` / equivalent code. Existing `portals/<repo>` entries cleaned up by mill-cleanup orphan scan.
  - Add `.portals: <CONTAINER_PATH>/portals/` as hub-scope junction (mill-setup creates it). Because `.portals` contains no `<SLUG>` token it is classified hub-scope by the existing filter in `_setup.create_hub_links`, so wiki/config.yaml alone does not propagate it to task worktrees. **Decision: mill-spawn explicitly creates `.portals` in the new task worktree during its junction-setup pass** — the same step that already creates `.wiki` and `.active`. Mill-spawn reads `<CONTAINER_PATH>/portals/` as the target (already available from `container_path`), creates `<worktree_root>/.portals → container_path/portals/`, and logs it alongside the other junctions. No new wiki/config.yaml entry or token type is needed.
  - **Why this mechanism, not a new wiki/config.yaml entry:** Adding a non-slug-scoped but worktree-targeted entry would require extending the scope-filter logic. Explicit creation in mill-spawn's junction pass is simpler and localises the knowledge ("task worktrees need `.portals`") in one place.
- **Rationale:** Clean inventory: `.wiki`, `.active`, `.portals` — three well-named entries, each serving a clear IDE-navigation purpose.
- **Rejected:** Keeping hub-self-portal — it conflates "portals" (task working states) with "main worktree navigation"; the main worktree is navigated via file explorer or the hub itself.

### tasks.md hardlink removal

- **Decision:** Remove `hardlinks:` block from wiki/config.yaml and templates/wiki-config.yaml. Remove `/tasks.md` from `.gitignore` mill-managed block. Update mill-setup Phase 4.5b (hardlink names logic) and Phase 8 verification. Existing `tasks.md` file in hub worktree is left as-is (not actively removed by scripts — the `.gitignore` removal means git will start tracking it; operator can `git rm tasks.md` manually or mill-cleanup can detect and remove it).
- **Rationale:** The hardlink's markdown links are all dead because relative links resolve against hub root, where wiki sibling files are absent. Operators should navigate via `.wiki/Home.md` instead, where links resolve correctly.
- **Rejected:** Fix the dead links — impossible without either rewriting all wiki markdown to use absolute paths or restructuring the wiki repo layout.

### mill-cleanup orphan portal scan

- **Decision:** In `millpy-cleanup.py`, after the existing worktree/slug reconciliation, add a sweep over `<container>/portals/`: a portal entry `portals/<X>` is stale if EITHER (a) `X` is not registered as an `[active]` slug in Home.md, OR (b) the junction target path does not exist. Mark stale entries for removal; honour the `--apply` flag for dry-run vs live.
- **Rationale:** The two-condition oracle is necessary because neither condition alone is sufficient. Target-not-exists misses hub-self-portals (`portals/millhouse` points at a real dir that exists). Slug-vs-Home.md alone misses tasks still listed in Home.md whose worktrees were deleted without mill-cleanup (the portal target is gone but the slug is still `[active]`). The union catches all three failure modes: hub-self-portals, abandoned slugs removed from Home.md, and worktrees deleted out-of-band.
- **Rejected:** Target-not-exists alone — misses hub-self-portals pointing at live dirs. Slug-vs-Home.md alone — misses portals for active slugs whose targets are gone.

### mill-merge .active clearing

- **Decision:** In millpy-cleanup.py's done-record teardown (`_remove_done_record` or `apply_plan`), after removing `portals/<slug>`, check hub `.active` junction: if it resolves to the same target as the removed portal, delete hub `.active`. Mill-merge SKILL.md notes this is handled by mill-cleanup — no new operator step needed.
- **Rationale:** Keeps teardown atomic — mill-cleanup already owns worktree + portal removal; `.active` clearing belongs in the same pass.
- **Rejected:** New operator step in mill-merge SKILL.md — adds cognitive overhead and is error-prone if the operator skips it.

### CLAUDE_PLUGIN_ROOT env var + fallback (strand 10)

- **Decision:** Mill-setup Phase 4.7 sets both `PYTHONPATH` and `CLAUDE_PLUGIN_ROOT` as Windows user env vars, pointing at `<latest_cache>/scripts` and `<latest_cache>` respectively. SKILL.md examples that use `$CLAUDE_PLUGIN_ROOT` add a fallback line: `PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(dirname "$PYTHONPATH")}"` and use `$PLUGIN_ROOT` thereafter.
- **Rationale:** Setting the var in mill-setup means it is available in all subsequent shell sessions. The fallback covers the transition period and CI-style environments where user env vars aren't inherited.
- **Rejected:** Runtime derivation from `python -c "import sys; print(sys.path[0])"` — too fragile; depends on PYTHONPATH already being effective, which is the problem we're solving.

### Unicode output rule + cleanup (strand 8)

- **Decision:** Replace every non-ASCII character in `print()` and `_log()` output strings in `plugins/mill/scripts/` with ASCII equivalents: em-dash (`—`) → ` -- `, right arrow (`→`) → ` -> `, etc. Docstrings and comments may keep them. Add a one-sentence rule to CLAUDE.md's "Conventions worth carrying" block: "**ASCII-only in stdout/stderr/log output.** Windows cp1252 terminals crash on non-ASCII characters in output strings. Docstrings and comments are exempt."
- **Rationale:** The crashes are reproducible (millpy-cleanup.py line 215, millpy-migrate-layout.py lines 118/120/475/487/527/545). The fix is trivial and the scope is bounded.
- **Rejected:** Setting `PYTHONIOENCODING=utf-8` globally — this requires operator action in every shell and doesn't protect against future additions.

### task-files-contract.md (strand 9)

- **Decision:** Create `plugins/mill/doc/task-files-contract.md`. Content: formalises the invariant (per-task state is git-tracked on the task branch, never merged to main, never written to the wiki), lists what files live under `_mill/`, documents the recovery path (archive tags, `git fsck --lost-found`). Pin from mill:workflow SKILL.md (one-sentence pointer) and mill:mill-merge SKILL.md (one-sentence pointer in the "Working state" note).
- **Rationale:** Standalone doc makes the contract citable from multiple skills without duplication. The `doc/` directory establishes a home for similar reference material.
- **Rejected:** Inline into CLAUDE.md — CLAUDE.md is already long; stable contracts belong in separate files linked from it.

## Technical context

**Key files to change:**

- `plugins/mill/scripts/millpy-spawn.py` — portal creation (remove wiki/active, create portals/<slug> → wts/<slug>/_mill/), `.portals` junction creation, `.active` junction update.
- `plugins/mill/scripts/_spawn_core.py` — `write_wiki_active_task_md` (delete), `recreate_active_junction` (update target), `write_initial_status` (path from `task/status.md` → `_mill/status.md`).
- `plugins/mill/scripts/millpy-cleanup.py` — remove wiki_active_dir references (`SlugRecord` field, teardown logic), add portal orphan scan, add `.active` clearing in done-record handler.
- `plugins/mill/scripts/millpy-claim.py` — portal creation uses new target; remove wiki/active write.
- `plugins/mill/scripts/_paths.py` (or `_status.py`) — add `resolve_task_path(worktree_root: Path, cfg_relative_path: str) -> Path` compat helper: if the `_mill/` path doesn't exist but the equivalent `task/` path does, return the `task/` path with a deprecation log. Callers of all four config-driven paths (`discussion_file`, `plan_dir`, `reviews_dir`, `status.md`) go through this.
- `plugins/mill/scripts/_paths.py` — update `"task"` path segment in `resolve_active_hub` and related helpers.
- `plugins/mill/scripts/millpy-abandon.py`, `millpy-implement.py`, `millpy-implement-holistic.py` — update `task/` path segments.
- `plugins/mill/scripts/_review_discussion.py`, `_review_plan.py`, `_review_code.py` — update path segments (already go through `cfg["paths"]`, so mainly `wiki/config.yaml` update propagates).
- `plugins/mill/scripts/_review_common.py` — update path segments.
- `plugins/mill/scripts/millpy-migrate-layout.py` — Unicode fix (8 lines); `task/` reference in docstring/comment update.
- `plugins/mill/scripts/millpy-cleanup.py` — Unicode fix (em-dash lines).
- `plugins/mill/scripts/_setup.py` — remove hardlinks support or leave as no-op when `hardlinks:` block absent.
- `plugins/mill/scripts/_wiki.py` — check for `read_hardlinks` usage (called from `_setup.py`).
- `plugins/mill/scripts/_gitignore.py` — `GLOB_ENTRIES` may need to add `**/_mill/` (currently has `**/.wiki/`, `**/.active/`, `**/.portals/`).
- `plugins/mill/templates/wiki-config.yaml` — remove `hardlinks:` block, update `paths:` to `_mill/`, add `.portals` junction entry, update `.active` target. **Important:** the template's `paths:` block currently uses `active/<SLUG>/` prefixes (e.g. `active/<SLUG>/discussion.md`), not `task/`. A mechanical `task/` → `_mill/` find/replace will silently miss these lines. The plan batch for the template must explicitly rewrite the entire `paths:` block to the new `_mill/` values, not rely on string substitution.
- Wiki `config.yaml` (live) — same changes as template.
- `plugins/mill/skills/mill-setup/SKILL.md` — remove Phase 3.7 hub-self-portal, remove Phase 4.5b hardlink logic, update Phase 8 verification, add CLAUDE_PLUGIN_ROOT to Phase 4.7.
- `plugins/mill/skills/mill-spawn/SKILL.md`, `mill-claim/SKILL.md`, `mill-merge/SKILL.md`, `mill-start/SKILL.md`, `mill-plan/SKILL.md`, `mill-go/SKILL.md`, `mill-autofix/SKILL.md`, `mill-finalize/SKILL.md`, `mill-merge-in/SKILL.md` — replace all `task/` path references with `_mill/`.
- `plugins/mill/skills/git-pr/SKILL.md` — replace `task/` references.
- `plugins/mill/unit_tests/` — update all `"task"` path segment references.
- `plugins/mill/integration_tests/` — same.
- `CLAUDE.md` — update path-invariants block (junction inventory, `_mill/` everywhere), add Unicode-output rule, update `wiki/active` and `tasks.md` references.

**Key helpers to understand before planning:**

- `_junction.py` — `create(target, link_path)`, `remove(link_path)`, `strip_all_in_worktree` — junction-safe deletion prerequisite.
- `_wiki.py` — `read_hardlinks(wiki_path)` reads the `hardlinks:` block; if removed from config, this returns `{}` (no change needed in `_setup.create_hub_links`).
- `_setup.py:create_hub_links` — already handles absent `hardlinks:` block (returns empty list); no code change needed there.
- `_gitignore.py:upsert` — called by mill-setup Phase 4.5b with hardlink names; after removing hardlinks, pass only `GLOB_ENTRIES`.
- `_spawn_core.py:write_initial_status` — writes `task/status.md`; rename to `_mill/status.md`.
- `_status.py` — `append_phase`, `set_blocked`, `read_status` all take a `status_path` argument; callers pass the path returned by `resolve_task_path`. No internal changes to `_status.py` needed.

**Portals chain after redesign:**

```
hub root:
  .active         → container/portals/<last-slug>  → wts/<slug>/_mill/
  .portals        → container/portals/
  .wiki           → container/wiki/

task worktree:
  .active         → container/portals/<this-slug>  → wts/<slug>/_mill/
  .portals        → container/portals/
  .wiki           → container/wiki/
  _mill/          (local, git-tracked, working state)
```

**millpy-cleanup.py SlugRecord after redesign:**

Remove `wiki_active_dir: Path | None` field. The wiki-active-dir teardown logic in `apply_plan` (currently `shutil.rmtree(record.wiki_active_dir)`) is removed. Portal orphan scan is a new post-pass that iterates `container/portals/` independently of the slug-based reconciliation.

**wiki/config.yaml paths section drives all review path resolution.** Updating `task/` → `_mill/` there propagates automatically to `_review_discussion.py`, `_review_plan.py`, `_review_code.py` without touching those files' logic.

**`_mill/` is not `_mill` (no trailing slash).** All path construction must use `"_mill"` as the directory name. The `paths:` block in config becomes:
```yaml
paths:
  discussion_file: _mill/discussion.md
  plan_dir:        _mill/plan/
  reviews_dir:     _mill/reviews/
```

**`.gitignore` GLOB_ENTRIES:** Currently `**/_mill/` is NOT in `_gitignore.GLOB_ENTRIES`. It doesn't need to be — `_mill/` is a git-tracked directory on the task branch, not a gitignored one. The existing `.gitignore` handling for mill manages junction names (`.wiki/`, `.active/`, `.portals/`), not working-state dirs.

**Existing `wiki/active/` content in wiki repo:** Currently has `mill-paths-cleanup/` and `ps1-startup-speedup/` subdirs. These need to be removed from the wiki repo as part of this task: `git -C <wiki> rm -rf active/ && git -C <wiki> commit -m "chore: remove wiki/active (portals redesign)"`. Also remove from `wiki/config.yaml`'s junctions block (`.active` target update).

## Constraints

- **Junctions are never used by scripts.** All path resolution goes through `_paths.py`. Junction target changes (`.active`, `.portals`) only affect IDE/terminal navigation, not script behavior.
- **NTFS junctions + recursive deletion.** Any worktree removal must call `_junction.strip_all_in_worktree` first. This invariant already holds in millpy-cleanup.py; the portal orphan scan must also respect it (junctions in `portals/<slug>` don't recurse into worktrees, but confirm before deleting).
- **Wiki mutations go through `_wiki.write_commit_push` or `git -C <wiki_path>`** — never by changing cwd.
- **`${CLAUDE_PLUGIN_ROOT}` may be empty in Bash subshells.** Scripts invoked via Bash in SKILL.md must use the `PLUGIN_ROOT` fallback pattern.
- **No half-finished renames.** The rename must be atomic across all files in a single commit (or a small set of commits covering logically grouped changes). Leaving `task/` strings in some files while others use `_mill/` will cause confusion mid-batch.
- **Unit tests must pass after each batch.** Run `python plugins/mill/unit_tests/run-all.py` as the verify command for each batch.

## Testing

- **Unit tests for `resolve_task_path` compat shim:** Add tests in `test-paths.py` (or `test-status.py`) covering:
  - `_mill/discussion.md` exists → returns `_mill/` path, no log.
  - `_mill/discussion.md` absent, `task/discussion.md` present → returns `task/` path, emits deprecation log.
  - Neither exists → returns `_mill/` path (no fallback), no log (caller handles missing-file error).
  - Same three cases for `plan_dir` and `reviews_dir`.
- **Unit tests for millpy-cleanup.py orphan portal scan:** Add test cases in `test-cleanup.py` using the combined oracle (stale = not in Home.md active slugs OR target missing):
  - `portals/<slug>` where slug is `[active]` in Home.md AND target exists → not stale.
  - `portals/<slug>` where slug is `[active]` in Home.md but target missing → stale (worktree deleted out-of-band).
  - `portals/<repo>` (hub self-portal) where `repo` is not a slug in Home.md → stale, even if target dir exists.
  - `portals/<slug>` where slug was removed from Home.md → stale.
- **Unit test for millpy-cleanup.py `.active` clearing:** Verify that when a done-record is processed and hub `.active` points at the same portal, `.active` junction is removed.
- **Unit tests for `_setup.py` hardlinks removal:** Verify `create_hub_links` with a config missing the `hardlinks:` block returns `{"junctions": [...], "hardlinks": []}`.
- **TDD candidates:** `resolve_task_path` compat helper, orphan portal scan predicate, `.active` clearing logic.
- **Integration test (manual):** After implementing, run `millpy-spawn.py --dry-run` on a test task and verify portal target is `wts/<slug>/_mill/`, `.portals` junction exists, no wiki/active write.

## Q&A log

- **Q:** How to handle backward compat for in-flight worktrees that have `task/` dirs after the rename? **A:** [auto-pick] Add compat shim in `_status.py`/path resolvers: try `_mill/` first, fall back to `task/` with deprecation log. **Why:** Minimal operational risk; existing branches continue through mill-merge without forced migration.
- **Q:** What should the per-worktree `.active` junction in wiki/config.yaml point to after portals redesign? **A:** [auto-pick] `<CONTAINER_PATH>/portals/<SLUG>/` — routes through the new portal chain. **Why:** Consistent with hub's `.active` semantics; two-hop navigation is transparent to operators.
- **Q:** How to handle the stale `portals/<repo>` (hub self-portal) on existing hubs? **A:** [auto-pick] mill-cleanup orphan scan — portal entry with no matching slug in Home.md is stale. **Why:** mill-cleanup is the sweeper; no separate migration script needed.
- **Q:** What fallback pattern for `CLAUDE_PLUGIN_ROOT` in SKILL.md examples? **A:** [auto-pick] `PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(dirname "$PYTHONPATH")}"`. **Why:** PYTHONPATH points to `<cache>/scripts`; its dirname is the plugin root. Concrete and copy-pasteable.
- **Q:** Should `.portals` junction be hub-scope only or also per-worktree? **A:** [auto-pick] Both hub and per-worktree — as stated in the proposal. **Why:** Per-worktree `.portals` lets operators `cd .portals/<slug>` from inside any task worktree.
- **Q:** What triggers "orphan" in the portal orphan scan? **A:** [auto-pick revised] Combined oracle: stale if slug NOT in Home.md active slugs OR junction target doesn't exist. **Why:** Neither condition alone is sufficient — target-not-exists misses live hub-self-portals; slug-vs-Home.md misses active-but-orphaned worktrees. The union handles all three failure modes.
- **Q:** Where does hub `.active` clearing on merge happen? **A:** [auto-pick] millpy-cleanup.py done-record teardown — after portal removal, clear hub `.active` if it points at that portal. **Why:** Keeps teardown atomic; no new operator step.
- **Q:** Where to place the task-files-contract doc? **A:** [auto-pick] `plugins/mill/doc/task-files-contract.md` (new `doc/` dir). **Why:** Separates stable contract from CLAUDE.md conventions; citable from multiple skills.
- **Q:** Where to add the Unicode-output rule in CLAUDE.md? **A:** [auto-pick] Inline into "Conventions worth carrying" block. **Why:** Collocates with other operational rules implementers read; single-sentence rule doesn't need its own section.
