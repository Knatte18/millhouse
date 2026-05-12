# Plan: 33 (A) -- Working-dir rename + portals redesign + junction cleanup

```yaml
task: 33 (A) -- Working-dir rename + portals redesign + junction cleanup
slug: mill-paths-cleanup
approved: false
started: 20260512-133522
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: resolve-task-path-shim
    file: 01-resolve-task-path-shim.md
    depends-on: []
    verify: python plugins/mill/unit_tests/run-all.py

  - number: 2
    name: task-to-mill-rename
    file: 02-task-to-mill-rename.md
    depends-on: [1]
    verify: python plugins/mill/unit_tests/run-all.py

  - number: 3
    name: portals-junctions-hardlinks
    file: 03-portals-junctions-hardlinks.md
    depends-on: [2]
    verify: python plugins/mill/unit_tests/run-all.py

  - number: 4
    name: cleanup-orphan-scan
    file: 04-cleanup-orphan-scan.md
    depends-on: [3]
    verify: python plugins/mill/unit_tests/run-all.py

  - number: 5
    name: unicode-output-cleanup
    file: 05-unicode-output-cleanup.md
    depends-on: [4]
    verify: python plugins/mill/unit_tests/run-all.py

  - number: 6
    name: skills-docs-claude-md
    file: 06-skills-docs-claude-md.md
    depends-on: [4]
    verify: null
```

## Shared Decisions

### Decision: compat-shim-semantics

- **Decision:** `resolve_task_path(worktree_root: Path, cfg_relative_path: str) -> Path` lives in `_paths.py`. Given a path starting with `_mill/`, checks if `worktree_root / cfg_relative_path` exists; if not but the equivalent `task/` path exists, returns the `task/` path and prints `[compat] falling back to task/ for <path>` to stderr. If neither exists, returns the `_mill/` path (caller handles missing-file). Works for both file paths and directory paths.
- **Rationale:** In-flight worktrees still have `task/status.md` etc. after the config rename to `_mill/`. The shim bridges the gap transparently without requiring operators to rename their task/ dirs before continuing. The `exists()` check works for both files (Path.exists()) and directories (Path.is_dir() is a subset of Path.exists()).
- **Applies to:** batches 1, 2

### Decision: portal-target-after-redesign

- **Decision:** `portals/<slug>` points directly at `wts/<slug>/_mill/`, not `wiki/active/<slug>/`. Hub `.active` points at `portals/<slug>`. Per-worktree `.active` also points at `portals/<slug>`. The `portals/<slug>` junction is created by mill-spawn/mill-claim; it is a junction to a real directory that must exist first. New `.portals` junction in every worktree (hub-scope and per-worktree) points at `<container>/portals/`.
- **Rationale:** Direct path removes wiki from the portal chain. No wiki write on spawn.
- **Applies to:** batch 3

### Decision: orphan-portal-oracle

- **Decision:** A portal entry `portals/<X>` is stale if (a) `X` is not an `[active]` slug in Home.md, OR (b) the junction target path does not exist. Two-condition oracle: either condition alone is sufficient to mark stale.
- **Rationale:** Neither condition alone catches all cases. Target-not-exists misses live hub-self-portals; slug-not-in-Home.md misses worktrees deleted out-of-band. The union catches all three failure modes.
- **Applies to:** batch 4

### Decision: ascii-only-output

- **Decision:** All `print()` and `_log()` output strings use ASCII only. Em-dash (`—`) → ` -- `, right-arrow (`→`) → ` -> `. Docstrings and comments are exempt.
- **Rationale:** Windows cp1252 terminals crash on non-ASCII in stdout/stderr.
- **Applies to:** batch 5

## All Files Touched

- `CLAUDE.md`
- `plugins/mill/doc/task-files-contract.md`
- `plugins/mill/scripts/_inplace.py`
- `plugins/mill/scripts/_paths.py`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/scripts/_spawn_core.py`
- `plugins/mill/scripts/millpy-abandon.py`
- `plugins/mill/scripts/millpy-claim.py`
- `plugins/mill/scripts/millpy-cleanup.py`
- `plugins/mill/scripts/millpy-implement-holistic.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/scripts/millpy-migrate-layout.py`
- `plugins/mill/scripts/millpy-spawn.py`
- `plugins/mill/scripts/millpy-terminal.py`
- `plugins/mill/skills/git-pr/SKILL.md`
- `plugins/mill/skills/mill-autofix/SKILL.md`
- `plugins/mill/skills/mill-claim/SKILL.md`
- `plugins/mill/skills/mill-finalize/SKILL.md`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-merge-in/SKILL.md`
- `plugins/mill/skills/mill-merge/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/skills/mill-resume/SKILL.md`
- `plugins/mill/skills/mill-setup/SKILL.md`
- `plugins/mill/skills/mill-spawn/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/skills/workflow/SKILL.md`
- `plugins/mill/templates/wiki-config.yaml`
- `plugins/mill/unit_tests/test-abandon.py`
- `plugins/mill/unit_tests/test-cleanliness.py`
- `plugins/mill/unit_tests/test-cleanup.py`
- `plugins/mill/unit_tests/test-implementer-common.py`
- `plugins/mill/unit_tests/test-millpy-claim.py`
- `plugins/mill/unit_tests/test-millpy-spawn.py`
- `plugins/mill/unit_tests/test-paths.py`
- `plugins/mill/unit_tests/test-spawn-core.py`
- `wiki/config.yaml`
