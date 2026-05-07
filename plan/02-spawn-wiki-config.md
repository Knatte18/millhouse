# Batch: Spawn infrastructure and wiki config

```yaml
task: Restructure hub junction layout
batch: Spawn infrastructure and wiki config
number: 2
cards: 7
verify: python plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

Change `wiki/config.yaml` to the new junction layout (`.wiki`, `.portals`). Update `_spawn_core.py` with three targeted changes: `write_initial_status` writes to `task/`, `recreate_active_junction` accepts `hub_root` directly, new `write_wiki_active_task_md` helper. Update `millpy-spawn.py` and `millpy-claim.py` to create `wiki/active/<slug>/task.md`, point portals entries at wiki/active, and call hub-side `.active` update. Update four test files to match the new config fixture and new function signatures.

Bootstrap justification for `wiki/config.yaml`: `_setup.create_hub_links` reads junction names dynamically from config — no junction name is hardcoded in any script. The three config entries (`.wiki`, `.portals`) have no hardcoded script consumers; scripts that create or strip junctions operate on whatever keys the config declares. Consuming code for the new names is added in this same batch (cards 4–6). Changing config and consuming code together means the live system is updated atomically when this batch lands; there is no window where the config and code are out of sync.

## Cards

### Card 3: `wiki/config.yaml` — new junction block

- **Context:**
  - `plugins/mill/scripts/_setup.py`
  - `plugins/mill/scripts/_junction.py`
  - `plugins/mill/scripts/_wiki.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `wiki/config.yaml`
  - `plugins/mill/scripts/_wiki.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. Read `C:\Code\millhouse\wiki\config.yaml` (the wiki clone, not the task branch).
  2. Replace the `junctions:` block:
     ```yaml
     junctions:
       .millhouse/wiki: <WIKI_PATH>
       .others: <CONTAINER_PATH>/portals/
       .active: <CONTAINER_PATH>/portals/<SLUG>/
     ```
     with:
     ```yaml
     junctions:
       .wiki: <WIKI_PATH>
       .portals: <WIKI_PATH>/active/<SLUG>/
     ```
     `.wiki` has no `<SLUG>` token so it is created in every worktree (hub and task). `.portals` requires `<SLUG>` so it is only created in task worktrees. `.active` is removed entirely from config; mill-spawn and mill-claim create it explicitly on the hub.
  3. Update the `junctions:` section comment block above the entries to reflect the new semantics. The key `.wiki` maps to `<WIKI_PATH>`; the key `.portals` maps to the wiki state dir for the current task.
  4. Deployment note: after this card's config push lands, `_junction.strip_all_in_worktree` will iterate only `.wiki` and `.portals`. Active task worktrees with old-layout junctions (`.millhouse/wiki`, `.others`, `.active`) are not automatically stripped. `--step rename-junctions` (Card 11, batch 03) strips old junctions and recreates the new layout for every active worktree. **Ensure Card 11 is run before the first `mill-cleanup` or `mill-merge` post-deploy.** No code change is needed here — this is a deployment sequencing requirement.
  5. In `plugins/mill/scripts/_wiki.py`, update `_JUNCTION_DEFAULTS` (line ~79) from:
     ```python
     _JUNCTION_DEFAULTS: dict[str, str] = {
         ".millhouse/wiki": "<WIKI_PATH>",
         ".active": "<WIKI_PATH>/active/<SLUG>/",
     }
     ```
     to:
     ```python
     _JUNCTION_DEFAULTS: dict[str, str] = {
         ".wiki": "<WIKI_PATH>",
     }
     ```
     `.portals` is SLUG-scoped and must not be in defaults (it would be created with literal `<SLUG>` in the target when no slug is available).
  6. Commit and push: call `_wiki.write_commit_push(wiki_path, ["config.yaml"], "config: new junction layout — .wiki, .portals (rename-hub-junctions)", slug="rename-hub-junctions")` where `wiki_path` is resolved via `_paths.resolve_wiki_path(_paths.resolve_git_root())`.
- **Commit:** `config(wiki): replace .millhouse/wiki + .others + .active with .wiki + .portals; strip old junctions; update _JUNCTION_DEFAULTS`

### Card 4: `_spawn_core.py` — three targeted changes

- **Context:**
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_junction.py`
  - `plugins/mill/scripts/_wiki.py`
