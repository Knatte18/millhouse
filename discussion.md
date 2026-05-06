# Discussion: Restructure hub junction layout

```yaml
task: Restructure hub junction layout
slug: rename-hub-junctions
status: discussing
parent: main
```

## Problem

The current junction layout has several usability and correctness problems. `.others` is an opaque name. The wiki junction is buried under `.millhouse/wiki` rather than at the worktree root where it would be immediately visible in the IDE sidebar. `.active` is created in every task worktree, making it self-referential (the junction points back through `portals/<slug>` to the same directory it lives in — infinite recursion with no value). Working state (`status.md`, `discussion.md`, `plan/`, `reviews/`) is scattered at the worktree root, cluttering it alongside repo files. The `.gitignore` managed block uses two files and a mix of glob and anchored entries, which breaks for external repos where mill is installed as a plugin.

The rename is also the right moment to change `.portals` semantics so that it gives direct navigation to the wiki state for the current task rather than to the container portals directory (which is better accessed via `wts/` directly).

## Scope

**In:**
- Rename `.others` → `.portals` everywhere (config.yaml, `_gitignore.py`, `_junction.py`, `_worktree.py`, all SKILL.md files, `CLAUDE.md`).
- Move `.millhouse/wiki` junction to `.wiki` at worktree cwd root (config.yaml, all references).
- Change `.portals` target in task worktrees from `<CONTAINER_PATH>/portals/` → `<WIKI_PATH>/active/<SLUG>/`.
- Change container `portals/<slug>` entries to target `wiki/active/<slug>/` instead of `wts/<slug>`.
- Make `.active` hub-only: remove from `config.yaml` junctions block; mill-spawn and mill-claim create it explicitly in the hub worktree.
- Create `wiki/active/<slug>/task.md` in mill-spawn (minimal file with slug, title, created-at).
- Clean up `wiki/active/<slug>/` in mill-merge and mill-cleanup.
- Consolidate working state into `task/` subdirectory at worktree root; update every consumer.
- Simplify `.gitignore` managed block to glob-only entries; simplify `upsert_split` to `upsert`.
- Add a migration step to `millpy-migrate-layout.py`.
- Update all SKILL.md files that reference old paths or junction names.
- Update `CLAUDE.md` layout diagrams and path invariants.
- Update unit tests for changed behaviour.

**Out:**
- Container directory structure (`wts/`, `portals/`, `wiki/` at container level) — unchanged.
- Mill-go / mill-plan / mill-receiving-review orchestration logic — path references updated, no logic change.
- Plugin manifest format — unchanged.
- Cross-worktree navigation shortcut (`.others/<slug>` → sibling worktree) — intentionally removed; `wts/<slug>` is the canonical path.

## Decisions

### `.portals` target semantics

- **Decision:** In a task worktree, `.portals` → `wiki/active/<slug>/` (the wiki state directory for that specific task). In the hub worktree (no SLUG), `.portals` is not created (token-scope filter skips it). The container `portals/<slug>` entries also change target from `wts/<slug>` → `wiki/active/<slug>/`.
- **Rationale:** Gives direct IDE/terminal navigation to the wiki face of the current task. The old semantics (`.others` → the full container portals dir) let you navigate to sibling worktrees, but `wts/<slug>` is a cleaner path for that and does not require a junction indirection.
- **Rejected:** Keeping `.portals` as a pointer to the container portals directory (would just be a name change, loses the opportunity to give useful task-scoped navigation).

### `.active` placement — hub-only

- **Decision:** `.active` is created only in the hub worktree (main worktree). It is removed from `wiki/config.yaml`'s `junctions:` block entirely. Mill-spawn and mill-claim both call a hub-side helper (extend/reuse `_spawn_core.recreate_active_junction`) after creating/claiming a task. In the hub `.active` → `container/portals/<slug>` → `wiki/active/<slug>/`.
- **Rationale:** `.active` in a task worktree is self-referential (routes back to itself). Hub-only makes it a useful "jump to current task's wiki state" shortcut from the main worktree.
- **Rejected:** Keeping `.active` in task worktrees with a new non-self-referential target — would require a new config flag and more complex token logic; hub-only is simpler.

