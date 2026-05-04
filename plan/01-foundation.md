# Batch: Foundation helpers + two-step readers

```yaml
task: 'script-invocation-hygiene — Scripts: cwd not git-root, plugin cache not source repo'
batch: Foundation helpers + two-step readers
cards: 4
verify: python plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

This batch delivers the four foundational helpers and protocol changes that every subsequent batch consumes. It adds `resolve_hub_path()` as the single cwd-as-hub entry point, renames and extends `_config.load_config` with a two-step stub-aware read, extends `_paths.resolve_wiki_path` with the same protocol, and updates `_spawn_core.discover_active_worktrees` to use the stub-aware read when scanning worktrees. All four changes are accompanied by updated unit tests. The next batch (`simple-fixes`) imports `resolve_hub_path` directly, and `spawn-worktree-dst` depends on the renamed `load_config` parameter and the two-step protocol.

Batch-local decisions:
- The two-step read in `_config.load_config` deep-merges the stub first, then the real config on top, so the returned dict includes `hub_relative_path` from the stub AND all operational keys from the real config.
- `resolve_wiki_path` reads `hub_relative_path` from the stub but does NOT merge the stub into the returned wiki path — it only uses `hub_relative_path` to locate the real config file that contains `paths.wiki:`.
- `discover_active_worktrees` silently skips worktrees whose stub is malformed or whose real `.millhouse/` is absent; this preserves the existing "skip on error" behavior.

## Cards

### Card 1: Add `_paths.resolve_hub_path()`

- **Reads:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/unit_tests/test-paths.py`
- **Modifies:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/unit_tests/test-paths.py`
- **Creates:** none
- **Requirements:** Add `resolve_hub_path(cwd: Path | None = None) -> Path` to `_paths.py`. The body is one line: `return (cwd or Path.cwd()).resolve()`. Add a one-line docstring: "Return the hub directory — assumes CC's cwd equals the hub when mill scripts run." Export it in `__all__`. Update the module-level `Public API:` docstring with a new `resolve_hub_path(cwd)` entry. Add three tests to `test-paths.py` inside the existing `main()` function: (1) call with no argument and assert the result equals `Path.cwd().resolve()`; (2) call with an explicit absolute path and assert it is returned resolved; (3) call with a relative path (use a tempdir parent) and assert it is resolved to an absolute path. Print `PASS` lines in the existing test style.
- **Commit:** `feat(_paths): add resolve_hub_path() — cwd-as-hub single point of truth`

### Card 2: Fix `_config.load_config` — rename + two-step read

- **Reads:**
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/unit_tests/test-config.py`
- **Modifies:**
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/unit_tests/test-config.py`
- **Creates:** none
- **Requirements:** In `_config.py`: rename the third parameter of `load_config` from `git_root` to `worktree_root` (positional, same slot). Implement two-step stub-aware read replacing the single `local_path` read: (1) read `worktree_root / ".millhouse" / "config.local.yaml"` (call it `stub_path`); if it exists, `yaml.safe_load` it, deep-merge the stub data into `cfg`, capture `hub_subpath = stub_data.get("hub_relative_path", ".")`; (2) if `hub_subpath != "."`, compute `real_path = worktree_root / hub_subpath / ".millhouse" / "config.local.yaml"`; if it exists, `yaml.safe_load` it, deep-merge into `cfg`. Update the module docstring `Exports` section (`git_root` → `worktree_root`). Update the function docstring accordingly. In `test-config.py`: rename the `hub` variable to `worktree_root` (or `wt_root`) in all three existing `load_config` tests so the intent is clear. Add two new tests: (a) subfolder-install layout — create a tempdir with a stub at `<wt_root> / .millhouse / config.local.yaml` containing `hub_relative_path: sub/hub` and nothing else; create the real config at `<wt_root> / sub/hub / .millhouse / config.local.yaml` containing operational keys; call `load_config(wiki, wt_root)` and assert both `hub_relative_path` (from stub) and the real config keys are in the result; (b) stub-only (real config absent) — stub has `hub_relative_path: sub/hub`; assert `hub_relative_path` is in result and real config keys are absent (falls back to wiki config for everything else).
- **Commit:** `fix(_config): rename git_root→worktree_root, implement two-step stub-aware read`

### Card 3: Fix `_paths.resolve_wiki_path` — two-step stub-aware read

- **Reads:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/unit_tests/test-paths.py`
- **Modifies:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/unit_tests/test-paths.py`
- **Creates:** none
- **Requirements:** In `_paths.py`, update `resolve_wiki_path(git_toplevel)`: (1) read stub at `git_toplevel / ".millhouse" / "config.local.yaml"` for `hub_relative_path` (default `"."`; missing file → `"."`); (2) compute `hub = git_toplevel` when `hub_subpath == "."`, else `hub = git_toplevel / hub_subpath`; (3) if `hub != git_toplevel` and `hub / ".millhouse" / "config.local.yaml"` exists, read it for `paths.wiki:`; otherwise use the already-read stub content for `paths.wiki:` (the existing logic for the override check); (4) fall back to `resolve_path("wiki", main_root)` as before. Remove the docstring lines 293-297 that claim "The local config file is read from `git_toplevel` (correct — each worktree carries its own `.millhouse/`)" and replace with "The local config read is stub-aware: when a worktree carries a stub with `hub_relative_path`, the `paths.wiki:` override is read from the real config at `hub / .millhouse / config.local.yaml`." Update the module-level `resolve_wiki_path(git_toplevel)` docstring entry to reflect the two-step. In `test-paths.py`, add two new tests after the existing walk-up tests: (a) subfolder-install stub present — `git_toplevel / .millhouse / config.local.yaml` has `hub_relative_path: sub/hub`; real config at `git_toplevel / sub/hub / .millhouse / config.local.yaml` has `paths.wiki: /override/wiki`; patch `resolve_main_worktree_root` and assert result equals `/override/wiki`; (b) subfolder-install stub present but no real config — result falls back to sibling default. All existing tests must still pass (they use no stub, so `hub_subpath = "."` → same behavior as before).
- **Commit:** `fix(_paths): resolve_wiki_path uses two-step stub-aware read for subfolder-install`

### Card 4: Fix `_spawn_core.discover_active_worktrees` — two-step stub-aware read

- **Reads:**
  - `plugins/mill/scripts/_spawn_core.py`
  - `plugins/mill/scripts/_active.py`
  - `plugins/mill/unit_tests/test-spawn-core.py`
- **Modifies:**
  - `plugins/mill/scripts/_spawn_core.py`
  - `plugins/mill/unit_tests/test-spawn-core.py`
- **Creates:** none
- **Requirements:** In `_spawn_core.py`, update `discover_active_worktrees`: replace `mill_dir = entry / ".millhouse"` and the direct `_active.read_all(mill_dir)` call with a two-step stub-aware read: (1) read `entry / ".millhouse" / "config.local.yaml"` for `hub_relative_path` (default `"."`; missing file or YAML parse error → `"."`; wrap in `try/except`); (2) compute `hub_mill_dir = entry / hub_subpath / ".millhouse"` (or just `entry / ".millhouse"` when `hub_subpath == "."`); (3) call `_active.read_all(hub_mill_dir)` and continue as before (skip on `ActiveError`). Update the docstring to note the stub-aware discovery. In `test-spawn-core.py`, add a test for `discover_active_worktrees` with subfolder-install layout: build a tempdir with a stub at `entry / .millhouse / config.local.yaml` (containing `hub_relative_path: src/hub`) and a valid active marker at `entry / src/hub / .millhouse /` (using `_active.write`); assert the worktree is found and the slug matches. The existing standard-layout test (no stub) must still pass.
- **Commit:** `fix(_spawn_core): discover_active_worktrees uses two-step stub-aware read`

## Batch Tests

Verify command: `python plugins/mill/unit_tests/run-all.py`

Covers: `test-paths.py` (Cards 1, 3), `test-config.py` (Card 2), `test-spawn-core.py` (Card 4). All existing tests in run-all.py must continue to pass — the `_config.load_config` rename is positional and all call sites within the scripts dir use keyword-free positional calls, so no existing test breaks on the rename alone.
