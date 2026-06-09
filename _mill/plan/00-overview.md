# Plan: Fix millpy-review-discussion to write briefs to the task worktree

```yaml
task: Fix millpy-review-discussion to write briefs to the task worktree
slug: review-discussion-brief-path
approved: true
started: 20260609-124907
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: fix-and-test
    file: 01-fix-and-test.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-review-cli.py
```

## Shared Decisions

### Decision: targeted-fix-only

- **Decision:** Change only the `briefs_dir` variable in `millpy-review-discussion.py`; leave `project_root = hub_dir` and all other uses of `project_root` intact.
- **Rationale:** `project_root = hub_dir` is correct for registry loading, task-title lookup, and constraint reading. A global rename would silently break those callers.
- **Applies to:** batch fix-and-test

## All Files Touched

- `plugins/mill/scripts/millpy-review-discussion.py`
- `plugins/mill/unit_tests/test-review-cli.py`
