# Status

```yaml
phase: approved-dotnet-verify-lock-retry
slug: mill-go-windows-buildserver-lock-hygiene
branch: hanf/mill-go-windows-buildserver-lock-hygiene
plan: _mill/plan
parent: main
task: 'mill-go/millpy-implement: Windows dotnet build-server file-lock races in verify/baseline stages'
task_description: |
  mill-go/millpy-implement: Windows dotnet build-server file-lock races in verify/baseline stages
```

## Timeline

```text
discussing  '2026-08-14T08:33:12Z'
discussion-fix-r1  '2026-08-14T08:49:35Z'
discussion-fix-r2  '2026-08-14T08:54:20Z'
discussed  '2026-08-14T08:54:20Z'
planning  '2026-08-14T09:14:45Z'
plan-review-r1  '2026-08-14T09:20:33Z'
plan-fix-r1  '2026-08-14T09:21:38Z'
plan-fix-r2  '2026-08-14T09:29:00Z'
planned  '2026-08-14T09:30:00Z'
implementing  '2026-08-14T09:29:07Z'
approved-dotnet-verify-lock-retry  '2026-08-14T09:34:39Z'
```

## Batches

```yaml
batches:
  - name: dotnet-verify-lock-retry
    state: approved
    implementer_session: 4e041b01-ad5c-4a7d-9353-d5c99d731921
    start_sha: 784d965bcd6cd65832d3c5944a6bbec322f9580e
    commit_sha: f12599738e1bf3856a2be9264e30cb7cabdd177a
    verify_baseline_failures: []
  - name: baseline-teardown-defense-in-depth
    state: running
    implementer_session: 261f9d10-6820-4378-92e8-bef69697ed5c
    start_sha: 2df2ed9f8330eff7c59d338b1156ac12c287d5c5
    verify_baseline_failures: []
```
