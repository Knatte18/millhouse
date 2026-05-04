# Batch: Spawn and worktree destination-side hub mirroring

```yaml
task: 'script-invocation-hygiene — Scripts: cwd not git-root, plugin cache not source repo'
batch: Spawn and worktree destination-side hub mirroring
cards: 4
verify: python plugins/mill/unit_tests/run-all.py
depends-on: [foundation, simple-fixes]
```

## Batch Scope

This batch fixes the two scripts that produce new worktrees (`millpy-spawn.py` and `millpy-worktree.py`). The fix has two interlocking parts: source-side (read source hub state via `resolve_hub_path()`, not `git_root`), and destination-side (write the new worktree's full hub state at `dest_hub = worktree_path / hub_subpath`, plus a bootstrap stub at `worktree_path / ".millhouse"` when `hub_subpath != "."`). The destination-side mirroring is the load-bearing piece for subfolder-install support — without it, every newly-spawned worktree would put `.millhouse/`, `.vscode/`, and active markers at the wrong location. Tests for spawn cover three cases: standard layout regression, subfolder-install destination layout, and a discovery round-trip that confirms terminal/vscode-style discovery (`_spawn_core.discover_active_worktrees` + `_config.load_config` + `_paths.resolve_hub_relative_path`) works end-to-end on the new layout. This batch depends on `foundation` (uses `resolve_hub_path`, the renamed `load_config`, and the stub-aware `discover_active_worktrees`) and on `simple-fixes` (the same fix pattern is established in earlier scripts so the implementer can follow it).

Batch-local decisions:
- The bootstrap stub is written AFTER `_worktree.copy_millhouse` has copied the source's `.millhouse/` to the destination, and AFTER all other hub-state writes complete, so a partial spawn never leaves a stub pointing at an empty hub directory.
- `_build_tokens` in spawn is called twice — once with `resolve_hub_path()` for source-side junction resolution (the spawn's own `tokens` map for `_setup.create_hub_links` invariants), and once with `dest_hub` for destination-side writes. The function signature renames its first param from `git_root` to `hub_path` to make this explicit.
- `millpy-worktree.py` does NOT write an `active.slug.md` marker (it does not claim a task). It still writes the bootstrap stub when `hub_subpath != "."` so terminal/vscode can later resolve the layout.

## Cards

### Card 9: Fix millpy-spawn.py source-side

- **Reads:**
  - `plugins/mill/scripts/millpy-spawn.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_config.py`
- **Modifies:**
  - `plugins/mill/scripts/millpy-spawn.py`
- **Creates:** none
- **Requirements:** Add `resolve_hub_path` to the `from _paths import ...` line. Rename the first parameter of `_build_tokens` from `git_root` to `hub_path` and update its body: `"HUB_PATH": str(hub_path)`, `"CWD_PATH": str(hub_path)` (`CWD_PATH` was previously `Path.cwd()` which happens to equal `hub_path` when called from claim/color/spawn, but make it explicit), `"CONTAINER_PATH": str(resolve_container_path(hub_path))` — note: `resolve_container_path` walks up via git, so it works whether passed `hub_path` or `git_root`; this is intentional, the container is anchored on the main worktree root, not on cwd, but `resolve_container_path` accepts any path inside the repo, so passing `hub_path` is correct, `"REPO": hub_path.name`. At line 109, change `cfg = _load_config(wiki_path, git_root)` to `cfg = _load_config(wiki_path, resolve_hub_path())`. At line 155, change `tokens = _build_tokens(git_root, wiki_path, slug=slug)` to `tokens = _build_tokens(resolve_hub_path(), wiki_path, slug=slug)`. At line 190, change `src=git_root / ".millhouse"` to `src=resolve_hub_path() / ".millhouse"`. Verify the local `_load_config` wrapper at line 56-65 still works (it forwards to `_load_config_lenient` aka `_config.load_config`; the parameter rename in `_config.py` is positional, so the wrapper's call `return _load_config_lenient(wiki_path, git_root)` continues to work — just rename the local wrapper's parameter from `git_root` to `worktree_root` for consistency). Leave every other use of `git_root` (subprocess invocations, parent-branch capture, worktree create call) untouched.
- **Commit:** `fix(millpy-spawn): source-side — read source hub state via resolve_hub_path()`

### Card 10: Fix millpy-spawn.py destination-side + bootstrap stub

- **Reads:**
  - `plugins/mill/scripts/millpy-spawn.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_setup.py`
  - `plugins/mill/scripts/_vscode.py`
  - `plugins/mill/scripts/_spawn_core.py`
  - `plugins/mill/scripts/_worktree.py`
- **Modifies:**
  - `plugins/mill/scripts/millpy-spawn.py`
- **Creates:** none
- **Requirements:** After Card 9's source-side fix, compute `hub_subpath = cfg.get("hub_relative_path", ".")` once (after `cfg = _load_config(...)` at line 109) and `dest_hub = resolve_hub_relative_path(worktree_path, hub_subpath)` (immediately after `worktree_path` is computed at line 157). When `hub_subpath != "."`, ensure `dest_hub.mkdir(parents=True, exist_ok=True)` is called before any destination write. Patch each destination write: (a) line 189-193 `_worktree.copy_millhouse(src=..., dst=worktree_path / ".millhouse", ...)` — change `dst` to `dest_hub / ".millhouse"`. (b) Build a destination-side tokens dict immediately before line 206: `dest_tokens = _build_tokens(dest_hub, wiki_path, slug=slug)`. Pass `dest_tokens` to `_setup.create_hub_links` at line 206 instead of the source-side `tokens`, and change the `target_root` argument from `worktree_path` to `dest_hub`. (c) Line 214 `_vscode.write_settings(... target=worktree_path / ".vscode" / "settings.json", ...)` — change to `target=dest_hub / ".vscode" / "settings.json"`. (d) Line 220 `_spawn_core.write_active_marker(worktree_path / ".millhouse", ...)` — change to `_spawn_core.write_active_marker(dest_hub / ".millhouse", ...)`. (e) After all destination writes complete (after line 225), if `hub_subpath != "."`, write the bootstrap stub: ensure `worktree_path / ".millhouse"` exists (`.mkdir(parents=True, exist_ok=True)`), then write `worktree_path / ".millhouse" / "config.local.yaml"` with content `f"hub_relative_path: {hub_subpath}\n"` (UTF-8 plain YAML, no extra keys). Use `yaml.safe_dump({"hub_relative_path": hub_subpath}, ...)` for safer serialization. The portal junction creation at line 200-201 stays anchored on `worktree_path` (terminal/vscode resolve `dest_hub` via the stub at launch time). The `worktrees_dir.mkdir` at line 182 is unchanged.
- **Commit:** `fix(millpy-spawn): destination-side — place hub state at dest_hub, write bootstrap stub`

### Card 11: Update test-millpy-spawn.py

- **Reads:**
  - `plugins/mill/unit_tests/test-millpy-spawn.py`
  - `plugins/mill/scripts/millpy-spawn.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/scripts/_spawn_core.py`
- **Modifies:**
  - `plugins/mill/unit_tests/test-millpy-spawn.py`
- **Creates:** none
- **Requirements:** Add three test cases. Use the existing tempfile + mock pattern (mock `_worktree.create`, `_junction.create`, `_wiki.sync_pull`, `_wiki.write_commit_push`, `_subprocess_util.run`, `_vscode.write_settings`'s side effects, and any other subprocess- or git-touching helper). Test 1 — standard layout regression: source config has no `hub_relative_path` (or has it set to `"."`); after running spawn's main path (or a refactored helper extracted from main if needed for testability), assert `worktree_path / ".millhouse" / "active.slug.md"` exists with the expected slug, `worktree_path / ".vscode" / "settings.json"` was written via the mock with the expected target, no `worktree_path / ".millhouse" / "config.local.yaml"` stub-only file is left dangling (the file may exist as a copy of source config, but it must have all keys, not just `hub_relative_path`). Test 2 — subfolder-install: source config has `hub_relative_path: src/Models`; after spawn, assert (a) `worktree_path / "src/Models" / ".millhouse" / "active.slug.md"` exists with the expected slug, (b) `worktree_path / "src/Models" / ".vscode" / "settings.json"` is the `_vscode.write_settings` target (assert via mock call args), (c) `worktree_path / ".millhouse" / "config.local.yaml"` exists, (d) the stub file's parsed YAML equals exactly `{"hub_relative_path": "src/Models"}` — no other keys, (e) `_setup.create_hub_links` was called with `target_root=worktree_path / "src/Models"`. Test 3 — discovery round-trip on subfolder-install layout: after Test 2 sets up the layout, call `_spawn_core.discover_active_worktrees(worktrees_dir)` and assert the worktree is returned with the right slug; also call `_config.load_config(wiki_path, worktree_path)` and assert the result includes `hub_relative_path: "src/Models"` AND the operational keys from the real config; finally call `_paths.resolve_hub_relative_path(worktree_path, hub_subpath)` and assert it equals `worktree_path / "src/Models"`. If main is not directly testable, factor out a helper (e.g. `_run_spawn_with_picked_task(picked, cfg, worktree_path, wiki_path, ...)`) inside spawn for testability — the refactor must be minimal and committed in this card.
- **Commit:** `test(millpy-spawn): add standard-layout regression, subfolder-install, and discovery round-trip`

### Card 12: Fix millpy-worktree.py + update test

- **Reads:**
  - `plugins/mill/scripts/millpy-worktree.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/unit_tests/test-millpy-worktree.py`
- **Modifies:**
  - `plugins/mill/scripts/millpy-worktree.py`
  - `plugins/mill/unit_tests/test-millpy-worktree.py`
- **Creates:** none
- **Requirements:** Apply the source-side + destination-side fix to `_cmd_create`. Add `resolve_hub_path` and `resolve_hub_relative_path` to the `from _paths import ...` line. At line 94 (`src=git_root / ".millhouse"`), change `src` to `resolve_hub_path() / ".millhouse"` and `dst` to `dest_hub / ".millhouse"` where `dest_hub = resolve_hub_relative_path(worktree_path, hub_subpath)` and `hub_subpath = cfg.get("hub_relative_path", ".")` (compute both once, immediately after `worktree_path = worktrees_dir / dir_name` at line 54). When `hub_subpath != "."`, call `dest_hub.mkdir(parents=True, exist_ok=True)` before the copy. Update the inline tokens dict at lines 107-113 to use `dest_hub` for `HUB_PATH` and `CWD_PATH` (this is the destination-side token set; `_cmd_create` only builds destination tokens because junctions are created in the new worktree, not the source), and `resolve_hub_path().name` for `REPO`. Wait — re-examine: the existing tokens dict at L107-113 mixes source and destination concepts (`CWD_PATH=str(worktree_path)`, but `HUB_PATH=str(git_root)`). After the fix, this dict's role is destination-side junction creation. Set `HUB_PATH=str(dest_hub)`, `CWD_PATH=str(dest_hub)`, `CONTAINER_PATH=str(resolve_container_path(git_root))` (container resolution stays anchored on git_root because containers are repo-level), `REPO=resolve_hub_path().name` (source's repo name carries to the destination). At line 138 (`target=worktree_path / ".vscode" / "settings.json"`), change to `target=dest_hub / ".vscode" / "settings.json"`. After all destination writes, if `hub_subpath != "."`, write the bootstrap stub at `worktree_path / ".millhouse" / "config.local.yaml"` containing exactly `{"hub_relative_path": hub_subpath}` (UTF-8 YAML via `yaml.safe_dump`). No active marker write is added (worktree-create deliberately doesn't claim a task). At the top of `main()`, the `cfg = _load_config(wiki_path, git_root)` call (line ~30, verify location) needs to update its second arg to `resolve_hub_path()` so `cfg["hub_relative_path"]` is read correctly post-Card 2. Update `test-millpy-worktree.py`: add tests mirroring Card 11's cases 1 and 2 (standard layout regression and subfolder-install destination layout). The discovery round-trip (case 3) is not added here since worktree-create produces no active marker.
- **Commit:** `fix(millpy-worktree): apply source-side + destination-side hub mirroring with stub`

## Batch Tests

Verify command: `python plugins/mill/unit_tests/run-all.py`

Covers: `test-millpy-spawn.py` (Cards 9-11), `test-millpy-worktree.py` (Card 12), and incidentally re-runs every test from foundation and simple-fixes. The Card 11 case 3 (discovery round-trip) is the load-bearing assertion for this batch — it confirms the full chain (spawn writes stub → discover reads stub → load_config merges stub + real → resolve_hub_relative_path produces correct launch_path) works end-to-end on a synthetic subfolder-install layout. After this batch, manual smoke: invoke `mill-spawn` on a repo with `hub_relative_path: .` (the standard millhouse layout) and confirm a clean spawn; if a subfolder-install fixture is available locally, repeat there.
