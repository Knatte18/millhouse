# Status

```yaml
phase: approved-git-pr-explicit-flag
slug: mill-infra-and-tooling-fixes
branch: hanf/mill-infra-and-tooling-fixes
plan: _mill/plan
parent: main
task: Fix daemon health-check race, finalize env-var delivery, skills-index drop, and encoding crash
task_description: |
  Fix daemon health-check race, finalize env-var delivery, skills-index drop, and encoding crash
```

## Timeline

```text
discussing  '2026-07-02T08:45:22Z'
discussion-fix-r2  '2026-07-02T09:00:00Z'
discussed  '2026-07-02T09:00:14Z'
planning  '2026-07-02T09:06:15Z'
plan-fix-r1  '2026-07-02T09:24:05Z'
planned  '2026-07-02T09:24:37Z'
implementing  '2026-07-02T09:27:42Z'
approved-daemon-respawn-on-retry  '2026-07-02T09:30:53Z'
approved-git-pr-explicit-flag  '2026-07-02T09:33:07Z'
```

## Batches

```yaml
batches:
  - name: daemon-respawn-on-retry
    state: approved
    implementer_session: 7c4d8b57-512d-4fee-94e5-ebbb341241b3
    start_sha: 04e0c147d93d4d9e596aada8ae30edcfe251e3a9
    commit_sha: 57361832432c314ac67a0bcd3647f3a73ce4f130
  - name: git-pr-explicit-flag
    state: approved
    implementer_session: 4d74d41a-9160-4877-8a94-d0e55cf16053
    start_sha: a17166842b08d1a91a7e0d11dd1d2dd8f4fe3729
    commit_sha: eb651ac9d0191ce511c1c3e6eba0c85299d8516b
  - name: skills-index-fail-loud
    state: pending
  - name: encoding-crash-migrate-fix
    state: pending
```
