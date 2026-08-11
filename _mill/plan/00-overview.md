# Plan: mill-merge-in --recompute-baseline crashes uncaught on absent status.md

```yaml
task: mill-merge-in --recompute-baseline crashes uncaught on absent status.md
slug: mill-merge-in-recompute-baseline-crash
approved: true
started: '2026-08-11T03:32:45Z'
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: crash-fix
    file: 01-crash-fix.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-merge-in-subagent.py
```

## Shared Decisions

### Decision: except-Exception-shape-matches-siblings

- **Decision:** The new try/except around `_paths.require_status_path(project_root, cfg)` in `_run_recompute_baseline` catches broad `Exception` (not narrowly `_paths.TaskHubError`), prints `json.dumps({"status": "success", "baseline": "error", "reason": str(e)})`, and returns 0 — with no additional `file=sys.stderr` diagnostic line, matching the first of the two existing sibling try/except blocks in the same function (the `parent_branch = _parent_branch.resolve(...)` block, not the `compute_baseline` block which does carry a stderr line).
- **Rationale:** `require_status_path` is analogous to the parent-branch-resolution failure — an expected, silently-recoverable pre-condition miss on the closed-PR re-entry path — not a computation failure worth a stderr breadcrumb. Broad `Exception` keeps the call site shape-consistent with its two siblings, which also catch bare `Exception`.
- **Applies to:** crash-fix.

### Decision: reason-field-verbatim

- **Decision:** The `reason` field reuses `str(e)` verbatim (including `TaskHubError`'s "run this CLI from the task hub dir" suggestion text), not a call-site-specific message.
- **Rationale:** Matches both sibling try/except blocks in the same function. The JSON line is machine-consumed by mill-merge-in's Verify step, not surfaced raw to an operator.
- **Applies to:** crash-fix.

## All Files Touched

- `plugins/mill/scripts/millpy-merge-in-subagent.py`
- `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
