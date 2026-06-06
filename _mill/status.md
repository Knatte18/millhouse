# Status

```yaml
phase: approved-config-and-dispatch-helper
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
    state: running
    implementer_session: b4453d23-78b2-4946-8146-624c7bcfd0f7
    start_sha: 250202504d01bfaed20dc9479dea878e4e2becfb
  - name: impl-fix-merge-seam
    state: pending
  - name: review-seam
    state: pending
  - name: skill-mill-go
    state: pending
  - name: skill-others
    state: pending
  - name: agent-mode-parity-test
    state: pending
```
