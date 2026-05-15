# Plan: 55 (A) -- Fix hardcoded _mill/ paths and mill-setup junction/config bugs

```yaml
task: 55 (A) -- Fix hardcoded _mill/ paths and mill-setup junction/config bugs
slug: mill-path-hardcodes
approved: false
started: 20260515-073621
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: unit-test
    file: 01-unit-test.md
    depends-on: []
    verify: python plugins/mill/unit_tests/run-all.py

  - number: 2
    name: mill-go-paths
    file: 02-mill-go-paths.md
    depends-on: []
    verify: null

  - number: 3
    name: finalize-merge-paths
    file: 03-finalize-merge-paths.md
    depends-on: []
    verify: null

  - number: 4
    name: start-plan-paths
    file: 04-start-plan-paths.md
    depends-on: []
    verify: null

  - number: 5
    name: mill-setup-fixes
    file: 05-mill-setup-fixes.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: Path setup block pattern

- **Decision:** Each affected SKILL.md gets a "Path Setup" sub-step that loads config via `_config.load_config(wiki_path, worktree_root)` (already resolved at entry) and derives path variables: `status_path`, `plan_dir`, `overview_path`, `reviews_dir`, `task_dir` (= `status_path.parent`). All subsequent path references use these variables. For reads, use `_paths.resolve_task_path(worktree_root, cfg['paths']['X'])`. For writes of new state, use `worktree_root / cfg['paths']['X']` (config-canonical, no compat fallback).
- **Rationale:** Centralizes config loading; compat shim applied consistently; ensures git commands use resolved absolute paths (which handle `task/` legacy worktrees).
- **Applies to:** all batches except unit-test

### Decision: Cleanliness snapshot exception

- **Decision:** The cleanliness snapshot path in mill-go/SKILL.md (`<worktree>/_mill/.cleanliness-snapshot-<batch_name>.txt`) must keep its `_mill/` literal and NOT be replaced with `task_dir`. `millpy-implement.py` writes this file unconditionally to `_mill/` and is out of scope — replacing only the SKILL.md read reference would cause a read/write mismatch on legacy `task/` worktrees.
- **Rationale:** Both ends (writer + reader) must agree on the path; changing only the SKILL.md side breaks the contract silently.
- **Applies to:** mill-go-paths

### Decision: git rm uses task_dir

- **Decision:** Replace `git rm -r _mill/` with `git -C <worktree> rm -r <task_dir>` where `task_dir = status_path.parent`. The resolved `status_path` determines whether the directory is `_mill/` or `task/`.
- **Rationale:** The relative literal `_mill/` fails on legacy `task/` worktrees.
- **Applies to:** finalize-merge-paths

## All Files Touched

- `plugins/mill/skills/mill-finalize/SKILL.md`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-merge/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/skills/mill-setup/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/unit_tests/test-resolve-task-path.py`
