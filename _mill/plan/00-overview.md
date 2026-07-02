# Plan: Fix daemon health-check race, finalize env-var delivery, skills-index drop, and encoding crash

```yaml
task: Fix daemon health-check race, finalize env-var delivery, skills-index drop, and encoding crash
slug: mill-infra-and-tooling-fixes
approved: true
started: 20260702-090427
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: daemon-respawn-on-retry
    file: 01-daemon-respawn-on-retry.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-wiki-client-retry.py
  - number: 2
    name: git-pr-explicit-flag
    file: 02-git-pr-explicit-flag.md
    depends-on: []
    verify: null
  - number: 3
    name: skills-index-fail-loud
    file: 03-skills-index-fail-loud.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-skills-index.py
  - number: 4
    name: encoding-crash-migrate-fix
    file: 04-encoding-crash-migrate-fix.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-wiki-migrate-print.py
```

## Shared Decisions

### Decision: all four batches are independent (Layer A)

- **Decision:** All four batches carry `depends-on: []` — there is no DAG ordering constraint between them.
- **Rationale:** The four fixes touch entirely disjoint files (`wiki/_client.py`; `git-pr`+`mill-finalize` SKILL.md; `millpy-skills-index.py`; `millpy-wiki-migrate.py`) and originate from four separate GitHub issues (#594, #591, #589, #588) that were already explicitly consolidated into this one wiki task. Splitting them into a dependency chain would be structurally false and would serialize work that can run fully in parallel.
- **Applies to:** all batches.

### Decision: Python verify commands use the `PYTHONPATH= ` isolation prefix

- **Decision:** Every non-null `verify:` command in this plan is prefixed with the literal `PYTHONPATH= ` (empty value, single space) before the test invocation.
- **Rationale:** Per CLAUDE.md's "Verify command shape" convention — without the prefix, the test subprocess inherits the mill plugin cache's `PYTHONPATH` from the parent shell and can load stale cache modules instead of the worktree's own `plugins/mill/scripts/` modules, silently testing the wrong code.
- **Applies to:** batches 01 (`daemon-respawn-on-retry`), 03 (`skills-index-fail-loud`), 04 (`encoding-crash-migrate-fix`). Batch 02 (`git-pr-explicit-flag`) has `verify: null` — it edits only SKILL.md prose/bash instructions consumed by an LLM orchestrator, with no automated test harness to isolate.

## All Files Touched

- `plugins/mill/scripts/millpy-skills-index.py`
- `plugins/mill/scripts/millpy-wiki-migrate.py`
- `plugins/mill/scripts/wiki/_client.py`
- `plugins/mill/skills/git-pr/SKILL.md`
- `plugins/mill/skills/mill-finalize/SKILL.md`
- `plugins/mill/unit_tests/test-skills-index.py`
- `plugins/mill/unit_tests/test-wiki-client-retry.py`
- `plugins/mill/unit_tests/test-wiki-migrate-print.py`
