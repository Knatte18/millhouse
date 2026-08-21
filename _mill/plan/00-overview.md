# Plan: mill-merge/merge-in: nested-layout config resolution, stale locks, and rollback-target bugs

```yaml
task: 'mill-merge/merge-in: nested-layout config resolution, stale locks, and rollback-target bugs'
slug: mill-merge-nested-layout-and-lock-bugs
approved: true
started: 20260821-092340
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: mill-merge-push-and-lock
    file: 01-mill-merge-push-and-lock.md
    depends-on: []
    verify: null
  - number: 2
    name: mill-merge-in-nested-cwd
    file: 02-mill-merge-in-nested-cwd.md
    depends-on: []
    verify: null
  - number: 3
    name: parent-branch-liveness
    file: 03-parent-branch-liveness.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-parent-branch.py
  - number: 4
    name: config-caller-alignment
    file: 04-config-caller-alignment.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-config.py
```

## Shared Decisions

### Decision: independent-file batches, no cross-batch dependency

- **Decision:** All four batches touch disjoint files (two SKILL.md docs, one standalone script + its test, and a three-file script/test group) with no shared state or ordering requirement between them.
- **Rationale:** Each of the seven source bugs (#904, #862, #863, #879, #900, #899, #880) maps to one of four independent fix areas, confirmed via source read during discussion (`_mill/discussion.md`). Splitting further would fragment single-file edits across batches for no benefit; merging further would mix unrelated subsystems (docs-only SKILL.md prose vs. Python code+tests) into one Sonnet context.
- **Applies to:** all batches

### Decision: SKILL.md batches are docs-only, `verify: null`

- **Decision:** Batches 1 and 2 edit only `SKILL.md` prose (instructions an LLM orchestrator follows at runtime) — no Python code exists to unit-test the edited behavior directly, so their per-batch `verify:` is `null`.
- **Rationale:** Per mill-plan's own "verify: is null or missing -- pure-docs batches have no runnable surface" convention. The DAG helpers these SKILL.md files reference (`_parent_branch.py`, `_plan_dag.py`, etc.) are unmodified by these batches — no regression surface to test.
- **Applies to:** mill-merge-push-and-lock, mill-merge-in-nested-cwd

### Decision: no `mill-config.yaml` mutation, `done_gate` left as-is

- **Decision:** This plan does not touch `mill-config.yaml`'s `pipeline.done_gate` key (currently `null`).
- **Rationale:** Setting a repo-wide lint/test `done_gate` is an unrelated hub-configuration improvement, out of scope for this bug-fix task; doing so here would also trigger the `wiki-config-mutation` validator check for no reason tied to any of the seven source bugs.
- **Applies to:** all batches

## All Files Touched

- `plugins/mill/scripts/_config.py`
- `plugins/mill/scripts/_parent_branch.py`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/scripts/millpy-review-plan.py`
- `plugins/mill/skills/mill-merge-in/SKILL.md`
- `plugins/mill/skills/mill-merge/SKILL.md`
- `plugins/mill/unit_tests/test-config.py`
- `plugins/mill/unit_tests/test-parent-branch.py`
