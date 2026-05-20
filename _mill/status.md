# Status

```yaml
phase: approved-migrate _paths.py
slug: pygit2-git-ops
branch: hanf/pygit2-git-ops
plan: _mill/plan
parent: main
task: Replace git subprocess calls with pygit2
task_description: |
  Replace git subprocess calls with pygit2
```

## Timeline

```text
discussing  '2026-05-20T09:01:42Z'
blocked  '2026-05-20T10:04:42Z'
discussed  '2026-05-20T10:26:10Z'
planning  '2026-05-20T10:31:54Z'
plan-review-r1  '2026-05-20T10:40:46Z'
plan-fix-r1  '2026-05-20T10:40:46Z'
plan-review-r2  '2026-05-20T11:00:19Z'
plan-fix-r2  '2026-05-20T11:00:19Z'
plan-review-r3  '2026-05-20T11:07:01Z'
plan-fix-r3  '2026-05-20T11:07:01Z'
planned  '2026-05-20T11:10:27Z'
implementing  '2026-05-20T11:13:13Z'
approved-_pygit2_util foundation  '2026-05-20T11:16:01Z'
approved-unit tests  '2026-05-20T11:18:14Z'
approved-migrate _paths.py  '2026-05-20T11:22:50Z'
```

## Batches

```yaml
batches:
  - name: _pygit2_util foundation
    state: approved
    implementer_session: da3bccd7-3198-40e3-b036-c248c7b2e0b5
    start_sha: 4822f4e02ccf718a962da8565661bb4a8eb99d41
  - name: unit tests
    state: approved
    implementer_session: daea89bc-cdde-4a4d-8233-a5a8b69d9f1b
    start_sha: 3cfdeb015253912d4799efe55c8ee7cd69c6be24
  - name: migrate _paths.py
    state: approved
    implementer_session: d2688d68-a39e-466b-a602-eef2d0730c17
    start_sha: 6a90fd0beaac77e31fbe50292becfe2f4acbf2f4
  - name: migrate _marker.py and _worktree.list_worktrees
    state: running
    implementer_session: 47e18dd3-9a72-48f6-8cb3-896003000ccf
    start_sha: 0f52a5d3474d99fa9d3bf8117330113a16eef388
  - name: migrate _cleanliness.py and _review_common.py
    state: pending
```