### `.active` removed from `config.yaml` junctions block

- **Decision:** Do not add a "hub-only" concept to the config format. Instead, remove `.active` from `wiki/config.yaml`'s `junctions:` block entirely and have mill-spawn and mill-claim call a dedicated helper to create/update it in the hub.
- **Rationale:** Adding a `hub_only: true` or `scope:` flag to config.yaml is added complexity with one use-case. Explicit calls in spawn and claim are readable and testable.
- **Rejected:** New `hub_only:` config flag — over-engineered for a single entry.

### `wiki/active/<slug>/` contents

- **Decision:** Mill-spawn creates `wiki/active/<slug>/task.md` with three fields: `slug`, `title`, and `created_at` (ISO-8601 UTC). This directory serves as the junction target for both the task's `.portals` and the container's `portals/<slug>` entry. Mill-merge and mill-cleanup remove the directory (or move it to `wiki/archive/<slug>/` — see separate archive decision below).
- **Archive sub-decision:** Mill-merge removes the directory entirely (does not archive to `wiki/archive/`). The `archive/<slug>` git tag on the task branch is the authoritative archive. A `wiki/archive/` directory would duplicate that.
- **Rationale:** A `task.md` file makes the directory useful when navigated to. An empty directory is valid as a junction target but gives the operator nothing to read.
- **Rejected:** Copying `proposal-<slug>.md` there — creates a stale duplicate to maintain.

### Task folder `task/` — consolidate working state

- **Decision:** Working state (`status.md`, `discussion.md`, `plan/`, `reviews/`) moves from the worktree root to `task/` (a visible, tracked subdirectory at worktree root). Mill-spawn writes `task/status.md`; mill-start writes `task/discussion.md`; mill-plan writes `task/plan/`; mill-go writes `task/reviews/`. Mill-merge's cleanup commit removes `task/` entirely.
- **Rationale:** The worktree root currently mixes repo files (CLAUDE.md, plugins/, SKILLS.md, specs/) with ephemeral task metadata. A named folder isolates this, makes `git status` cleaner, and groups task artefacts visibly. `task/` is visible (not `.task/`) because it is the one non-infrastructure thing at root — making it visible helps the operator find it, not hide it.
- **All path updates:** Every consumer that currently uses `Path("status.md")`, `Path("discussion.md")`, `Path("plan/")`, or `Path("reviews/")` relative to the worktree root must be updated to `Path("task/status.md")`, etc. This covers: `_spawn_core.write_initial_status`, mill-start skill, mill-plan skill, mill-go skill, mill-merge skill, mill-merge-in skill, `_parent_branch.py`, `_status.py` docstrings, `CLAUDE.md`, and test fixtures.
- **Rejected:** `.task/` (hidden) — the only non-infrastructure thing at root should be visible, not buried.
- **Rejected:** Deferring to a separate task — migration cost is the same, and this PR already touches all the relevant files.

### `.gitignore` managed block simplification

- **Decision:** `GLOB_ENTRIES` becomes `["**/.millhouse/", "**/.scratch/", "**/.portals/", "**/.wiki/", "**/.active/"]`. `ANCHORED_ENTRIES` is removed from `_gitignore.py` entirely. `upsert_split` is replaced by a single-path `upsert(gitignore_path, glob_entries)` function. The `GLOB_ENTRIES` list covers all junctions at any depth with globs — no anchored entries needed.
- `**/wts/`, `**/portals/`, `**/plugins/*/uv.lock` are removed. These were in the managed block as carry-overs from the initial migration; the container-level `wts/` and `portals/` are outside any repo root, and `uv.lock` tracking is the dev's responsibility.
- **Rationale:** Globe-only means a single `upsert` call works for any repo layout (repo-root hub, subdirectory hub, external plugin consumer). Anchored entries break when the hub is not the repo root. `upsert_split` with two files only existed to separate glob vs anchored concerns — removing anchored entries eliminates the reason for splitting.
- **Rejected:** Keeping anchored entries for `.wiki` and `.active` — breaks external plugin consumers whose hub is not at the repo root.

### Migration approach

