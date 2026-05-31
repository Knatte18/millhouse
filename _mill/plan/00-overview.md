# Plan: mill-go / mill-merge / plan-validator follow-up bugs (round 2)

```yaml
task: mill-go / mill-merge / plan-validator follow-up bugs (round 2)
slug: mill-orchestration-hardening-r2
approved: true
started: 20260531-083617
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: text-and-template
    file: 01-text-and-template.md
    depends-on: []
    verify: null
  - number: 2
    name: fixer-inferred-success
    file: 02-fixer-inferred-success.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-millpy-fix.py
  - number: 3
    name: validate-and-config
    file: 03-validate-and-config.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-plan-validate.py test-config.py
```

## Shared Decisions

### Decision: no-cross-batch-dependencies

- **Decision:** All three batches are independent (no shared files, no ordering requirement). All run in parallel (Layer A).
- **Rationale:** Each bug fix touches a disjoint set of files. Parallelising reduces total wall-clock time and avoids merge conflicts inside the plan.
- **Applies to:** all batches

### Decision: existing-test-style

- **Decision:** New unit tests follow the `main() -> int` pattern already used in `test-implementer-common.py`, `test-plan-validate.py`, and `test-config.py` — not pytest. Use `tempfile.TemporaryDirectory` for fixtures; assert conditions directly, increment an `errors` counter, return 0 on success.
- **Rationale:** Consistency with the existing suite; `run-all.py` discovers tests via the `main()` entry point, not pytest discovery.
- **Applies to:** batches 2, 3

### Decision: skill-md-is-prose

- **Decision:** SKILL.md edits are minimal targeted text replacements — no structural rewrites. The implementer reads the surrounding context to locate the exact sentence, then applies a surgical edit.
- **Rationale:** SKILL.md files are executed as prompts; wholesale rewrites risk breaking adjacent steps. Surgical edits are easier to review.
- **Applies to:** batch 1

## All Files Touched

- `plugins/mill/scripts/_config.py`
- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/scripts/_plan_validate.py`
- `plugins/mill/scripts/millpy-fix.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-merge/SKILL.md`
- `plugins/mill/templates/merge-in-conflict-brief.md`
- `plugins/mill/unit_tests/test-config.py`
- `plugins/mill/unit_tests/test-implementer-common.py`
- `plugins/mill/unit_tests/test-millpy-fix.py`
- `plugins/mill/unit_tests/test-plan-validate.py`
