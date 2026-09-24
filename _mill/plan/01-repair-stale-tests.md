# Batch: repair-stale-tests

```yaml
task: "Repair two failing unit tests on main"
batch: "repair-stale-tests"
number: 1
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-validate-plan.py test-mill-go-base-agent-only.py
depends-on: []
```

## Batch Scope

Two independent one-line repairs to stale unit tests, delivered as one batch because each is a few lines and they share one verify command.
No interface is consumed by a later batch.
No batch-local decisions differ from `## Shared Decisions`.

## Cards

### Card 1: Accept done_gate in the validate-plan test fake

- **Context:**
  - `plugins/mill/scripts/millpy-validate-plan.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-validate-plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `test_cli_uses_resolve_hub_path_not_cwd_for_project_root`, change the nested fake `_fake_plan_validate_run` so its signature gains a keyword-only `done_gate=None` parameter after `skip_checks`.
  The CLI's `main` now passes `done_gate=...` to `_plan_validate.run`, and the fake raised `TypeError` without it.
  Keep the fake's body unchanged and do not use a `**kwargs` catch-all.
  Do not assert a specific `done_gate` value.
- **Commit:** `test(validate-plan): accept done_gate in _fake_plan_validate_run`

### Card 2: Stop banning millpy-bg in the agent-only guard

- **Context:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Edits:**
  - `plugins/mill/unit_tests/test-mill-go-base-agent-only.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the module-level `BANNED_LITERALS` tuple, remove the `"millpy-bg"` entry and keep `"psmux"` and `"dispatch == subprocess"`.
  The `millpy-bg` helper is live and used by the mill-go-base skill, so only the other two literals guard dead dispatch paths.
  No docstring or comment edit is needed; `millpy-bg` appears in this file only in that tuple.
- **Commit:** `test(mill-go-base): drop millpy-bg from agent-only banned literals`

## Batch Tests

`verify:` runs `run-all.py --only` on the two edited test files; both must pass.
Scope is per-batch, not the full suite, since no cross-cutting helper is touched.