- **Decision:** Extend `millpy-migrate-layout.py` with a new `--step rename-junctions` sub-command. The step: (1) strips old junctions in each found worktree (`_junction.strip_all_in_worktree`), (2) updates each worktree's `portals/<slug>` container entry target to `wiki/active/<slug>/`, (3) creates `wiki/active/<slug>/` with `task.md` for each active slug found, (4) recreates junctions under new names via `_setup.create_hub_links`, (5) for each task worktree: verify clean working tree (`git status --porcelain`) before moving files — if dirty, skip that worktree, emit a warning, continue with remaining; at end, print a summary of skipped worktrees for manual follow-up; if clean, move `status.md`, `discussion.md`, `plan/`, `reviews/` into `task/` via `git mv` and commit on the task branch, (6) rewrites the `.gitignore` managed block in the hub. Hub `.active` is NOT recreated — left absent; the next `mill-claim` or `mill-spawn` will create it correctly. Dry-run mode required. Idempotent (safe to re-run).
- **Rationale:** The existing migration script already has logging, dry-run, and safeguard scaffolding. A new standalone script would duplicate all of that.
- **Rejected:** Mill-setup re-run alone — mill-setup only operates on the hub, not on task worktrees. Existing task worktrees would keep old layout.

## Technical context

### `wiki/config.yaml` (checked into wiki repo)

Current junctions block:
```yaml
junctions:
  .millhouse/wiki: <WIKI_PATH>
  .others: <CONTAINER_PATH>/portals/
  .active: <CONTAINER_PATH>/portals/<SLUG>/
```

New junctions block:
```yaml
junctions:
  .wiki: <WIKI_PATH>
  .portals: <WIKI_PATH>/active/<SLUG>/
```

`.active` is removed from config — created explicitly by spawn/claim in hub.

### `plugins/mill/scripts/_gitignore.py`

- `GLOB_ENTRIES`: `["**/.millhouse/", "**/.scratch/", "**/.portals/", "**/.wiki/", "**/.active/"]`
- `ANCHORED_ENTRIES` constant: deleted.
- `upsert_split(repo_root, hub, glob_entries, anchored_entries)` replaced by `upsert(gitignore_path, glob_entries)` — single-file, single call.
- `render_block` simplified: no `anchored_entries` parameter.
- Update the one caller (`millpy-setup.py` Phase 4.5b) to call `upsert` with the new signature.

### `plugins/mill/scripts/millpy-spawn.py`

Three new responsibilities:
1. Create `wiki/active/<slug>/` directory with `task.md` (slug, title, created_at). Commit+push in wiki.
2. Change container portals entry creation: `_junction.create(target=wiki_path / "active" / slug, link_path=container_path / "portals" / slug)` — was `wts/<slug>`.
3. After creating the task worktree, call hub-side `.active` update (see `_spawn_core.recreate_active_junction`) on the HUB root rather than on the new task worktree.
4. In `create_hub_links` call on the new worktree — the new config.yaml no longer has `.active`, so it will not be created there. `.portals` will be created pointing to `wiki/active/<slug>/`.

Mill-merge teardown: after removing `portals/<slug>` and `wiki/active/<slug>/`, also remove hub `.active` junction (`_junction.remove(hub_root / ".active")`). A dangling junction (pointing to removed targets) is confusing to operators; explicit removal is cleaner. The next spawn/claim recreates it.

Mill-spawn creates `wiki/active/` with `mkdir(parents=True, exist_ok=True)` before creating the slug subdirectory — handles fresh wiki clones with no prior tasks.

Also: `write_initial_status` path changes from `worktree_path / "status.md"` to `worktree_path / "task" / "status.md"` (see `_spawn_core`).

### `plugins/mill/scripts/_spawn_core.py`

- `write_initial_status`: change `status_abs = worktree_path / "status.md"` → `worktree_path / "task" / "status.md"`. Create `task/` dir before writing.
- `recreate_active_junction`: receives `hub_root: Path` parameter. The junction is placed at `hub_root / ".active"` pointing to `container_path / "portals" / slug`. Currently places it at `mill_dir.parent / ".active"` — needs to accept hub root explicitly for the mill-spawn call.
- New `write_wiki_active_task_md(wiki_path, slug, title, ts)` helper (or inline in spawn): creates `wiki/active/<slug>/` and writes `task.md`.

