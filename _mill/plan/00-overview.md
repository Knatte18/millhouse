# Plan: millpy-implement finalize/resume fixes and the red integration suites

```yaml
task: "millpy-implement finalize/resume fixes and the red integration suites"
slug: "implement-recovery-and-integration-tests"
approved: false
started: "20260926-093500"
parent_branch: "main"
discussion_sha: "d442faf1183d3a5fda1a24f9439efe12ae268ce7"
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: implementer-fixes
    file: 01-implementer-fixes.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py
  - number: 2
    name: integration-repairs
    file: 02-integration-repairs.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/test-plan-assets.py && PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/test-go-assets.py && PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/test-merge.py && PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/test-agent-mode-commit-target.py
  - number: 3
    name: spawn-suite
    file: 03-spawn-suite.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/test-spawn.py
```

## Shared Decisions

### Decision: tests-are-stale-unless-proven-otherwise

- **Decision:** the five red integration suites are repaired in the test files; product code changes only where a reproduction proves a product bug (per discussion.md `integration-suite-repairs`).
- **Rationale:** each failure traced to a deliberate later product change.
- **Applies to:** integration-repairs, spawn-suite

### Decision: finalize-side-brief-exclusion

- **Decision:** the #1162 fix lives in the finalize dirty gate, never in the resume prepare path (no second housekeeping commit).
  Reproduce first with a failing unit test using a nested task dir.
- **Rationale:** the content-commit recount subtracts only `mill-go: start batch` commits; briefs are Builder-owned bookkeeping.
- **Applies to:** implementer-fixes

### Decision: done-gate-recommendation

- **Decision:** recommend no `pipeline.done_gate` change.
  Not applied: mill-go gates on the effective config value, not this Decision.
  The acceptance bar is expressed through batch `verify:` commands (the unit file for the code batch, the five integration suites for the repair batches).
- **Rationale:** the task is scoped to two source files and five integration tests; a repo-wide suite is out of proportion.
- **Applies to:** all batches

## All Files Touched

- `plugins/mill/integration_tests/test-agent-mode-commit-target.py`
- `plugins/mill/integration_tests/test-go-assets.py`
- `plugins/mill/integration_tests/test-merge.py`
- `plugins/mill/integration_tests/test-plan-assets.py`
- `plugins/mill/integration_tests/test-spawn.py`
- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/skills/mill-go-base/SKILL.md`
- `plugins/mill/unit_tests/test-implementer-common.py`
