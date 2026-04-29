# Plan: 11 — par-C — Container layout overhaul + cwd-as-hub everywhere + gitignore-split

```yaml
task: 11 — par-C — Container layout overhaul + cwd-as-hub everywhere + gitignore-split
slug: container-restructure
approved: true
started: 20260429-094807
parent: main
root: ""
verify: python plugins/mill/unit_tests/run-all.py
```

## Batch Index

```yaml
batches:
  - name: foundation
    file: 01-foundation.md
    depends-on: []
    verify: python plugins/mill/unit_tests/run-all.py
  - name: create-hub-links
    file: 02-create-hub-links.md
    depends-on: [foundation]
    verify: python plugins/mill/unit_tests/run-all.py
  - name: state-on-worktree
    file: 03-state-on-worktree.md
    depends-on: [create-hub-links]
    verify: python plugins/mill/unit_tests/run-all.py
  - name: consumers-and-skills
    file: 04-consumers-and-skills.md
    depends-on: [state-on-worktree]
    verify: python plugins/mill/unit_tests/run-all.py
  - name: migration-and-docs
    file: 05-migration-and-docs.md
    depends-on: [consumers-and-skills]
    verify: null
```

## Shared Decisions

### Decision: TDD-where-possible, integration-otherwise

- **Decision:** Pure functions in `_sibling.py`, `_paths.py`, `_gitignore.py`, `_setup.py` are written test-first. Each card in batch 01 (and the new helper card in batch 02) lands tests in the same commit as the implementation. Integration-heavy code (`millpy-spawn.py`, `millpy-claim.py`, cross-worktree consumers, `mill-merge` teardown) is implemented first, then verified by extending existing test files or adding fixture-based tests. Manual verification covers the migration script — it is a one-shot operation against a real on-disk layout.
- **Rationale:** Pure helpers are cheap to test and mistakes in them ripple through every script that uses them. Integration cost dominates for I/O-heavy scripts; tests there are smoke-checks against fixtures, not full coverage. Mirrors discussion.md `## Testing`.
- **Applies to:** all batches.

### Decision: YAML quoting via `_yaml_writer.quote_scalar`

- **Decision:** Every YAML scalar emitted into a fenced ```yaml block of a generated file (status.md, active.slug.md, plan files, review files, status writes from `_status.update_field`, etc.) is passed through `_yaml_writer.quote_scalar` before substitution into a template. Raw f-string YAML is forbidden in writers.
- **Rationale:** Project convention; avoids quoting bugs from special characters in task titles, slugs, branch names. Matches existing `_active.write` and `_status.render_initial` shape.
- **Applies to:** any card that writes YAML scalars, particularly batches 02–04.

### Decision: All path resolution goes through `_paths.py`

- **Decision:** No new `_resolve_*` helpers added to individual `millpy-*.py` scripts. Every path computation that needs to know about hub/worktree/wiki/container/portals goes through a function in `_paths.py`. New helpers added in this task: `resolve_hub_relative_path`, `resolve_active_worktree`. Existing helpers updated: `resolve_worktrees_dir` (fallback expression). The only resolver that may stay scattered is direct `Path.cwd()` use at script entry points (project-root anchor for review CLIs).
- **Rationale:** CLAUDE.md path invariants. Keeps the cwd-as-hub story coherent — every script that asks "where is the hub-relative subdir inside this worktree" gets the same answer through one function.
- **Applies to:** all batches.

### Decision: Plugin scripts reference `${CLAUDE_PLUGIN_ROOT}`, never source repo paths

- **Decision:** All new prose in SKILL.md files and any subprocess invocations of mill scripts use `${CLAUDE_PLUGIN_ROOT}/scripts/...`. Hardcoded `plugins/mill/scripts/...` paths are forbidden in SKILL.md prose. Test files under `plugins/mill/unit_tests/` may reference `plugins/mill/scripts/...` directly because tests run from the source repo.
- **Rationale:** Plugins install on user machines that may have no millhouse source checkout. Existing CLAUDE.md invariant.
- **Applies to:** batches 02–05.

### Decision: Junctions are IDE/terminal convenience only

- **Decision:** No script reads from `.millhouse/wiki`, `.others/<slug>/`, `.active/`, or any other junction to discover paths. `_paths.resolve_active_worktree` and friends return the real underlying directory; junctions are only created (and removed at teardown). Test fixtures do not require junctions.
- **Rationale:** CLAUDE.md path invariant. Junctions are unreliable across machines and break under filesystem operations.
- **Applies to:** all batches.

### Decision: wiki/config.yaml change atomicity

- **Decision:** Each card that modifies `wiki/config.yaml` lands the change in the same commit as the code that consumes the new shape. Specifically: junctions block updates (Card 10) ship with the spawn/claim wiring; paths block updates (Card 14) ship with the review-subsystem wiring. The wiki commit message follows the same convention as the source-repo commit (e.g. `feat(wiki-config): retarget .active to portals/<SLUG>/`).
- **Rationale:** wiki/config.yaml is consumed at runtime by every mill script. A schema change without a code change leaves running clones broken between fetches.
- **Applies to:** batches 02 and 03.

## All Files Touched

- `CLAUDE.md`
- `plugins/codeguide/scripts/_sibling.py`
- `plugins/mill/scripts/_gitignore.py`
- `plugins/mill/scripts/_paths.py`
- `plugins/mill/scripts/_review_code.py`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/scripts/_review_discussion.py`
- `plugins/mill/scripts/_review_plan.py`
- `plugins/mill/scripts/_setup.py`
- `plugins/mill/scripts/_sibling.py`
- `plugins/mill/scripts/_spawn_core.py`
- `plugins/mill/scripts/millpy-claim.py`
- `plugins/mill/scripts/millpy-cleanup.py`
- `plugins/mill/scripts/millpy-inspect.py`
- `plugins/mill/scripts/millpy-list.py`
- `plugins/mill/scripts/millpy-migrate-layout.py`
- `plugins/mill/scripts/millpy-review-code.py`
- `plugins/mill/scripts/millpy-review-discussion.py`
- `plugins/mill/scripts/millpy-review-plan.py`
- `plugins/mill/scripts/millpy-spawn.py`
- `plugins/mill/scripts/millpy-status.py`
- `plugins/mill/scripts/millpy-terminal.py`
- `plugins/mill/scripts/millpy-vscode.py`
- `plugins/mill/skills/mill-merge/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/skills/mill-resume/SKILL.md`
- `plugins/mill/skills/mill-self-report/SKILL.md`
- `plugins/mill/skills/mill-setup/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/templates/config.local.yaml`
- `plugins/mill/unit_tests/test-cleanup.py`
- `plugins/mill/unit_tests/test-gitignore-phase.py`
- `plugins/mill/unit_tests/test-millpy-claim.py`
- `plugins/mill/unit_tests/test-millpy-spawn.py`
- `plugins/mill/unit_tests/test-millpy-terminal.py`
- `plugins/mill/unit_tests/test-millpy-vscode.py`
- `plugins/mill/unit_tests/test-paths.py`
- `plugins/mill/unit_tests/test-review-code-flow.py`
- `plugins/mill/unit_tests/test-review-common.py`
- `plugins/mill/unit_tests/test-review-discussion-flow.py`
- `plugins/mill/unit_tests/test-review-plan-flow.py`
- `plugins/mill/unit_tests/test-setup-hub-links.py`
- `plugins/mill/unit_tests/test-sibling.py`
- `plugins/mill/unit_tests/test-spawn-core.py`
- `wiki/config.yaml`
