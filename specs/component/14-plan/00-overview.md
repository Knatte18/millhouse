# Plan: junction-rule enforcement + `_paths.py` consolidation

```yaml
task: junction-rule enforcement + _paths.py consolidation
slug: 14-junction-rule-wiki-resolve
approved: false
started: 20260424-000000
parent: main
root: ""
verify: python plugins/mill/unit_tests/run-all.py && python plugins/mill/integration_tests/test-spawn.py && python plugins/mill/integration_tests/test-merge.py && python plugins/mill/integration_tests/test-plan-assets.py && python plugins/mill/integration_tests/test-go-assets.py
```

## Batch Index

```yaml
batches:
  - name: foundation
    file: 01-foundation.md
    depends-on: []
    verify: python plugins/mill/unit_tests/test-paths.py
  - name: callsite-migration
    file: 02-callsite-migration.md
    depends-on: [foundation]
    verify: python plugins/mill/integration_tests/test-spawn.py
  - name: scratch-move
    file: 03-scratch-move.md
    depends-on: []
    verify: python plugins/mill/integration_tests/test-spawn.py && python plugins/mill/integration_tests/test-merge.py
  - name: docs
    file: 04-docs.md
    depends-on: [callsite-migration, scratch-move]
    verify: null
```

`foundation` and `scratch-move` are independent and could run in parallel; `callsite-migration` needs `_paths.py` first; `docs` needs the new code shape locked so the rule text matches reality.

## Shared Decisions

### Decision: `_paths.py` imports from `_sibling.py` — never copies it

- **Decision:** `plugins/mill/scripts/_paths.py` adds `resolve_wiki_path` and `resolve_git_root`, and re-exports `resolve_path` from `_sibling` via `from _sibling import resolve_path` (plus a bare mention in `__all__` for clarity). Callers may do `from _paths import resolve_path, resolve_wiki_path, resolve_git_root` through a single import.
- **Rationale:** Preserves the identical-twin rule with `plugins/codeguide/scripts/_sibling.py` (spec 00) — the codeguide copy stays byte-for-byte aligned with mill's `_sibling.py`. Duplicating `resolve_path` into `_paths.py` would create a third copy-path to maintain.
- **Applies to:** foundation batch.

### Decision: `resolve_wiki_path` precedence is local-config-first, sibling-default-second

- **Decision:** Look up `.millhouse/config.local.yaml` at `<git-toplevel>/.millhouse/config.local.yaml`; read `paths.wiki:` (string). If present and non-empty, return that path (relative paths resolved against `<git-toplevel>`). Otherwise call `resolve_path("wiki", git_toplevel)`. If neither exists on disk, raise with a message naming both the resolved path and the override key.
- **Rationale:** Bootstrap-safe (no circular dependency — wiki-path override never lives in the wiki itself). Matches the convention from spec 00 where `.codeguide-root` overrides sibling default.
- **Applies to:** foundation + all call-sites.

### Decision: `.scratch/` at cwd-root, NOT `.millhouse/scratch/`

- **Decision:** Move the scratch location out of `.millhouse/` entirely. New path: `<cwd>/.scratch/`. `.gitignore` gains `**/.scratch/` alongside the existing `**/.millhouse/`. `_worktree.copy_millhouse`'s legacy `scratch` exclusion is dropped — scratch no longer lives inside `.millhouse/`, so the exclusion is obsolete (and fragile — name-based filters inside `.millhouse/` are a code smell).
- **Rationale:** Other plugins the engineer uses default to top-level `.scratch/`. Keeping mill's scratch inside `.millhouse/` fragmented the scratch pool across plugins. Moving it out unifies the convention AND frees `_worktree.copy_millhouse` from carrying a path-specific exclusion list.
- **Applies to:** scratch-move batch + docs.

### Decision: `.wiki` / `.active` junctions stay where they are

- **Decision:** `.millhouse/wiki/` (junction) stays in `.millhouse/`. `.active` (junction) stays at cwd-root. The refactor touches ONLY how code resolves the wiki — not where the junctions live on disk.
- **Rationale:** IDE sidebar grouping — one foldable `.millhouse/` folder beats four top-level hidden entries. The invariant says junctions are UI, not code contracts; policing the code-side is sufficient.
- **Applies to:** every batch — no junction-location changes.

### Decision: CLAUDE.md gets a `## Path invariants` section (not a bullet)

- **Decision:** Add a new top-level section between `## Conventions worth carrying` and any following section. Contents: junction rule, pointer to `_paths.py` as the single resolver surface, scratch-location rule (updated to `.scratch/`), optional future-pointer sentence ("new path-resolver helpers go in `_paths.py`").
- **Rationale:** Path rules keep being forgotten. A dedicated section makes them findable and gives them room to grow.
- **Applies to:** docs batch.

## All Files Touched

New files:
- `plugins/mill/scripts/_paths.py`
- `plugins/mill/unit_tests/test-paths.py`

Modified files:
- `plugins/mill/scripts/mill-add.py`
- `plugins/mill/scripts/mill-spawn.py`
- `plugins/mill/scripts/mill-list.py`
- `plugins/mill/scripts/_worktree.py` (drop `scratch` from the default exclude set in `copy_millhouse`)
- `plugins/mill/unit_tests/test-worktree.py` (drop the `scratch` exclusion assertion)
- `plugins/mill/integration_tests/test-spawn.py` (`SCRATCH` constant)
- `plugins/mill/integration_tests/test-merge.py` (`SCRATCH` constant)
- `plugins/mill/integration_tests/test-plan-assets.py` (`SCRATCH` constant)
- `plugins/mill/integration_tests/test-go-assets.py` (`SCRATCH` constant)
- `plugins/mill/integration_tests/test-review-discussion.py` (`SCRATCH` constant)
- `plugins/mill/integration_tests/test-review-plan.py` (`SCRATCH` constant)
- `plugins/mill/integration_tests/test-review-code.py` (`SCRATCH` constant)
- `plugins/mill/integration_tests/smoke-llm-claude.py` (`SCRATCH` constant)
- `plugins/mill/integration_tests/test-bootstrap.ps1` (`$scratch` variable)
- `plugins/mill/skills/conversation/SKILL.md` (scratch path text)
- `plugins/mill/skills/mill-merge/SKILL.md` (scratch path text)
- `plugins/mill/skills/mill-self-report/SKILL.md` (scratch path text)
- `plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md` (scratch path text)
- `.gitignore` (add `**/.scratch/`)
- `CLAUDE.md` (new `## Path invariants` section)
- `specs/component/README.md` (update scratch path reference)
- `specs/component/11-mill-groom-skill.md` (update two scratch path references — spec is active, not done; frozen done-* specs are NOT touched)
