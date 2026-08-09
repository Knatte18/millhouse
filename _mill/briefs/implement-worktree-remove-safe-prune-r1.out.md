Both cards committed (2 of 2). Card 1 commit `b95f67ce` matches the plan's `Commit:` message for Card 1; card 2 commit `ced7b6db` matches Card 2's `Commit:` message. Verify passed with exit 0.

{"status":"success","commit_sha":"ced7b6db9d71e9c4b133232256d35f5005bfda53","session_id":"0f748ca9-9721-49cd-bbda-78e72a0fc40f","cards_done":[1,2]}

Summary: 2 of 2 cards committed.

- `plugins/mill/scripts/_worktree.py` — restructured `remove_safe` so `git worktree prune` runs unconditionally exactly once after either the direct-success branch or the fallback branch, via a shared `removed_via` variable and trailing block.
- `plugins/mill/unit_tests/test-worktree.py` — added a real-git (no mocks) end-to-end test reproducing the nested-worktree orphan scenario: registers a task worktree with a nested `.scratch/nested` worktree, force-removes the task worktree via `remove_safe`, and asserts the nested worktree's stale registration is pruned from `list_worktrees(hub)` and that the direct-success ("removed via git") branch actually ran.

Verify command `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-worktree.py` passed (exit 0), including the new test. `git status --porcelain --untracked-files=no` is clean.

{"status":"success","commit_sha":"ced7b6db9d71e9c4b133232256d35f5005bfda53","session_id":"0f748ca9-9721-49cd-bbda-78e72a0fc40f","cards_done":[1,2]}
