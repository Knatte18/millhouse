# Plan: Repair two failing unit tests on main

```yaml
task: "Repair two failing unit tests on main"
slug: "fix-stale-unit-tests"
approved: false
started: "20260924-054200"
parent: "main"
root: ""
verify: null
discussion_sha: "21b2165ec629d1c57671cac439882042286bb94e"
```

## Batch Index

```yaml
batches:
  - number: 1
    name: repair-stale-tests
    file: 01-repair-stale-tests.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-validate-plan.py test-mill-go-base-agent-only.py
```

## Shared Decisions

### Decision: test-only change

- **Decision:** edit only the two test files; leave `millpy-validate-plan.py`, `_plan_validate.py`, and every SKILL.md untouched.
- **Rationale:** the code under test moved on legitimately; the tests are stale (GitHub issues #1147, #1146).
- **Applies to:** repair-stale-tests

### Decision: done-gate-left-null

- **Decision:** `pipeline.done_gate` stays `null`.
- **Rationale:** `uvx ruff check .` run from the worktree tip exits 1 (pre-existing repo-wide lint debt unrelated to this task), so it cannot be a default gate; the batch's scoped `verify:` covers both edited files.
- **Applies to:** all batches

## All Files Touched

- `plugins/mill/unit_tests/test-mill-go-base-agent-only.py`
- `plugins/mill/unit_tests/test-millpy-validate-plan.py`
