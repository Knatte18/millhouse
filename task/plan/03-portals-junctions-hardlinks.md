# Batch: portals-junctions-hardlinks

```yaml
task: 33 (A) -- Working-dir rename + portals redesign + junction cleanup
batch: portals-junctions-hardlinks
number: 3
cards: 8
verify: python plugins/mill/unit_tests/run-all.py
depends-on: [2]
```

## Batch Scope

Implements the portal redesign: `portals/<slug>` now points directly at `wts/<slug>/_mill/` instead of `wiki/active/<slug>/`. Deletes `write_wiki_active_task_md` from `_spawn_core.py` and removes its callers in spawn/claim. Adds `.portals: <CONTAINER_PATH>/portals/` to the junctions config (hub-scope) and creates the `.portals` junction explicitly in task worktrees during spawn/claim. Removes `wiki_active_dir` from `millpy-cleanup.py`'s `SlugRecord` and all cleanup logic that depended on it. Updates unit tests.

## Cards

### Card 15: Delete `write_wiki_active_task_md` from `_spawn_core.py`

- **Context:**
  - `plugins/mill/scripts/_spawn_core.py`
- **Edits:**
  - `plugins/mill/scripts/_spawn_core.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Delete the entire `write_wiki_active_task_md` function from `_spawn_core.py` (lines 745-763). The function creates `wiki/active/<slug>/task.md` and commits it to the wiki. After this batch, portals no longer require a wiki active directory, so this function is obsolete. Remove the function body and its docstring. Do not remove `recreate_active_junction` (immediately follows, lines 766+) — that function remains correct.
- **Commit:** `feat(spawn-core): delete write_wiki_active_task_md (portals no longer use wiki active dir)`

### Card 16: Update `millpy-spawn.py` portal creation

- **Context:**
  - `plugins/mill/scripts/millpy-spawn.py`
  - `plugins/mill/scripts/_spawn_core.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-spawn.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `millpy-spawn.py`, around lines 200-221, make these changes:
  (1) Remove the call to `_spawn_core.write_wiki_active_task_md(wiki_path, slug, picked.title, ts)` (line 207) entirely. Remove the surrounding comment block on lines 203-204 that described it.
  (2) Change the `_junction.create` call (line 211) so the portal target is `worktree_path / "_mill"` instead of `wiki_path / "active" / slug`. The link_path argument `container_path / "portals" / slug` stays unchanged.
  (3) After the `_junction.create` portal call, add a new line to create the `.portals` junction inside the new worktree: `_junction.create(target=container_path / "portals", link_path=dest_hub / ".portals")`. This gives the task worktree a `.portals` convenience junction pointing at the shared portals directory.
  (4) Update the comment block on lines 209-211 (formerly: "Portal entry points to wiki/active/<slug>/...") to: "Portal entry points to wts/<slug>/_mill/ directly; .portals junction gives the worktree a view of the shared portals dir."
  Note: `recreate_active_junction` call on line 221 remains correct — it already points `.active` at `container_path / "portals" / slug`, which after this change resolves transitively to `wts/<slug>/_mill/`.
- **Commit:** `feat(spawn): portal points at wts/<slug>/_mill/, add .portals junction in task worktree`

### Card 17: Update `millpy-claim.py` portal creation

- **Context:**
  - `plugins/mill/scripts/millpy-claim.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-claim.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `millpy-claim.py`, around lines 275-296, make these changes:
  (1) Remove the call to `_spawn_core.write_wiki_active_task_md(wiki_path, slug, picked.title, ts)` (line 280) and its associated comment.
  (2) In the portal junction creation block (lines 282-294): change all occurrences of `wiki_path / "active" / slug` (the junction target) to `resolve_hub_path() / "_mill"`. The junction link_path `container_path / "portals" / slug` stays unchanged. The logic that checks whether the portal already points at the correct target and recreates it if not must be updated to compare against `resolve_hub_path() / "_mill"` instead of `wiki_path / "active" / slug`.
  (3) After the portal junction block, add a `.portals` junction creation inside the hub (worktree): `_junction.create(target=container_path / "portals", link_path=resolve_hub_path() / ".portals")`. Use the same guard as spawn: only create if not already present (check `not (resolve_hub_path() / ".portals").exists()`).
- **Commit:** `feat(claim): portal points at hub/_mill/, add .portals junction`

### Card 18: Update `wiki/config.yaml` junctions block

- **Context:**
  - `wiki/config.yaml`
- **Edits:**
  - `wiki/config.yaml`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `wiki/config.yaml`, under the `junctions:` key, make two changes:
  (1) Change `.active: <WIKI_PATH>/active/<SLUG>/` to `.active: <CONTAINER_PATH>/portals/<SLUG>/`. The `.active` junction now points at the portal entry (which in turn points at `wts/<slug>/_mill/`), not at the wiki.
  (2) Add a new entry below `.wiki`: `.portals: <CONTAINER_PATH>/portals/`. This is hub-scope (no `<SLUG>` token), so mill-setup creates it in the hub worktree during initial setup.
  Leave all surrounding comment lines and other config keys untouched.
- **Commit:** `feat(config): update .active junction target, add .portals junction`

### Card 19: Update `plugins/mill/templates/wiki-config.yaml` junctions block

- **Context:**
  - `plugins/mill/templates/wiki-config.yaml`
- **Edits:**
  - `plugins/mill/templates/wiki-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Apply the same junction changes as card 18 to the template file:
  (1) Change `.active: <WIKI_PATH>/active/<SLUG>/` to `.active: <CONTAINER_PATH>/portals/<SLUG>/`.
  (2) Add `.portals: <CONTAINER_PATH>/portals/` to the junctions block.
  Preserve all existing comment lines and key order.
