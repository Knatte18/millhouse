# Batch: Teardown and migration

```yaml
task: Restructure hub junction layout
batch: Teardown and migration
number: 3
cards: 3
verify: python plugins/mill/unit_tests/run-all.py
depends-on: [1, 2]
```

## Batch Scope

Update `millpy-cleanup.py` to read status from `task/status.md` (with legacy fallback) and to remove the hub `.active` junction when its target is gone after cleanup. Add `--step rename-junctions` to `millpy-migrate-layout.py`. Add new test cases to `test-cleanup.py` and `test-worktree.py` for the new behaviours.

## Cards

### Card 10: `millpy-cleanup.py` — status path fallback + hub .active cleanup

- **Context:**
  - `plugins/mill/scripts/_junction.py`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-cleanup.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. `build_plan` at the line `phase = _read_phase(wt_path / "status.md")`: replace with a two-path read that checks `task/status.md` first:
     ```python
     _task_status = wt_path / "task" / "status.md"
     _legacy_status = wt_path / "status.md"
     phase = _read_phase(_task_status if _task_status.exists() else _legacy_status)
     ```
     Also apply the same fallback pattern to the `read_parent_branch` call in `build_plan`'s `if phase == "done":` block — `read_parent_branch(wt_path / "status.md")` must become `read_parent_branch(_task_status if _task_status.exists() else _legacy_status)` using the same `_task_status` / `_legacy_status` variables already computed above. (The shared decision `task-status-path-fallback` states: "any consumer that reads `status.md` by path" must use the fallback.)
  2. `_apply_inplace_record`: there are two lines that read `record.worktree_path / "status.md"` (for `read_parent_branch` at ~line 302 and for `_read_phase` at ~line 330). Apply the same fallback pattern to both: resolve to `task/status.md` if it exists, otherwise `status.md`.
  3. `apply_plan`: after the main cleanup loop (after all `to_remove_done + to_remove_abandoned` records are processed), add a dangling-junction check for hub `.active`. Also add `import os` to the module-level imports section at the top of `millpy-cleanup.py` (not inline in the function):
     ```python
     active_link = hub_root / ".active"
     if os.path.lexists(str(active_link)) and not active_link.is_dir():
         _junction.remove(active_link)
         print(f"[cleanup] removed dangling .active junction: {active_link}", file=sys.stderr)
     ```
     Use `os.path.lexists` (not `Path.exists` or `Path.is_symlink`) — NTFS junctions are not symlinks; `Path.exists()` follows the junction and returns `False` when the target is gone, and `is_symlink()` is always `False` for junctions. `lexists` returns `True` for a broken junction without following the reparse point. This handles the case where the last portal entry was removed (chain `.active` → `portals/<slug>` → `wiki/active/<slug>/` is broken). It does NOT remove `.active` when another task's portal is still valid.
  4. Update module docstring to remove references to `.others` or `.millhouse/wiki` in favour of `.portals` / `.wiki` (if any such references exist in the module docstring).
- **Commit:** `feat(millpy-cleanup): task/status.md fallback; remove dangling hub .active after sweep`

### Card 11: `millpy-migrate-layout.py` — `--step rename-junctions`