- **Edits:**
  - `plugins/mill/scripts/_spawn_core.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. `write_initial_status`: change `status_abs = worktree_path / "status.md"` to `status_abs = worktree_path / "task" / "status.md"`. Before `status_abs.write_text(...)`, add `status_abs.parent.mkdir(parents=True, exist_ok=True)`. Change git add argument from `"status.md"` to `"task/status.md"`. Update the function docstring first line from "Render + write `status.md` at worktree root" to "Render + write `task/status.md` at worktree root; create `task/` directory if absent".
  2. `recreate_active_junction`: change signature from `(slug: str, mill_dir: Path, container_path: Path) -> None` to `(slug: str, hub_root: Path, container_path: Path) -> None`. Change `link_path = mill_dir.parent / ".active"` to `link_path = hub_root / ".active"`. Update docstring: first line from "Delete-then-create the `.active` junction at `mill_dir.parent / ".active"`" to "Delete-then-create the `.active` junction at `hub_root / ".active"`"; update the `mill_dir` arg doc to `hub_root: Absolute path to the hub git checkout`.
  3. Add new function `write_wiki_active_task_md(wiki_path: Path, slug: str, title: str, ts: str) -> None` immediately before `recreate_active_junction`. Implementation: create `wiki_path / "active" / slug` dir with `mkdir(parents=True, exist_ok=True)`, write `(wiki_path / "active" / slug / "task.md").write_text(...)` with content `f"# Task: {title}\n\n```yaml\nslug: {slug}\ntitle: {title}\ncreated_at: {ts}\n```\n"`, then call `_wiki.write_commit_push(wiki_path, [f"active/{slug}/task.md"], f"task: create active dir for {slug}", slug=slug)`.
  4. Add `write_wiki_active_task_md` to the module-level docstring's Public API section with its signature and one-line description: "Create `wiki/active/<slug>/task.md`; commit+push in wiki."
- **Commit:** `feat(_spawn_core): task/ status path; hub-root active junction; write_wiki_active_task_md`

### Card 5: `millpy-spawn.py` — create wiki/active, new portals target, hub .active

- **Context:**
  - `plugins/mill/scripts/_spawn_core.py`
  - `plugins/mill/scripts/_setup.py`
  - `plugins/mill/scripts/_junction.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-spawn.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. Move the `ts = datetime.datetime.now(...)` computation (currently at line ~225, after `_setup.create_hub_links`) to just before the container_path / portals section (around line 204). This makes `ts` available for `write_wiki_active_task_md`.
  2. After `(container_path / "portals").mkdir(parents=True, exist_ok=True)` and before `_junction.create(...)`, add: `_spawn_core.write_wiki_active_task_md(wiki_path, slug, picked.title, ts)`. This creates `wiki/active/<slug>/` and commits `task.md` in the wiki before the portal entry points to it.
  3. Change the portal entry target from `worktree_path` to `wiki_path / "active" / slug`: `_junction.create(target=wiki_path / "active" / slug, link_path=container_path / "portals" / slug)`.
  4. After `_setup.create_hub_links(dest_hub, wiki_path, dest_tokens)`, add a call to update the hub's `.active` junction: `_spawn_core.recreate_active_junction(slug, resolve_hub_path(), container_path)`. The hub worktree (`resolve_hub_path()`) gets `.active` → `container/portals/<slug>` → `wiki/active/<slug>/`.
  5. Update the dry-run status print: `print(f"[DryRun] Status:   {worktree_path / 'task' / 'status.md'}")`.
  6. Update the module docstring step 9 from "Write the initial `wiki/active/<slug>/status.md`" to "Write the initial `task/status.md` (phase=discussing) and commit+push."
- **Commit:** `feat(millpy-spawn): wiki/active dir, new portals target, hub .active update`

### Card 6: `millpy-claim.py` — portals target, recreate_active_junction sig, dry_run path

