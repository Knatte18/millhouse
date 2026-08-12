# Status

```yaml
phase: approved-yaml-injection
slug: reviewer-cost-summary
branch: hanf/reviewer-cost-summary
plan: _mill/plan
parent: main
task: Surface reviewer time/tool-call cost + a review-summary command
task_description: |
  Surface reviewer time/tool-call cost + a review-summary command
```

## Timeline

```text
discussing  '2026-08-11T18:34:38Z'
discussed  '2026-08-11T19:51:12Z'
planning  '2026-08-12T06:29:29Z'
plan-review-r1  '2026-08-12T06:37:07Z'
plan-fix-r1  '2026-08-12T06:37:07Z'
plan-fix-r2  '2026-08-12T06:43:18Z'
planned  '2026-08-12T06:43:34Z'
implementing  '2026-08-12T06:51:25Z'
approved-provider-contract  '2026-08-12T07:03:06Z'
approved-yaml-injection  '2026-08-12T07:06:57Z'
```

## Batches

```yaml
batches:
  - name: provider-contract
    state: approved
    implementer_session: 08521e07-7892-49ad-994e-9437d22f51c0
    start_sha: 8375d71b3c0f121366af151455ff8bb916024a4e
    commit_sha: 846a2ee82262ff811902a9556fe501a7e5a8fcc1
    verify_baseline_failures: []
  - name: yaml-injection
    state: approved
    implementer_session: 1b30fd1e-841a-427a-b15f-b01293719c73
    start_sha: 7481eb9fc7fe01e5835ea40a321326e7ec426fa4
    commit_sha: b5a27e30ffbc1cecf0dc19a31b131187d6785dfa
    verify_baseline_failures: []
  - name: dispatcher-flip
    state: running
    implementer_session: 69f54917-8ed8-4173-a49d-0459bedddae4
    start_sha: 6c51d56778b58f323cf945f33969568a2315cbc8
    verify_baseline_failures: []
  - name: summary-command
    state: pending
    verify_baseline_failures: []
  - name: discussion-metadata
    state: pending
    verify_baseline_failures: []
  - name: code-metadata
    state: pending
    verify_baseline_failures: []
  - name: plan-metadata
    state: pending
    verify_baseline_failures: []
  - name: cli-flags
    state: pending
    verify_baseline_failures: []
  - name: orchestrator-shared
    state: pending
  - name: orchestrator-callers
    state: pending
```
