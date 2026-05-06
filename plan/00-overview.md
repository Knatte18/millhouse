# Plan: Restructure hub junction layout

```yaml
task: Restructure hub junction layout
slug: rename-hub-junctions
approved: false
started: 20260506-171445
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: _gitignore API simplification
    file: 01-gitignore-api.md
    depends-on: []
    verify: python plugins/mill/unit_tests/test-gitignore-phase.py
  - number: 2
    name: Spawn infrastructure and wiki config
    file: 02-spawn-wiki-config.md
    depends-on: []
    verify: python plugins/mill/unit_tests/run-all.py
  - number: 3
    name: Teardown and migration
    file: 03-teardown-migration.md
    depends-on: [2]
    verify: python plugins/mill/unit_tests/run-all.py
  - number: 4
    name: Skills and documentation
    file: 04-skills-docs.md
    depends-on: [2]
    verify: null
```

## Shared Decisions

### Decision: junctions-are-ide-only

- **Decision:** Never pass a junction path (`.wiki`, `.portals`, `.active`) to any Python helper. All resolution goes through `_paths.py`. Junctions are purely for operator IDE/terminal navigation.
- **Rationale:** Codified in CLAUDE.md path invariants. Hardcoding junction paths in scripts creates invisible dependencies that break when junctions are missing or renamed.
- **Applies to:** all batches

### Decision: wiki-edits-via-helper

- **Decision:** All edits to `wiki/config.yaml` must go through `_wiki.write_commit_push(wiki_path, ["config.yaml"], msg, slug=...)` after editing the file in the wiki clone. Never raw-edit and leave uncommitted.
- **Rationale:** The wiki is a shared git repo; uncommitted edits are invisible to other machines and break concurrent operations.
- **Applies to:** batch 2

### Decision: task-status-path-fallback

- **Decision:** Any consumer that reads `status.md` by path must first try `worktree_root / "task" / "status.md"`, falling back to `worktree_root / "status.md"` for legacy worktrees not yet migrated. Writers always write to the `task/` location.
- **Rationale:** During transition (after code deploy but before `millpy-migrate-layout.py --step rename-junctions` runs), active task worktrees still have the old layout. Read-path fallback keeps mill-cleanup and mill-merge working on both layouts.
- **Applies to:** batches 2, 3

### Decision: portals-target-is-wiki-active

- **Decision:** `container/portals/<slug>` junctions now point to `wiki/active/<slug>/` (not `wts/<slug>`). The hub `.active` junction points to `container/portals/<slug>` which then points to the wiki state dir. This indirection is intentional — the wiki dir is the authoritative state, and the portal is a stable redirect.
- **Rationale:** Gives direct IDE/terminal access to the wiki state for the current task from both the hub (via `.active`) and the task worktree (via `.portals`). The old semantics (portals → wts/<slug>) just navigated to the same worktree you were already in.
- **Applies to:** batches 2, 3

## All Files Touched

- `CLAUDE.md`
- `plugins/mill/scripts/_gitignore.py`
- `plugins/mill/scripts/_spawn_core.py`
- `plugins/mill/scripts/millpy-claim.py`
- `plugins/mill/scripts/millpy-cleanup.py`
- `plugins/mill/scripts/millpy-migrate-layout.py`
- `plugins/mill/scripts/millpy-spawn.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-merge-in/SKILL.md`
- `plugins/mill/skills/mill-merge/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/skills/mill-setup/SKILL.md`
- `plugins/mill/skills/mill-spawn/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/unit_tests/test-cleanup.py`
- `plugins/mill/unit_tests/test-gitignore-phase.py`
- `plugins/mill/unit_tests/test-millpy-claim.py`
- `plugins/mill/unit_tests/test-millpy-spawn.py`
- `plugins/mill/unit_tests/test-setup-hub-links.py`
- `plugins/mill/unit_tests/test-spawn-core.py`
- `plugins/mill/unit_tests/test-worktree.py`
- `wiki/config.yaml`