- **Context:**
  - `plugins/mill/scripts/_spawn_core.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_junction.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-claim.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. Move the `ts = datetime.datetime.now(...)` computation (currently at line ~300, after `recreate_active_junction`) to just before the portal entry section (around line 280, after the `container_path` and `main_root` assignments). This makes `ts` available for `write_wiki_active_task_md`.
  2. Before creating/re-checking the portal entry, call `_spawn_core.write_wiki_active_task_md(wiki_path, slug, picked.title, ts)`. This ensures `wiki/active/<slug>/` exists before the portal entry points to it.
  3. Change portal entry target from `main_root` to `wiki_path / "active" / slug`:
     - First creation: `_junction.create(target=wiki_path / "active" / slug, link_path=portal_link)`.
     - Re-creation check: `current_target = os.path.realpath(str(wiki_path / "active" / slug))`.
  4. Update `recreate_active_junction` call (currently line ~297): change `_spawn_core.recreate_active_junction(slug, mill_dir, container_path)` to `_spawn_core.recreate_active_junction(slug, resolve_hub_path(), container_path)`. Do NOT use `git_root` — in subfolder installs `resolve_hub_path()` differs from `git_root`, and using `git_root` would place `.active` at the wrong location.
  5. Update dry-run status print (line ~217): `print(f"[DryRun] Status:  {resolve_hub_path() / 'task' / 'status.md'}")`.
- **Commit:** `feat(millpy-claim): wiki/active dir, new portals target, hub-root active junction`

### Card 7: `test-setup-hub-links.py` — update config fixture and assertions

- **Context:**
  - `plugins/mill/scripts/_setup.py`
  - `plugins/mill/scripts/_junction.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-setup-hub-links.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. Update `_FULL_CFG` junctions block:
     ```python
     "junctions": {
         ".wiki": "<WIKI_PATH>",
         ".portals": "<WIKI_PATH>/active/<SLUG>/",
     },
     ```
     (Remove `.millhouse/wiki`, `.others`, `.active`.)
  2. Update `_ALL_SLUG_CFG`:
     ```python
     "junctions": {
         ".portals": "<WIKI_PATH>/active/<SLUG>/",
     },
     ```
     (Was `.active: <CONTAINER_PATH>/portals/<SLUG>/`.)
  3. Update `_HARDLINK_ONLY_CFG`:
     ```python
     "junctions": {
         ".portals": "<WIKI_PATH>/active/<SLUG>/",  # filtered: needs SLUG
     },
     ```
  4. Update `test_token_scope_filter_no_slug`:
     - Create `wiki_path / "active"` dir in fixture (`.portals` target parent must exist).
     - Check `.wiki` junction created (at `target_root / ".wiki"`) and `.portals` NOT created.
     - Update result assertion: `len(result["junctions"]) == 1` (only `.wiki`).
     - Remove checks for `.millhouse/wiki` and `.others`.
  5. Update `test_token_scope_filter_with_slug`:
     - Create `wiki_path / "active" / "my-task"` dir in fixture (`.portals` target must exist).
     - Check `.wiki` and `.portals` junctions created. Remove checks for `.millhouse/wiki`, `.others`, `.active`.
     - Update result assertion: `len(result["junctions"]) == 2`.
  6. Update `test_portal_flow_integration`:
     - Change fixture: create `wiki_path / "active" / "my-task"` instead of portals/my-task → target_root. Create `portal/my-task` pointing to `wiki_path / "active" / "my-task"` (mirrors new mill-spawn).
     - Check `.wiki` (at `target_root / ".wiki"`) resolves to wiki path. Remove `.millhouse/wiki` check.
     - Check `.portals` (at `target_root / ".portals"`) resolves to `wiki/active/my-task/`. Write a probe file there and verify it's accessible via `.portals`.
     - Remove `.active`, `.others` checks. Update junction count to 2 (was 3).
  7. Update the test file's module-level docstring (lines 1–18) to reflect new junction names.
  8. Keep `test_hardlink_inode_skip_idempotent`, `test_hardlink_inode_mismatch_backup_and_recreate`, `test_all_entries_filtered_return_empty_lists`, `test_cross_volume_hardlink_raises_clear_error` — only change their `_FULL_CFG` usage indirectly (they use `_FULL_CFG` constant, already updated above).
- **Commit:** `test(test-setup-hub-links): update fixture to new .wiki + .portals junction layout`

### Card 8: `test-spawn-core.py` — status path and junction signature

