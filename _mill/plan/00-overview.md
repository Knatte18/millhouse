# Plan: Fix implement finalize correctness: mid-batch stop recovery, commit-count guard, and empty-commit detection

```yaml
task: 'Fix implement finalize correctness: mid-batch stop recovery, commit-count guard, and empty-commit detection'
slug: mill-implement-finalize-gaps
approved: true
started: '2026-06-28T06:30:00Z'
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: Code Fixes and Tests
    file: 01-code-fixes-and-tests.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-implementer-common.py
  - number: 2
    name: Docs and Template
    file: 02-docs-and-template.md
    depends-on: [1]
    verify: null
```

## Shared Decisions

### Decision: verify_cmd gate-disable scope

- **Decision:** Gate-disable in `_batch_completeness_stuck` triggers only when batch-level `verify_cmd is not None`. Module-wide `module_wide_verify_cmd` does not affect the gate.
- **Rationale:** The discussion scoped the fix to `verify_cmd`. Module-wide verify is already threaded through `_run_verify_gates` before the gate is reached; gating on it would require a second parameter. The completeness gate is a heuristic backstop; a false-positive from a module-wide-only batch (where `verify_cmd=None`) produces a recoverable `stuck_type: transient` with no data loss. Known limitation, not in scope for this task.
- **Applies to:** Batch 1 Card 1 only.

### Decision: all four completeness call sites patched

- **Decision:** The discussion stated three `_batch_completeness_stuck` call sites. A fourth exists at line 888 inside the `elif start_sha is not None and snapshot_path is None` branch, with a corresponding inferred-success emit at line 894. All four must receive the `verify_cmd=verify_cmd` argument, and the `_is_only_start_batch_commit` guard must be applied before all three inference-path success emits (formatter-drift at line 802, clean-tree at line 851, no-snapshot at line 894).
- **Rationale:** The no-snapshot branch is reachable in production: `millpy-fix.py --stage full` calls `_forward_output` with `start_sha` but no `snapshot_path`. Patching only three of four sites would leave the fixer finalize path vulnerable to both the empty-commit (#557) and commits_made (#545/#560) bugs.
- **Applies to:** Batch 1 Card 2.

### Decision: inference-path guard test covers snapshot-present path

- **Decision:** The unit test for the inference-path variant of Bug #557 (Case 39) must exercise the snapshot-present clean-tree path (~line 851), not the no-snapshot path (~line 894). The test passes an existing snapshot file as `snapshot_path` so the if-branch at line 720 is taken.
- **Rationale:** The snapshot-present path is the production-reached path: `millpy-implement.py --stage finalize` always constructs a `snapshot_path` from the batch name. The no-snapshot path is reached only by `millpy-fix.py --stage full`. Covering the production path provides the higher-value regression guard.
- **Applies to:** Batch 1 Card 3.

## All Files Touched

- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/templates/implementer-brief.md`
- `plugins/mill/unit_tests/test-implementer-common.py`
