# Status

```yaml
phase: approved-session-name-callers
slug: session-name-short-prefix
branch: hanf/session-name-short-prefix
plan: _mill/plan
parent: main
task: Prefix session names with repo short name; add MH:orch session
task_description: |
  Prefix session names with repo short name; add MH:orch session
```

## Timeline

```text
discussing  '2026-09-24T07:53:59Z'
discussion-fix-r3  '2026-09-24T08:57:17Z'
discussed  '2026-09-24T09:06:36Z'
planning  '2026-09-24T09:12:43Z'
plan-review-r1  '2026-09-24T09:18:10Z'
plan-fix-r1  '2026-09-24T09:18:29Z'
planned  '2026-09-24T09:18:36Z'
implementing  '2026-09-24T09:18:54Z'
approved-core-helpers  '2026-09-24T09:21:58Z'
approved-session-name-callers  '2026-09-24T09:24:28Z'
```

## Batches

```yaml
batches:
  - name: core-helpers
    state: approved
    implementer_session: de75e4bb-2517-4295-a3bf-4d7337f258c2
    start_sha: d13bf2d58474efd28b92d33a430d333af63c7d7a
    commit_sha: e5b1e07730530835f30d7e8beffe9a32fb13c5a2
    verify_baseline_failures: ['NONZERO_EXIT: exit 1: Using CPython 3.14.4 interpreter at: /usr/bin/python3', 'NONZERO_EXIT:
    exit 1: --only: unknown test file(s): [''test-paths-short-name.py'', ''test-setup-short-name.py'']']
  - name: session-name-callers
    state: approved
    implementer_session: 627b2a00-bf91-4781-9f41-cd0553d0c907
    start_sha: 3d8701550ee8a89616a519eab3e30b48dcb42ef9
    commit_sha: 150500db84a6e6d98c4d518643a7900da6074df4
    verify_baseline_failures: []
  - name: docs-and-setup
    state: running
    implementer_session: 65f4124e-3a5a-44a1-80f3-6b0f8d67b219
    start_sha: fee4a630d839abaa828649b61aa27bc07217ae44
    verify_baseline_failures: []
```
## Inferred-success log

```text
'2026-09-24T09:21:50Z'  core-helpers  round 1
'2026-09-24T09:24:28Z'  session-name-callers  round 1
'2026-09-24T09:25:58Z'  docs-and-setup  round 1
```
