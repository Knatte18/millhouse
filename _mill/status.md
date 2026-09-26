# Status

```yaml
phase: approved-merge-core-entry
slug: mill-merge-script
branch: hanf/mill-merge-script
plan: _mill/plan
parent_branch: main
parent_thread: MH:orch
task: 'mill-merge: run the deterministic path as one script'
task_description: |
  mill-merge: run the deterministic path as one script
```

## Timeline

```text
discussing  '2026-09-26T13:42:16Z'
discussion-fix-r2  '2026-09-26T13:54:26Z'
discussion-fix-r3  '2026-09-26T13:59:21Z'
discussed  '2026-09-26T13:59:21Z'
planning  '2026-09-26T14:07:43Z'
plan-review-r1  '2026-09-26T14:15:35Z'
plan-fix-r1  '2026-09-26T14:16:00Z'
plan-review-r2  '2026-09-26T14:24:02Z'
plan-fix-r2  '2026-09-26T14:24:02Z'
plan-review-r3  '2026-09-26T14:30:14Z'
planned  '2026-09-26T14:30:24Z'
implementing  '2026-09-26T14:30:43Z'
approved-merge-core-entry  '2026-09-26T14:34:53Z'
```

## Batches

```yaml
batches:
  - name: merge-core-entry
    state: approved
    implementer_session: b61bd069-f37d-40d9-b302-72803c08b49c
    start_sha: 56474e41a0afc6340d4ae33556facc914bc30d6d
    commit_sha: 8a50679157172f0d318227abd0e93341125a5c96
    verify_baseline_failures: ['NONZERO_EXIT: exit 2: /home/knatte/Code/millhouse/wts/mill-merge-script/plugins/mill/.venv/bin/python3:
    can''t open file ''/home/knatte/Code/millhouse/wts/mill-merge-script/plugins/mill/unit_tests/test-merge.py'':
    [Errno 2] N']
  - name: merge-core-squash
    state: running
    implementer_session: 89bc3804-ba78-45d9-b31b-0b26a33196f8
    start_sha: f971c521a7d7e64d770605780d465be33d081a2f
    verify_baseline_failures: ['NONZERO_EXIT: exit 2: /home/knatte/Code/millhouse/wts/mill-merge-script/plugins/mill/.venv/bin/python3:
    can''t open file ''/home/knatte/Code/millhouse/wts/mill-merge-script/plugins/mill/unit_tests/test-merge.py'':
    [Errno 2] N']
  - name: merge-cli
    state: pending
    verify_baseline_failures: ['NONZERO_EXIT: exit 1: --only: unknown test file(s): [''test-merge.py'', ''test-millpy-merge.py'']']
  - name: skill-rewrite
    state: pending
    verify_baseline_failures: []
  - name: cross-references
    state: pending
```
