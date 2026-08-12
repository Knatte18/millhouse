# Status

```yaml
phase: approved-reviewer-kind-finalize-wrappers
slug: review-pipeline-consistency-bugs
branch: hanf/review-pipeline-consistency-bugs
plan: _mill/plan
parent: main
task: 'millpy-review-plan finalize: usage-error indistinguishability, flag issues, verdict rendering stale'
task_description: |
  millpy-review-plan finalize: usage-error indistinguishability, flag issues, verdict rendering stale
```

## Timeline

```text
discussing  '2026-08-12T17:45:53Z'
discussion-fix-r1  '2026-08-12T18:02:18Z'
discussion-fix-r3  '2026-08-12T18:15:44Z'
discussed  '2026-08-12T18:31:27Z'
planning  '2026-08-12T18:43:35Z'
plan-review-r1  '2026-08-12T18:53:47Z'
plan-fix-r1  '2026-08-12T18:54:09Z'
plan-fix-r2  '2026-08-12T19:00:09Z'
planned  '2026-08-12T19:00:28Z'
implementing  '2026-08-12T19:01:00Z'
approved-error-envelope-contract  '2026-08-12T19:03:54Z'
approved-reviewer-kind-finalize-wrappers  '2026-08-12T19:08:30Z'
```

## Batches

```yaml
batches:
  - name: error-envelope-contract
    state: approved
    implementer_session: 4d0cad78-cd98-446f-958e-3b53e4ae645c
    start_sha: b3b4522034b151316543cb0965fb8b53eca18c30
    commit_sha: 1ca7ef0b790659316a5349b666e21caa7ffcb007
    verify_baseline_failures: []
  - name: reviewer-kind-finalize-wrappers
    state: approved
    implementer_session: 2f270d4f-aa7d-4ba3-a861-dc51096cf174
    start_sha: d815a14ca503a1eb77331ad71ae3149681c6c491
    commit_sha: 534c0b4edb0b0bbcbbbb8eea5be1c11eec9b9e2f
    verify_baseline_failures: []
  - name: verdict-summary-demotion-note
    state: pending
    verify_baseline_failures: []
  - name: cli-round-threading
    state: pending
    verify_baseline_failures: []
  - name: skill-error-kind-retry-wiring
    state: pending
```
