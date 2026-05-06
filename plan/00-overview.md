# Plan: 8 (A) — Disable per-batch reviews (config-driven)

```yaml
task: "8 (A) — Disable per-batch reviews (config-driven)"
slug: disable-per-batch-reviews
approved: false
started: 20260506-122230
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - name: python-backend
    file: 01-python-backend.md
    depends-on: []
    verify: python plugins/mill/unit_tests/run-all.py
  - name: config-docs
    file: 02-config-docs.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: null-batch sets holistic_only inside run()

- **Decision:** The null-batch guard lives inside `_review_plan.run()`, not in the CLI. When `cfg["review"]["plan"]["batch"]` is `None`, `run()` sets `holistic_only = True` before calling `load_reviewer`. If both `batch` and `holistic` are null, raise `ReviewError` immediately.
- **Rationale:** Keeps validation in one place; all callers (CLI and tests) benefit automatically.
- **Applies to:** python-backend batch

### Decision: per_batch gating is orchestrator-owned for code review

- **Decision:** `review.code.per_batch` is a boolean config key (default true). Mill-go reads it at Entry and skips the "Code Review loop" section when false, setting batch state directly to `approved`.
- **Rationale:** Code review dispatch is mill-go's responsibility, not `_review_code.py`'s. Matching `review.code.holistic` symmetry.
- **Applies to:** config-docs batch

### Decision: no assert for per_batch=false + holistic=false

- **Decision:** Zero code review (both flags disabled) raises no error.
- **Rationale:** Intentional power-user choice; unlike plan review, code review may legitimately be skipped.
- **Applies to:** config-docs batch

## All Files Touched

- `plugins/mill/scripts/_review_plan.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/templates/wiki-config.yaml`
- `plugins/mill/unit_tests/test-review-plan-flow.py`
- `wiki/config.yaml`