- **Context:**
  - `plugins/mill/scripts/_spawn_core.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-spawn-core.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. `test_write_initial_status`: change the assertion `status_path != repo / "status.md"` to `status_path != repo / "task" / "status.md"`. The git log check (`"spawn: init status for task-one"`) remains the same.
  2. `test_write_initial_status_forced_failure_raises_runtime_error`: no change needed — it only checks the error message prefix.
  3. `test_recreate_active_junction_creates_link`: update call from `recreate_active_junction("my-task", mill_dir, container_path)` to `recreate_active_junction("my-task", mill_dir.parent, container_path)`. The `link_path` assertion remains `mill_dir.parent / ".active"` (unchanged: `hub_root / ".active"` == `mill_dir.parent / ".active"`).
  4. `test_recreate_active_junction_idempotent`: same signature update — both calls use `mill_dir.parent` as the `hub_root` argument.
  5. Update the import line to add `write_wiki_active_task_md` to the imports from `_spawn_core`.
  6. Add `test_write_wiki_active_task_md`: use the existing `_make_wiki` fixture (which creates a local bare remote + working clone — already used by `test_claim_in_wiki` and `test_multi_select_groom_then_claim_basic`). Call `_spawn_core.write_wiki_active_task_md(wiki_path, "task-one", "Task One Title", "20260506-180000")`. Assert: (a) `wiki_path / "active" / "task-one"` directory exists; (b) `wiki_path / "active" / "task-one" / "task.md"` contains both the slug `task-one` and title `Task One Title`; (c) git log in the wiki shows a commit with message containing `task-one`. Use the same git-log inspection pattern as `test_write_initial_status` (`git log --pretty=%s -n 1` via `_subprocess_util` or direct subprocess call).
- **Commit:** `test(test-spawn-core): task/status.md path; hub_root signature; write_wiki_active_task_md coverage`

### Card 9: `test-millpy-spawn.py` + `test-millpy-claim.py` — stub and assertion updates

- **Context:**
  - `plugins/mill/scripts/millpy-spawn.py`
  - `plugins/mill/scripts/millpy-claim.py`
  - `plugins/mill/scripts/_spawn_core.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-spawn.py`
  - `plugins/mill/unit_tests/test-millpy-claim.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  **test-millpy-spawn.py:**
  1. In `test_main_dry_run_prints_worktree_status_path`: update the expected path assertion from `str(Path("/fake/worktrees") / "my-task" / "status.md")` to `str(Path("/fake/worktrees") / "my-task" / "task" / "status.md")`. Card 5 req 5 changes the dry-run print to the `task/` path; the test must match.
  2. No stub for `write_wiki_active_task_md` is needed in `test_smoke_import`. That test does not call `main()` and `_spawn_core` is loaded as a real `types.ModuleType` (not a `MagicMock`), so the new `_spawn_core.write_wiki_active_task_md` function is available without stubbing. Tests that mock-replace `_spawn_core` with a `MagicMock` (e.g. main-flow tests) auto-handle the attribute via `MagicMock`'s default behaviour. (This NIT is documented here so that a future change to the test pattern doesn't reintroduce the stub.)

  **test-millpy-claim.py:**
  3. In `test_main_happy_path` (the test with all helper call assertions): change the comment on line ~241 from `"Verify new signature: (slug, mill_dir, container_path)"` to `"Verify new signature: (slug, hub_root, container_path)"`. Change `expected_mill_dir = Path("/fake/repo") / ".millhouse"` to `expected_hub_root` set to whatever `resolve_hub_path()` is mocked to return in that test (check the mock stub map — it may differ from `git_root` in subfolder-install tests). Change the assertion `rac_call.args[1] != expected_mill_dir` to `rac_call.args[1] != expected_hub_root` and update the error message to name `hub_root`. If the standard test has both `resolve_hub_path` and `resolve_git_root` returning `Path("/fake/repo")`, change the hub mock to return a distinct path (e.g. `Path("/fake/repo/subdir")`) so the test catches the `git_root` vs `resolve_hub_path()` distinction.
  4. Update all `sc.write_initial_status.return_value` mock values (lines ~211, ~331, ~396, ~450, ~510, ~570, ~625, ~681) from stale paths like `Path("/fake/wiki/active/my-task/status.md")` to `Path("/fake/repo/task/status.md")` (or `/fake/repo/src/Models/task/status.md` for the subfolder-install case). These are mock return values; updating them keeps tests readable and avoids confusion about the expected path.
- **Commit:** `test(spawn/claim): update stubs, dry-run path, and sig assertions for new _spawn_core API`

## Batch Tests

`python plugins/mill/unit_tests/run-all.py` must exit 0. All unit tests pass.