- **Context:**
  - `plugins/mill/scripts/_junction.py`
  - `plugins/mill/scripts/_setup.py`
  - `plugins/mill/scripts/_gitignore.py`
  - `plugins/mill/scripts/_spawn_core.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/scripts/_timestamp.py`
  - `plugins/mill/scripts/millpy-spawn.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-migrate-layout.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. Add `import _setup, _spawn_core, _gitignore, _config, _timestamp` to the imports section. Extend the existing `from _paths import resolve_main_worktree_root, resolve_git_root` line to also import `resolve_container_path, resolve_wiki_path`.
  2. Update the `argparse` argument definition: add a `--step` argument:
     ```python
     parser.add_argument(
         "--step",
         choices=["rename-junctions"],
         default=None,
         help="Which migration step to run. Omit to run the full legacy-layout migration.",
     )
     ```
  3. In `main()`, after `args = parser.parse_args()`, add a dispatch: if `args.step == "rename-junctions"`, call `_step_rename_junctions(args)` and return; otherwise fall through to the existing migration logic.
  4. Add function `_step_rename_junctions(args: argparse.Namespace) -> None`:
     ```
     a. Resolve paths: git_root = resolve_git_root(); wiki_path = resolve_wiki_path(git_root); container = resolve_container_path(git_root); hub_root = resolve_main_worktree_root(git_root).
     b. Load config: `cfg = _config.load_config(wiki_path, hub_root)` (unconditional — `load_config` has signature `(wiki_path, worktree_root)` and internally constructs the local config path; it is lenient when the file is absent).
     c. Open log file at `.scratch/migrate-rename-junctions-<ts>.log` (skip in dry-run).
     d. Discover active task worktrees: active_wts = _spawn_core.discover_active_worktrees(container / "wts").
     e. For each (wt_path, slug, title) in active_wts:
        - Strip junctions from worktree: call `_junction.strip_all_in_worktree(wt_path, cfg.get("junctions", {}))` (strips new-layout junctions if they exist). Then for old-layout junctions: `for name in [".millhouse/wiki", ".others", ".active"]: _junction.remove(wt_path / name)` — call `_junction.remove` directly without a pre-check (`remove` uses `os.path.lexists` internally and is a no-op when absent).
        - Remove old portals entry: _junction.remove(container / "portals" / slug) (tolerate already-gone).
        - Create wiki/active/<slug>/task.md and commit+push: `ts = _timestamp.now_utc_compact(); _spawn_core.write_wiki_active_task_md(wiki_path, slug, title, ts)`. This creates the dir and task.md idempotently and commits them to the wiki.
        - Create new portals entry: `_junction.create(target=wiki_path / "active" / slug, link_path=container / "portals" / slug)`.
        - Recreate junctions: `_setup.create_hub_links(wt_path, wiki_path, tokens)` where `tokens` matches the full `_build_tokens` pattern from `millpy-spawn.py`: `{"SLUG": slug, "WIKI_PATH": str(wiki_path), "CONTAINER_PATH": str(container), "HUB_PATH": str(hub_root), "CWD_PATH": str(wt_path), "REPO": hub_root.name}`. Construct via `_spawn_core._build_tokens(...)` if exposed, or replicate the dict here. Missing tokens cause `_junction.resolve_target` to raise `ValueError` if any junction template references them.
        - Move working state to task/: check `git -C <wt_path> status --porcelain` is empty. If not: log warning "skipping task/ move for <slug>: working tree dirty", continue. If clean: first run `(wt_path / "task").mkdir(exist_ok=True)` (`git mv` does not create parent directories). Then for src_name in ["status.md", "discussion.md", "plan", "reviews"]: src = wt_path / src_name; dst = wt_path / "task" / src_name; if src.exists(): run `git -C <wt_path> mv <src> <dst>`. After staging all four moves (for whichever files exist), issue a single commit: `git -C <wt_path> commit -m "migrate: move working state to task/ for {slug}"`. Do NOT commit inside the per-file loop.
     f. For hub worktree:
        - Strip old junctions: for name in [".millhouse/wiki", ".others", ".active"]: manually remove if exists. Also call _junction.strip_all_in_worktree(hub_root, cfg.get("junctions", {})) for any new-layout junctions.
        - Recreate hub junctions: `_setup.create_hub_links(hub_root, wiki_path, hub_tokens)` where `hub_tokens = {"WIKI_PATH": str(wiki_path), "CONTAINER_PATH": str(container), "HUB_PATH": str(hub_root), "CWD_PATH": str(hub_root), "REPO": hub_root.name}` (no SLUG — hub scope; `<SLUG>`-templated junctions are silently skipped by the token-scope filter).
        - Update .gitignore: hub_gitignore = hub_root / ".gitignore"; _gitignore.upsert(hub_gitignore, _gitignore.GLOB_ENTRIES).
        - Do NOT recreate .active — leave absent; the next mill-claim/mill-spawn will create it.
     g. In dry-run mode: log all planned operations but perform no writes. Return.
     h. Print summary: "Rename-junctions migration complete. N task worktrees updated. Run /mill-setup to refresh hardlinks."
     ```
     Use existing `_log(msg, log_fh, dry_run)` and `_run(argv, log_fh, dry_run, cwd=...)` helpers throughout.
  5. Update the module docstring to add: "Pass `--step rename-junctions` to migrate an existing container from the old `.millhouse/wiki + .others + .active` junction layout to the new `.wiki + .portals` layout."
- **Commit:** `feat(millpy-migrate): --step rename-junctions sub-command`

### Card 12: `test-cleanup.py` + `test-worktree.py` — new test cases

- **Context:**
  - `plugins/mill/scripts/millpy-cleanup.py`
  - `plugins/mill/scripts/_worktree.py`
  - `plugins/mill/scripts/_junction.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-cleanup.py`
  - `plugins/mill/unit_tests/test-worktree.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  **test-cleanup.py:**
  1. Add test `test_build_plan_reads_task_status_md`: create a worktree fixture that has `task/status.md` (not `status.md` at root) with phase `done`. Call `build_plan`. Assert the slug ends up in `to_remove_done`. This confirms the new primary path is read.
  2. Add test `test_build_plan_falls_back_to_root_status_md`: create a worktree fixture that has `status.md` at the root (legacy layout, no `task/` dir) with phase `done`. Call `build_plan`. Assert the slug ends up in `to_remove_done`. This confirms the fallback works for legacy worktrees.
  3. Add test `test_apply_plan_removes_dangling_active_junction`: use the worktree mode mocking pattern from the existing `test apply_plan — portal entry removed for worktree record`. Scenario A: `os.path.lexists` returns `False` for the `.active` path → assert `_junction.remove` is NOT called with `hub_root / ".active"` (no junction present). Scenario B: `os.path.lexists` returns `True` and `Path.is_dir()` returns `False` (dangling junction — target gone) → assert `_junction.remove` IS called with `hub_root / ".active"`. Use `patch("os.path.lexists", ...)` (not `patch.object(Path, "exists")`) and `patch.object(Path, "is_dir")` to control the `os.path.lexists(str(active_link)) and not active_link.is_dir()` condition.
  4. Add test `test_apply_inplace_record_reads_task_status_md`: create an in-place worktree fixture with `task/status.md` (not `status.md` at root) carrying both a `parent_branch:` field and `phase: done`. Call `_apply_inplace_record` (with whatever mocking the existing in-place tests use) and verify both `read_parent_branch` and `_read_phase` resolve to the `task/` location (e.g. assert that the parent branch returned matches what was written to `task/status.md`, not stale data from a root-level `status.md`). This exercises the fallback path added in Card 10 Req 2.

  **test-worktree.py:**
  5. Add test `test_copy_millhouse_excludes_wiki_and_active`: verify `copy_millhouse(src, dst, exclude={"wiki", "active"})` does not copy items named `wiki` or `active` inside `.millhouse/`. (This test already effectively exists in the file — verify by checking what `test-worktree.py` currently tests; if not present, add it.) Use a tempdir fixture.
- **Commit:** `test: task/status.md fallback; dangling .active cleanup; worktree copy exclusions`

## Batch Tests

`python plugins/mill/unit_tests/run-all.py` must exit 0. All unit tests pass.