### `plugins/mill/scripts/_gitignore.py` and callers

- `millpy-setup.py` (Phase 4.5b): call `_gitignore.upsert(hub_gitignore_path, _gitignore.GLOB_ENTRIES)` — single path, no split.

### `plugins/mill/scripts/_junction.py`

- Update docstrings: `.millhouse/wiki` → `.wiki`, `.others` → `.portals`.
- No logic changes needed; `strip_all_in_worktree` reads from junctions_cfg keys (which now come from config.yaml), so it self-updates.

### `plugins/mill/scripts/_worktree.py`

- Update docstring mentioning `.others` → `.portals`.

### `plugins/mill/scripts/millpy-cleanup.py`

- Add cleanup of `wiki/active/<slug>/` directory for each slug being cleaned up (alongside the `portals/<slug>` entry removal).
- Remove hub `.active` junction when the last portal entry is removed (i.e., no active tasks remain). If other tasks remain, leave `.active` pointing to whatever is current — the next claim/spawn will update it.
- Update any docstrings/comments referencing `.others` or `.millhouse/wiki`.

### `plugins/mill/scripts/millpy-claim.py`

- `recreate_active_junction` call: pass `hub_root` (same directory since claim runs in hub) — verify signature matches updated `_spawn_core.recreate_active_junction`.

### `plugins/mill/scripts/millpy-migrate-layout.py`

- New `--step rename-junctions` sub-command. Steps in order:
  1. Discover all active task worktrees (scan `container/wts/`, confirm `.millhouse/active.slug.md` present).
  2. For each task worktree: strip junctions via `_junction.strip_all_in_worktree`; remove old `portals/<slug>` entry; create `wiki/active/<slug>/task.md`; create new `portals/<slug>` → `wiki/active/<slug>/`; recreate junctions via `_setup.create_hub_links` (new config); move `status.md`, `discussion.md`, `plan/`, `reviews/` into `task/` and commit on task branch.
  3. For hub worktree: strip old junctions; recreate via `_setup.create_hub_links`; update `.gitignore` managed block. Do NOT recreate `.active` — leave it absent. The next `mill-claim` or `mill-spawn` will create it correctly against the new layout. No recency heuristic is needed.

### SKILL.md files to update

All path references from root to `task/` subdirectory, and junction name updates:

| File | Changes |
|---|---|
| `mill-start/SKILL.md` | `discussion.md` → `task/discussion.md`; `status.md` → `task/status.md`; git add paths |
| `mill-plan/SKILL.md` | `discussion.md` → `task/discussion.md`; `plan/` → `task/plan/`; `reviews/` → `task/reviews/`; `status.md` → `task/status.md` |
| `mill-go/SKILL.md` | `status_path = Path("task/status.md").resolve()`; `plan/00-overview.md` → `task/plan/00-overview.md`; `reviews/` → `task/reviews/` |
| `mill-merge/SKILL.md` | cleanup commit: `git rm -r task/`; step 5 status_path; `.millhouse/wiki` → `.wiki`; `.others` → `.portals` |
| `mill-merge-in/SKILL.md` | `status.md` → `task/status.md` |
| `mill-setup/SKILL.md` | junction layout diagram updated |
| `mill-spawn/SKILL.md` | update description: wiki active dir creation, portal target change, hub `.active` update; update status path to `task/status.md` |
| `mill-receiving-review/SKILL.md` | if any status_path references |

### `CLAUDE.md`

- Container layout diagram: remove `.others`, add `.wiki`, `.portals`; show `task/` folder inside worktree.
- Path invariants section: update `.millhouse/wiki` → `.wiki`; update "scripts must strip junctions" list.
- Future `.wiki` junction note (last bullet): mark as implemented, remove "introduced by rename-hub-junctions" qualifier.

### `plugins/mill/unit_tests/`

