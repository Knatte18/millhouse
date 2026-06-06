# Status

```yaml
phase: approved-impl-fix-merge-seam
slug: subprocess-to-agents
branch: hanf/subprocess-to-agents
plan: _mill/plan
parent: main
task: Replace subprocess dispatch with Agent SDK calls
task_description: |
  Replace subprocess dispatch with Agent SDK calls
```

## Timeline

```text
discussing  '2026-06-06T12:30:32Z'
discussion-fix-r4  '2026-06-06T13:39:13Z'
discussed  '2026-06-06T13:39:25Z'
planning  '2026-06-06T13:57:46Z'
plan-fix-r1  '2026-06-06T14:06:43Z'
planned  '2026-06-06T14:06:58Z'
implementing  '2026-06-06T14:11:58Z'
approved-config-and-dispatch-helper  '2026-06-06T14:31:50Z'
approved-subagent-definitions  '2026-06-06T14:39:33Z'
approved-impl-fix-merge-seam  '2026-06-06T14:49:20Z'
```

## Batches

```yaml
batches:
  - name: config-and-dispatch-helper
    state: approved
    implementer_session: 99d57733-aafd-41b3-8e82-f9361ea1a230
    start_sha: bb0acec5850d24531952ce1edb11188674419a9f
    commit_sha: 6b93750557a64ce9731c26e5c916d9d110b37df0
  - name: subagent-definitions
    state: approved
    implementer_session: b4453d23-78b2-4946-8146-624c7bcfd0f7
    start_sha: 250202504d01bfaed20dc9479dea878e4e2becfb
    commit_sha: 59477ff02230fc00dcdd1b483d7ed11b9b4f507d
  - name: impl-fix-merge-seam
    state: approved
    implementer_session: e6026afd-a7c4-4fce-b857-a8898d99e324
    start_sha: 368f4ed0b7d19e74c5399bfa78a1d84af933a856
    commit_sha: 5bbb34a9afe1f3879db26a80eecc1d54b3bcadf9
  - name: review-seam
    state: running
    implementer_session: 1aec85c6-41a5-494f-aadb-cc1f15872b39
    start_sha: 0728a5c387e427d51fd40b5ad9cd6552ea12a7c4
  - name: skill-mill-go
    state: pending
  - name: skill-others
    state: pending
  - name: agent-mode-parity-test
    state: pending
```
