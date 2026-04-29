# Batch: consumers-and-skills

```yaml
task: 11 — par-C — Container layout overhaul + cwd-as-hub everywhere + gitignore-split
batch: consumers-and-skills
cards: 7
verify: python plugins/mill/unit_tests/run-all.py
depends-on: [state-on-worktree]
```

## Batch Scope

This batch updates every consumer of "where does the task state live" to read from the worktree instead of the wiki, and overhauls the SKILL.md prose for `mill-setup`, `mill-merge`, `mill-resume`, and `mill-self-report` to match the new layout. Six `millpy-*` scripts (status, list, inspect, terminal, vscode, cleanup) get the cwd-as-hub treatment via `_paths.resolve_hub_relative_path` and the new worktree-discovery scan (`<container>/wts/*/.millhouse/active.slug.md`). `mill-cleanup` learns to remove the portal entry; `mill-merge` SKILL.md gets the new teardown sequence (cleanup commit + archive tag + worktree remove + branch delete + portal remove). `mill-setup` SKILL.md is rewritten to use `_setup.create_hub_links`, create `<container>/portals/`, write `hub_relative_path` into `.millhouse/config.local.yaml`, and call `_gitignore.upsert_split` instead of the old `upsert`. The `config.local.yaml` template gets a documented `hub_relative_path:` example. After this batch lands, the only piece left is the migration tool + CLAUDE.md doc update (batch 05). Local decision diverging from shared: SKILL.md cards land prose changes only — no executable verification beyond `run-all.py` (which doesn't exercise SKILL.md). Manual smoke-tests after each SKILL.md card are recommended but the batch verify gate is unit-test pass.

## Cards

### Card 16: state-readers — `millpy-status.py`, `millpy-list.py`, `millpy-inspect.py`

- **Reads:**
  - `plugins/mill/scripts/millpy-status.py`
  - `plugins/mill/scripts/millpy-list.py`
  - `plugins/mill/scripts/millpy-inspect.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_spawn_core.py`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_active.py`
  - `plugins/mill/scripts/_tasks_md.py`
- **Modifies:**
  - `plugins/mill/scripts/millpy-status.py`
  - `plugins/mill/scripts/millpy-list.py`
  - `plugins/mill/scripts/millpy-inspect.py`
- **Creates:** none
- **Requirements:** All three scripts currently scan `<wiki>/active/*/` (`millpy-status.py`, `millpy-inspect.py`) or read `<wiki>/Home.md` (`millpy-list.py`) to enumerate tasks and read state. After this card: each script ADDS a derivation `container_path = _paths.resolve_container_path(git_root)` (using the new helper from Card 4 — handles both container-form and prefix-form correctly; do NOT use `resolve_main_worktree_root(git_root).parent` which returns `<container>/wts/` in container-form and would land the discovery scan at `<container>/wts/wts/`, an empty phantom directory). Then enumerate active worktrees via `_spawn_core.discover_active_worktrees(container_path / "wts")` (the existing helper handles the `.millhouse/active.slug.md` scan and is unchanged). For each active worktree, status is read from `<worktree>/status.md` directly (no wiki indirection). `millpy-list.py` continues to read `Home.md` from the wiki for the backlog listing — that's a wiki-side concern, not per-task state, and stays. `millpy-inspect.py` similarly reads each worktree's `status.md` and any other state files at the worktree root. Note: none of the three scripts currently call `_paths.resolve_worktrees_dir`; the discovery scan reaches `<container>/wts/` directly via `container_path / "wts"`, which equals what `resolve_worktrees_dir`'s container-form fallback returns (`main_root.parent`). Additionally, REMOVE `_worktree.list_worktrees` calls in `millpy-status.py` and `millpy-inspect.py`: the `discover_active_worktrees` scan already returns `(path, slug, title)` triples for every active worktree, which is the same data the `worktree_map` derived from `list_worktrees` was providing. Populate the WORKTREE column / map in each script directly from `discover_active_worktrees`'s return value to avoid two stale-data sources. Drop the now-unused `import _worktree` if no other callsite remains. Tests: extend `test-spawn-core.py` if it covers `discover_active_worktrees`; for `millpy-status`/`list`/`inspect` add lightweight tests OR extend any related test (none exist for these scripts today; create only if the changed surface justifies it — these are mostly path-substitution changes verified by the existing `discover_active_worktrees` test).
- **Commit:** `refactor(consumers): status/list/inspect read state from <container>/wts/<slug>`

### Card 17: cwd-as-hub launchers — `millpy-terminal.py` + `millpy-vscode.py`

- **Reads:**
  - `plugins/mill/scripts/millpy-terminal.py`
  - `plugins/mill/scripts/millpy-vscode.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/scripts/_spawn_core.py`
  - `plugins/mill/unit_tests/test-millpy-terminal.py`
  - `plugins/mill/unit_tests/test-millpy-vscode.py`
- **Modifies:**
  - `plugins/mill/scripts/millpy-terminal.py`
  - `plugins/mill/scripts/millpy-vscode.py`
  - `plugins/mill/unit_tests/test-millpy-terminal.py`
  - `plugins/mill/unit_tests/test-millpy-vscode.py`
- **Creates:** none
- **Requirements:** Both scripts launch a subprocess (Claude Code for terminal, VS Code for vscode) at a chosen worktree path. The existing pre-pick `_load_config(wiki_path, git_root)` call (used to resolve `worktrees_dir` and any other hub-side config keys) STAYS — it is needed before discovery to compute the worktrees container. After the user picks a worktree, ADD a SECOND `_load_config(wiki_path, selected_path)` call (passing the chosen worktree root) so the per-worktree `.millhouse/config.local.yaml` is read — the `hub_relative_path` key lives in the per-worktree config and reading from the hub returns the hub's own value, not the chosen worktree's. Pull `hub_relative_path` out of the post-pick merged config (default `.` if absent). Compute the launch directory as `_paths.resolve_hub_relative_path(selected_path, hub_relative_path)` — equals `selected_path` when `hub_relative_path == "."` (typical) and a subfolder when the consumer is hub-as-subfolder (NORCE-Models case). Launch the subprocess with the resolved path as cwd / workspace folder. `discover_active_worktrees` already returns the worktree root; the cwd-as-hub helper is a thin wrapper applied at the launch site. Extend each test file: stub `hub_relative_path: src/csharp/X` in the per-worktree config.local.yaml and assert the subprocess is launched with `<worktree>/src/csharp/X` as the workspace folder; also cover `hub_relative_path: .` (default); add a regression test where the HUB's `config.local.yaml` has a different `hub_relative_path:` from the selected worktree's, and assert the SELECTED worktree's value wins (proving the second `_load_config` call uses `selected_path`, not `git_root`).
- **Commit:** `feat(launchers): mill-terminal/mill-vscode honor hub_relative_path`

### Card 18: `millpy-cleanup.py` portal removal + cwd-as-hub + state-from-worktree

- **Reads:**
  - `plugins/mill/scripts/millpy-cleanup.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_junction.py`
  - `plugins/mill/scripts/_spawn_core.py`
  - `plugins/mill/scripts/_inplace.py`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/unit_tests/test-cleanup.py`
- **Modifies:**
  - `plugins/mill/scripts/millpy-cleanup.py`
  - `plugins/mill/unit_tests/test-cleanup.py`
- **Creates:** none
- **Requirements:** Restructure `SlugRecord` and the cleanup pipeline to disambiguate the two roles `active_dir` previously conflated (worktree root vs legacy wiki dir). Specifically. (a) `SlugRecord` becomes `(slug: str, worktree_path: Path | None, branch: str | None, wiki_active_dir: Path | None, home_marker: str | None)` — the `active_dir` field is split into `worktree_path` (always the worktree root when one exists, used for status reads and `_read_phase`) and `wiki_active_dir` (the legacy `<wiki>/active/<slug>/` directory IF it still exists from pre-migration state, optional and used only for the conditional rmtree at teardown). (b) `build_plan`'s parameter renames from `active_dirs` to `active_worktrees: list[Path]` where each path is a worktree root; the caller (in `main`) populates this list via `_spawn_core.discover_active_worktrees(container_path / "wts")`. `wiki_active_dir` for each record is computed as `wiki_path / "active" / slug` and stored only if `.is_dir()` — otherwise `None`. (c) `_read_phase` now reads `worktree_path / "status.md"` to pick up the post-batch-03 state location. (d) `_apply_inplace_record` reads `parent_branch = _status.read_parent_branch(record.worktree_path / "status.md")` (NOT `record.active_dir / "status.md"`) — the in-place case still has the worktree directory because in-place tasks DO have a worktree (it just IS the hub root). For tasks where `worktree_path is None` (orphan record), fall back to skipping branch deletion with the existing warning. (e) `_apply_worktree_record` and `_apply_inplace_record` now ALSO remove the portal entry: each function computes `container_path = _paths.resolve_container_path(hub_root)` inline at the top of its body (both functions already receive `hub_root`), then calls `_junction.remove(container_path / "portals" / slug)` after the worktree-or-branch removal completes. Use the new helper from Card 4, NOT `hub_root.parent` (which returns `<container>/wts/` in container-form, landing the removal under `<container>/wts/portals/<slug>` — a path that doesn't exist). Removal is idempotent (the helper handles missing/broken junctions). (f) `apply_plan`'s `shutil.rmtree(record.active_dir)` becomes `if record.wiki_active_dir is not None and record.wiki_active_dir.is_dir(): shutil.rmtree(record.wiki_active_dir)` — the legacy wiki dir is removed only when present, and `worktree_path` is NEVER `rmtree`'d (it's owned by `_apply_worktree_record`'s `_worktree.remove`). (g) The wiki-commit at the end now only commits `Home.md` and `_Sidebar.md` if those changed; the `active/{record.slug}` path is added to `wiki_relative_paths` only when `wiki_active_dir is not None`. Update `test-cleanup.py` fixtures: seed `<container>/wts/<slug>/status.md` (NEW state location); add fixture variants for "fresh layout, no wiki/active/<slug>/" and "legacy clone with leftover wiki/active/<slug>/" — both must work. Assert: portal entry removed; worktree removed; branch deleted; rmtree happens on the legacy fixture but NOT on the fresh fixture (and the worktree directory is NEVER rmtree'd in either case).
- **Commit:** `refactor(cleanup): split SlugRecord; remove portal entry; read state from worktree`

### Card 19: `mill-setup` SKILL.md update + legacy `_gitignore.upsert` removal

- **Reads:**
  - `plugins/mill/skills/mill-setup/SKILL.md`
  - `plugins/mill/scripts/_setup.py`
  - `plugins/mill/scripts/_gitignore.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/unit_tests/test-gitignore-phase.py`
  - `wiki/active/container-restructure/discussion.md`
- **Modifies:**
  - `plugins/mill/skills/mill-setup/SKILL.md`
  - `plugins/mill/scripts/_gitignore.py`
  - `plugins/mill/unit_tests/test-gitignore-phase.py`
- **Creates:** none
- **Requirements:** Rewrite the SKILL.md to match the new layout. Phase 3.5 (resolve junctions) and Phase 4 (create hub junctions) collapse into a single phase that calls `_setup.create_hub_links(target_root=<HUB_PATH>, wiki_path=<WIKI_PATH>, tokens={...without SLUG...})`. The token-scope filter handles "skip slug-bearing entries for the hub" automatically. Phase 4.5 (create hardlinks) is gone — `_setup.create_hub_links` does it. Phase 4.5b (gitignore marker block) calls `_gitignore.upsert_split(repo_root_gitignore=<git_toplevel>/.gitignore, hub_gitignore=<HUB_PATH>/.gitignore, glob_entries=GLOB_ENTRIES, anchored_entries=ANCHORED_ENTRIES + hardlink_names)` — replaces the legacy `_gitignore.upsert(...)` callsite that was preserved in Card 5 specifically until this card lands. After updating the SKILL.md callsite, REMOVE the now-unused legacy `upsert(gitignore_path, hardlink_entries)` function and the legacy single-arg `render_block(hardlink_entries)` overload from `plugins/mill/scripts/_gitignore.py`. Update `test-gitignore-phase.py` to drop the legacy-shape tests (the `upsert_split` tests added in Card 5 cover the new surface). New phase BEFORE Phase 4 (call it Phase 3.7 or "create container scaffolding"): create `<CONTAINER_PATH>/portals/` directory if missing; create main-worktree portal entry `<CONTAINER_PATH>/portals/<REPO>/` → `<HUB_PATH>`. New phase BEFORE Phase 5 (config.local.yaml seeding): write `hub_relative_path: <subpath>` into `.millhouse/config.local.yaml` where `<subpath>` is `cwd.relative_to(git_toplevel).as_posix()` (or `"."` when `cwd == git_toplevel`). Phase 8 (verify) updated to check: `<CONTAINER_PATH>/wts/` exists; `<CONTAINER_PATH>/portals/` exists with the main-worktree entry; `.others` junction exists at the hub; `hub_relative_path` is recorded in `config.local.yaml`. All Python invocation snippets use `${CLAUDE_PLUGIN_ROOT}/scripts/...`. Drop any prose that references the old hub-form (`name == "hub"`); replace with the container-form (`<container>/wts/<repo>/`) explanation. The "Layout assumed" section gets the new diagram from discussion.md. Markdown style follows the existing SKILL.md (per `mill:markdown` rules — fenced ```yaml metadata, tables for state-action mappings).
- **Commit:** `docs(mill-setup): rewrite SKILL.md for container-form layout; drop legacy gitignore.upsert`

### Card 20: `mill-merge` SKILL.md teardown rewrite

- **Reads:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_junction.py`
  - `plugins/mill/scripts/_active.py`
  - `wiki/active/container-restructure/discussion.md`
- **Modifies:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Creates:** none
- **Requirements:** Replace the existing teardown section with the seven-step sequence from discussion.md `## Decisions → task-branch-teardown`: (1) on the task branch, `git rm -r reviews/ discussion.md plan/ status.md` then `git commit -m "chore: pre-merge cleanup"`; (2) checkout parent branch, `git merge --squash <task-branch>`, author squash-commit message via the existing template; (3) `git tag archive/<slug> <task-branch>` to tag the cleanup-commit tip; (4) `git worktree remove <container>/wts/<slug>`; (5) `git branch -D <task-branch>`; (6) `_junction.remove(<container>/portals/<slug>)`; (7) idempotent legacy cleanup `rmtree(<wiki>/active/<slug>)` if it exists, then commit+push to wiki. Each step is a numbered table row with a "Why" column referencing the discussion. Update prose elsewhere in the file that refers to wiki-side cleanup as the primary path; primary path is now branch-side. Add a callout that the cleanup commit is reviewable in `git log archive/<slug>` after teardown — operators can recover state via `git checkout archive/<slug>`. Drop any reference to `wiki_path/active/<slug>` writes during merge — those don't happen anymore. Verify-side check: confirm after teardown that the worktree dir is gone, branch is gone, portal is gone, archive tag exists at the expected commit, and `Home.md` shows `[done]`.
- **Commit:** `docs(mill-merge): teardown becomes cleanup-commit + tag + worktree+branch+portal removal`

### Card 21: `mill-resume` + `mill-self-report` SKILL.md state-from-worktree

- **Reads:**
  - `plugins/mill/skills/mill-resume/SKILL.md`
  - `plugins/mill/skills/mill-self-report/SKILL.md`
  - `plugins/mill/scripts/_paths.py`
- **Modifies:**
  - `plugins/mill/skills/mill-resume/SKILL.md`
  - `plugins/mill/skills/mill-self-report/SKILL.md`
- **Creates:** none
- **Requirements:** Both SKILL.md files currently instruct the assistant to read `<wiki>/active/<slug>/status.md`, `<wiki>/active/<slug>/discussion.md`, and other state files. After this card: each prose change replaces those paths with `<container>/wts/<slug>/status.md` etc., or — preferred — directs the assistant to read state via `.others/<slug>/status.md` when invoked from a peer worktree, or just `<worktree>/status.md` when invoked from the task's own worktree. The `mill-self-report` skill posts GitHub issues based on observed bugs; its read of `status.md` for context-gathering is the only path that changes. `mill-resume` reads the latest task state to pick up where a previous session left off — same path change. Drop any `wiki/active/<slug>/` references in either file. ADDITIONALLY: `mill-resume` SKILL.md Phase 6 ("Create worktree") currently has `git -C <git-root> worktree add <worktrees-dir>/<slug> <branch_name>` with `<worktrees-dir>` defined as `<git-root-parent>/<repo-name>.worktrees/`. Both lines are wrong for the new layout. Update Phase 6 to: `git -C <git-root> worktree add <container>/wts/<slug> <branch_name>` and update the `<worktrees-dir>` definition to `<container>/wts/`, where `<container>` is `_paths.resolve_container_path(<git-root>)` (the helper from Card 4). The Phase 4 precondition check (`<worktrees-dir>/<slug>/` already exists) is updated symmetrically. The Phase 6 error-handling row in the prose table (`git worktree add fails`) is unchanged. Neither skill writes wiki state for the task itself anymore; both still write wiki state for cross-task concerns (e.g. mill-self-report may file an issue, but issues live on GitHub). Add a callout in `mill-resume` SKILL.md that cross-machine resume requires `git fetch && git checkout <branch>` first (mentioned in discussion.md `## Technical context → Cross-machine implications`).
- **Commit:** `docs(skills): mill-resume + mill-self-report read state from worktree`

### Card 22: `plugins/mill/templates/config.local.yaml` `hub_relative_path` example

- **Reads:**
  - `plugins/mill/templates/config.local.yaml`
- **Modifies:**
  - `plugins/mill/templates/config.local.yaml`
- **Creates:** none
- **Requirements:** Add a documented commented example for `hub_relative_path:` near the top of the file (after the leading description block but before the existing `spawn:` example). Comment the line out — the value is filled in by `mill-setup` at setup time, not by hand. Comment text should explain: the value is the cwd-relative subpath where the user effectively wants the hub state (`.active`, `.others`, `tasks.md`, `.vscode/`) to live. For typical mill-managed projects where `cwd == git_toplevel` at setup time, the value is `.`; for downstream consumers where mill is installed in a subfolder of an existing repo (like NORCE-DrillingAndWells/Models), the value is the relative path from the git toplevel to that subfolder. Existing template content (the leading description, the `spawn.branch_prefix` example) is unchanged.
- **Commit:** `docs(template): document hub_relative_path in config.local.yaml`

## Batch Tests

`verify: python plugins/mill/unit_tests/run-all.py` — unit-test gate. Note: cards 18–20 (SKILL.md prose) have no automated coverage in the unit test suite; their correctness is verified manually by re-reading the SKILL.md text against the discussion.md decisions and by smoke-testing once the migration tool from batch 05 has been run on a real clone. Card 17 (`millpy-cleanup`) carries the bulk of the integration-test surface for this batch through `test-cleanup.py`. After this batch, the only end-to-end gap is on-disk migration — batch 05 closes that.