- `test-setup-hub-links.py`: update `FULL_CONFIG` fixture (`.millhouse/wiki` → `.wiki`, `.others` → `.portals`, remove `.active`); update assertions for new junction names; add test: hub-only tokens (no SLUG) should produce `.wiki` only, not `.portals`.
- `test-gitignore-phase.py` (or `test-gitignore.py` if it exists): update expected `GLOB_ENTRIES`; update to call `upsert` not `upsert_split`; verify `ANCHORED_ENTRIES` no longer exists.
- `test-millpy-spawn.py`: update portals entry assertion (target is now `wiki/active/<slug>/`); verify `.active` is NOT created in task worktree; verify hub's `.active` IS updated; verify `task/status.md` exists not `status.md` at root; verify `wiki/active/<slug>/task.md` created.
- `test-spawn-core.py`: update `write_initial_status` assertion to `task/status.md`.

## Constraints

- **Junctions are IDE/terminal convenience only** — scripts must never pass a junction path to a Python helper. The new `.wiki`, `.portals`, and `.active` junctions follow the same rule. All resolution goes through `_paths.py`.
- **`_junction.strip_all_in_worktree` must be called before any recursive deletion.** Since junctions_cfg now has new keys, `strip_all_in_worktree` will automatically strip the new names — no change needed to the stripping logic itself.
- **Working state lives on the task branch, not in the wiki.** `wiki/active/<slug>/task.md` is wiki state, not task state. `task/status.md` etc. are task-branch state.
- **NTFS junction targets must exist** when the junction is created. Mill-spawn must create `wiki/active/<slug>/` before creating `container/portals/<slug>` → it. Similarly, `.portals` in the task worktree is created by `create_hub_links` which runs after `wiki/active/<slug>/` exists.
- **`${CLAUDE_PLUGIN_ROOT}` for all intra-plugin paths.** Any new `uv run` or path reference in skills must use this token, not `plugins/mill/…`.

## Testing

- **`test-gitignore-phase.py`**: single-file `upsert` call; `GLOB_ENTRIES` constant content; no `ANCHORED_ENTRIES`; idempotency (second call returns False).
- **`test-setup-hub-links.py`**: junction names from new config fixture; token-scope filter (no SLUG → no `.portals`); `.active` absent from output (not in config); nested junction path (`.millhouse/wiki` → `.wiki` is now root-level).
- **`test-millpy-spawn.py`**: portals entry target is `wiki/active/<slug>/`; `.active` absent from task worktree; hub `.active` present; `task/status.md` written; `wiki/active/<slug>/task.md` content; idempotent re-spawn (no duplicate portals entries).
- **`test-spawn-core.py`**: `write_initial_status` writes to `task/status.md` and creates the `task/` dir if absent.
- **`test-worktree.py`**: `strip_all_in_worktree` with new config strips `.wiki` and `.portals` (not `.others`).

Integration tests for NTFS junction operations (creation, portals re-targeting, migration script end-to-end) are out of scope for this PR. The existing `integration_tests/` harness can be extended separately when CI infra supports Windows junction fixtures.

TDD candidates:
- `_gitignore.upsert` — pure function, easy to drive from test data.
- `write_wiki_active_task_md` helper — pure file-write, test content + idempotency.
- `recreate_active_junction` updated signature — test that hub gets the junction and task worktree does not.

## Q&A log

- **Q:** `.portals` or `.worktrees` for the renamed junction? **A:** `.portals` — confirmed.
- **Q:** Task folder: visible `task/` or hidden `.task/`? **A:** `task/` — visible; it's the only non-infrastructure thing at root, being visible helps not hinders.
- **Q:** What goes in `wiki/active/<slug>/`? **A:** A `task.md` file with slug, title, created_at. No proposal copy.
- **Q:** Migration: extend existing `millpy-migrate-layout.py` or new script? **A:** Extend existing with `--step rename-junctions`.
- **Q:** Is task-folder consolidation in scope? **A:** Yes, include it. Same migration cost either way; this PR touches all the relevant files already.
- **Q:** `.active` hub-only — how to prevent it being created in task worktrees? **A:** Remove `.active` from `config.yaml` junctions block entirely; create it explicitly via `_spawn_core.recreate_active_junction` called on the hub root in mill-spawn and mill-claim.
- **Q:** Should `wiki/active/<slug>/` be archived to `wiki/archive/<slug>/` on mill-merge? **A:** No — the `archive/<slug>` git tag on the task branch is the archive. Removing the directory on merge is sufficient.
