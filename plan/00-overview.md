# Plan: script-invocation-hygiene — Scripts: cwd not git-root, plugin cache not source repo

```yaml
task: 'script-invocation-hygiene — Scripts: cwd not git-root, plugin cache not source repo'
slug: script-invocation-hygiene
approved: true
started: '20260504-123651'
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - name: foundation
    file: 01-foundation.md
    depends-on: []
    verify: python plugins/mill/unit_tests/run-all.py
  - name: simple-fixes
    file: 02-simple-fixes.md
    depends-on: [foundation]
    verify: python plugins/mill/unit_tests/run-all.py
  - name: spawn-worktree-dst
    file: 03-spawn-worktree-dst.md
    depends-on: [foundation, simple-fixes]
    verify: python plugins/mill/unit_tests/run-all.py
  - name: docs-gitignore
    file: 04-docs-gitignore.md
    depends-on: []
    verify: python plugins/mill/unit_tests/test-gitignore-phase.py
```

## Shared Decisions

### Decision: resolve_hub_path as single hub-resolution entry point

- **Decision:** All 8 cwd-vs-git-root script sites call `_paths.resolve_hub_path()` instead of using `git_root` for hub-state path construction. The helper returns `(cwd or Path.cwd()).resolve()`, documenting the invariant "CC's cwd is the hub when these scripts run."
- **Rationale:** Single point of truth for the cwd-as-hub assumption. If the assumption is ever loosened (e.g. walk-up to find `.millhouse/`), one helper changes, not eight call sites.
- **Applies to:** foundation, simple-fixes, spawn-worktree-dst

### Decision: Two-step stub-aware read protocol

- **Decision:** Every function that discovers the hub from a worktree root (including callers that receive `git_toplevel`, not cwd) implements: (1) read stub at `worktree_root / ".millhouse" / "config.local.yaml"` for `hub_relative_path` (default `"."`); (2) if `hub_subpath != "."`, read the real config from `worktree_root / hub_subpath / ".millhouse" / "config.local.yaml"`. When `hub_subpath = "."` the stub IS the real config; step 2 is skipped. Functions affected: `_config.load_config`, `_paths.resolve_wiki_path`, `_spawn_core.discover_active_worktrees`, `millpy-cleanup.py` L102 direct read.
- **Rationale:** Discovery functions (terminal, cleanup) scan worktrees without per-worktree hub knowledge. The bootstrap stub (written by spawn when `hub_subpath != "."`) provides the pointer.
- **Applies to:** foundation, simple-fixes, spawn-worktree-dst

### Decision: _config.load_config merges stub then real config

- **Decision:** `_config.load_config` merges the stub first (deep-merge step 1 into wiki config), then if `hub_subpath != "."` merges the real config on top (deep-merge step 2). This ensures `hub_relative_path` from the stub is present in the returned dict (callers like terminal read it), while all operational config keys come from the real config.
- **Rationale:** Callers need `hub_relative_path` to compute `launch_path`. The real config at the hub does not repeat this key. Merging both (stub then real) makes the returned dict self-sufficient.
- **Applies to:** foundation

### Decision: Bootstrap stub only for hub_subpath != "."

- **Decision:** Spawn (and worktree create) writes `worktree_path / ".millhouse" / "config.local.yaml"` containing only `hub_relative_path: <subpath>` when and only when `hub_subpath != "."`. Standard layout writes no stub; the single `.millhouse/` at worktree root serves both roles. When `hub_subpath != "."`, the full `.millhouse/` (with config, active marker, junctions) lands at `dest_hub = worktree_path / hub_subpath`, and the stub sits at `worktree_path / ".millhouse"`.
- **Rationale:** Minimal change. No extra file for the common case. Stub is a navigation pointer, not a config duplicate.
- **Applies to:** spawn-worktree-dst

### Decision: No walk-up logic in resolve_hub_path

- **Decision:** `resolve_hub_path()` returns `Path.cwd().resolve()` today. Walk-up logic (traversing parent directories to find `.millhouse/`) is explicitly deferred.
- **Rationale:** YAGNI. The existing codebase assumes CC sets cwd to the hub. Walk-up is a future task.
- **Applies to:** all batches

## All Files Touched

- `.gitignore`
- `CLAUDE.md`
- `plugins/mill/scripts/_config.py`
- `plugins/mill/scripts/_gitignore.py`
- `plugins/mill/scripts/_paths.py`
- `plugins/mill/scripts/_spawn_core.py`
- `plugins/mill/scripts/millpy-claim.py`
- `plugins/mill/scripts/millpy-cleanup.py`
- `plugins/mill/scripts/millpy-color.py`
- `plugins/mill/scripts/millpy-fetch-issues.py`
- `plugins/mill/scripts/millpy-spawn.py`
- `plugins/mill/scripts/millpy-worktree.py`
- `plugins/mill/skills/mill-add/SKILL.md`
- `plugins/mill/skills/mill-setup/SKILL.md`
- `plugins/mill/unit_tests/test-config.py`
- `plugins/mill/unit_tests/test-gitignore-phase.py`
- `plugins/mill/unit_tests/test-millpy-claim.py`
- `plugins/mill/unit_tests/test-millpy-color.py`
- `plugins/mill/unit_tests/test-millpy-spawn.py`
- `plugins/mill/unit_tests/test-millpy-worktree.py`
- `plugins/mill/unit_tests/test-paths.py`
- `plugins/mill/unit_tests/test-spawn-core.py`
