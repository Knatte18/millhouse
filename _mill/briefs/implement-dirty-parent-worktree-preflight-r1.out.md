Both cards (15 and 16) declared in this batch are committed: 2 of 2 cards complete. Verify passed with exit code 0.

Summary: 2 of 2 cards committed.

- Card 15 — `plugins/mill/skills/mill-merge/SKILL.md`: added the pre-squash dirty-parent-worktree check to Step 5's "Direct path" (runs `git -C <parent-path> status --porcelain --untracked-files=no` before `merge --squash`, scoped to `mode == 'worktree'` only, with the two-scenario halt message), plus a "Dirty-parent-worktree halt (Step 5)" carve-out added to the `## Rollback (Steps 1-5 only)` section mirroring the existing Step-4 carve-out. Commit `ce4e1af9`.
- Card 16 — `plugins/mill/integration_tests/test-merge.py`: added three lightweight single-repo fixtures (`container_dirty`, `container_retry`, `container_untracked`) immediately before the flat-hub scenario's `merge --squash` call, proving the underlying git status check flags both halt scenarios and ignores untracked-only noise; registered all three in `main()`'s `finally:` block. Commit `ce1a5c01`.

Verify command `PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/test-merge.py` passed (exit code 0), including all three new PASS assertions plus every pre-existing assertion in the file. Pre-existing `ruff check` findings (16, unrelated import-ordering/f-string/subprocess-check issues) were confirmed present in the pre-change version of the file via `git show HEAD:...`, so they are out of scope for this batch and were left untouched per the isolation instructions.

{"status":"success","commit_sha":"ce1a5c01","session_id":"686bec2e-ffb3-4c08-a7d3-e7d304ea7af1","cards_done":[15,16]}