- **Commit:** `feat(templates): update junctions in wiki-config template`

### Card 20: Remove `wiki_active_dir` from `millpy-cleanup.py`

- **Context:**
  - `plugins/mill/scripts/millpy-cleanup.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-cleanup.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** `wiki_active_dir` in `SlugRecord` tracked the `wiki/active/<slug>/` directory for cleanup. After the portal redesign, spawn no longer creates that directory, so tracking and removing it is no longer the cleanup script's responsibility.
  (1) Remove the `wiki_active_dir: Path | None` field from the `SlugRecord` dataclass (line 37).
  (2) In `build_plan` (around lines 129-132): remove the two lines that compute `wiki_active_dir_candidate` and `wiki_active_dir`, and remove the `wiki_active_dir` argument from the `SlugRecord(...)` constructor call.
  (3) In `_print_plan` (lines 211 and 216): remove `wiki_active_dir={r.wiki_active_dir}` from the format strings in both REMOVE print lines.
  (4) In `apply_plan` (lines 543-545): remove the `if record.wiki_active_dir is not None ...` block (3 lines: the if check, the rmtree call, and the wiki_relative_paths.append).
  (5) In `_apply_pr_reap_record` (lines 510-512): remove the equivalent `if record.wiki_active_dir is not None ...` block.
  The `import shutil` at the top of the file can be removed if it is now unused — check whether any other code in the file still calls `shutil`.
- **Commit:** `feat(cleanup): remove wiki_active_dir from SlugRecord (portals redesign)`

### Card 21: Update `test-millpy-spawn.py` and `test-millpy-claim.py` for portal changes

- **Context:**
  - `plugins/mill/unit_tests/test-millpy-spawn.py`
  - `plugins/mill/unit_tests/test-millpy-claim.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-spawn.py`
  - `plugins/mill/unit_tests/test-millpy-claim.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In both test files:
  (1) Find any test that asserts the portal entry (`portals/<slug>`) points at `wiki/active/<slug>/`. Update the assertion to check that the portal points at the worktree's `_mill/` subdirectory instead.
  (2) Find any test that asserts `write_wiki_active_task_md` is called (mock assertions, call counts, etc.) and remove or replace those assertions, since the function no longer exists.
  (3) Add assertions (where fixtures allow) that the `.portals` junction is created inside the worktree directory.
  If a test file uses `mock.patch` or similar for `_spawn_core.write_wiki_active_task_md`, remove those patches.
- **Commit:** `test(spawn,claim): update portal assertions for _mill/ target and .portals junction`

### Card 22: Update `test-spawn-core.py` and `test-cleanup.py`

- **Context:**
  - `plugins/mill/unit_tests/test-spawn-core.py`
  - `plugins/mill/unit_tests/test-cleanup.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-spawn-core.py`
  - `plugins/mill/unit_tests/test-cleanup.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In `test-spawn-core.py`: find and remove any test function(s) that test `write_wiki_active_task_md` (the deleted function). Also update any test for `write_initial_status` that asserts `task/status.md` is created — change it to assert `_mill/status.md` is created.
  In `test-cleanup.py`: find any test that constructs a `SlugRecord` with a `wiki_active_dir` argument — remove that argument from all `SlugRecord(...)` constructor calls in the tests. Update any test that checks `shutil.rmtree` is called on a `wiki/active/<slug>/` path to remove or update that assertion (the cleanup script no longer does this). If `wiki_active_dir` is referenced in any test assertion, remove it.
- **Commit:** `test(spawn-core,cleanup): remove wiki_active_dir tests, update status path assertions`

## Batch Tests

Run `python plugins/mill/unit_tests/run-all.py`. All tests from batches 01 and 02 must continue to pass. No test should reference `write_wiki_active_task_md` or `SlugRecord.wiki_active_dir` after this batch.
